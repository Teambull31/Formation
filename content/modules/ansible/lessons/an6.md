# Déploiement progressif, CI et Terraform + Ansible

Dernière étape : déployer une nouvelle version sur tout le parc **sans coupure**, faire valider chaque changement d'Ansible par la CI, et brancher Ansible sur l'infrastructure créée par Terraform.

## Le déploiement progressif

Par défaut, Ansible agit sur tous les hôtes d'un groupe en parallèle (5 à la fois, réglable par `forks`). Pour une mise à jour applicative, on veut l'inverse : quelques serveurs à la fois, en s'arrêtant au premier problème.

```yaml
- name: Déployer l'application
  hosts: web
  become: true
  serial: 1
  max_fail_percentage: 0
  pre_tasks:
    - name: Retirer du répartiteur
      ansible.builtin.uri:
        url: "http://lb.internal/api/drain/{{ inventory_hostname }}"
        method: POST
      delegate_to: localhost
  roles:
    - role: app
  post_tasks:
    - name: Attendre que l'application réponde
      ansible.builtin.uri:
        url: "http://{{ ansible_host }}:8000/health"
      register: health
      until: health.status == 200
      retries: 10
      delay: 3
    - name: Remettre dans le répartiteur
      ansible.builtin.uri:
        url: "http://lb.internal/api/enable/{{ inventory_hostname }}"
        method: POST
      delegate_to: localhost
```

Tous les réglages de lot (`serial`, `max_fail_percentage`) sont des clés du **play**, alignées sur `hosts:` : ils décrivent comment le play parcourt les hôtes, pas ce qu'une tâche fait. `pre_tasks`, `roles` et `post_tasks` sont aussi des clés du play, et Ansible les exécute **toujours** dans cet ordre, quel que soit leur ordre dans le fichier :

```
pour chaque lot de serial hôtes :
  1. pre_tasks    ← sortir l'hôte du répartiteur
  2. roles        ← installer la nouvelle version
  3. tasks        ← (s'il y en a)
  4. post_tasks   ← vérifier la santé, PUIS remettre dans le répartiteur
  5. handlers     ← notifiés pendant le lot
```

On les écrit quand même dans cet ordre dans le fichier, pour que la lecture suive l'exécution.

`delegate_to: localhost` est un mot-clé de **tâche** : aligné sur `ansible.builtin.uri:`, pas dessous. La tâche tourne alors sur le nœud de contrôle, mais `inventory_hostname` vaut toujours l'hôte du lot en cours : c'est ce qui permet de dire au répartiteur quel serveur retirer.

- `serial: 1` (ou `"25%"`, ou `[1, 5, "50%"]`) : le play traite les hôtes par lots.
- `max_fail_percentage: 0` : un seul échec arrête tout le déploiement, les lots suivants ne sont pas touchés.
- `pre_tasks` / `post_tasks` encadrent les rôles : sortir l'hôte du répartiteur, vérifier qu'il répond, le remettre.
- `delegate_to: localhost` exécute une tâche depuis le nœud de contrôle au nom de l'hôte courant.

!!Sans serial, une mauvaise version part sur tous les serveurs en même temps : la panne est totale au lieu d'être limitée à un serveur!!

!!Une vérification de santé placée après la remise dans le répartiteur laisse passer du trafic vers un serveur cassé!!

## Tags et exécutions partielles

```yaml
    - name: Déposer la configuration
      ansible.builtin.template:
        src: app.conf.j2
        dest: /etc/app/app.conf
        mode: "0640"
      tags: [config]
```

`ansible-playbook site.yml --tags config` ne lance que les tâches marquées ; `--skip-tags slow` les exclut ; `--list-tags` les affiche. Pratique pour une correction rapide, à condition que chaque tâche reste correcte seule.

## Ansible dans la CI

À chaque pull request :

1. `ansible-lint` : bonnes pratiques et erreurs fréquentes ;
2. `ansible-playbook --syntax-check` ;
3. optionnellement, Molecule pour tester les rôles dans un conteneur.

Après fusion, le déploiement lance le playbook depuis la CI, avec la clé SSH et le mot de passe du coffre en **secrets**, dans un environnement protégé.

```yaml
name: Ansible
on:
  pull_request:
permissions:
  contents: read
jobs:
  lint:
    runs-on: ubuntu-latest
    timeout-minutes: 10
    steps:
      - uses: actions/checkout@v4
      - run: pip install ansible-core==2.17.5 ansible-lint==24.9.2
      - run: ansible-lint
      - run: ansible-playbook -i inventories/staging/hosts.ini deploy.yml --syntax-check
```

!!Épinglez les versions d'ansible-core et d'ansible-lint dans la CI : une nouvelle règle de lint ne doit pas casser toutes les PR un matin!!

## Terraform crée, Ansible configure

Les deux outils se complètent :

- **Terraform** gère le cycle de vie de l'infrastructure : réseaux, machines, bases managées, DNS.
- **Ansible** configure l'intérieur des machines : paquets, fichiers, services, déploiements applicatifs.

Le pont entre les deux est l'inventaire. Terraform expose les adresses en output ; on en génère l'inventaire :

```bash
terraform output -json web_ips | jq -r '.[]' | sed '1i [web]' > inventories/prod/hosts.ini
```

Ou mieux, un inventaire **dynamique** : le plugin `amazon.aws.aws_ec2` (ou `google.cloud.gcp_compute`) interroge le cloud et range les machines en groupes selon leurs étiquettes, sans fichier à régénérer.

```yaml
# inventories/prod/aws_ec2.yml
plugin: amazon.aws.aws_ec2
regions: [eu-west-3]
keyed_groups:
  - key: tags.role
    prefix: role
```

Et les conteneurs ? Si l'application tourne sur Kubernetes, Ansible ne déploie plus l'application : il prépare les nœuds ou installe le cluster, puis Helm, Kustomize ou Argo CD prennent le relais.

## Pas à pas : un déploiement par lots

1. Dans `deploy.yml`, au niveau du play (aligné sur `hosts:`), ajoutez `serial: 1` et `max_fail_percentage: 0`.
2. Ajoutez `pre_tasks:` au niveau du play, avec une tâche `ansible.builtin.uri` vers `/api/drain/{{ inventory_hostname }}`, `method: POST` sous le module, et `delegate_to: localhost` aligné sur le module.
3. Gardez `roles:` entre `pre_tasks:` et `post_tasks:`.
4. Ajoutez `post_tasks:` avec, **dans cet ordre**, la vérification de santé (`register`, `until`, `retries`, `delay` alignés sur le module), puis la remise dans le répartiteur.
5. Créez `.github/workflows/ansible.yml` : déclencheur `pull_request`, `permissions` au niveau 0, un job avec `timeout-minutes`.
6. Dans ses étapes : checkout, `pip install` avec `ansible-core==` et `ansible-lint==` épinglés, `ansible-lint`, puis `--syntax-check`.
7. Vérifiez l'ordre et les lots : `ansible-playbook -i inventory.ini deploy.yml --list-hosts --list-tasks`.

## Labo réel

```bash
ansible-playbook -i inventory.ini deploy.yml --list-hosts
ansible-playbook -i inventory.ini deploy.yml --list-tags
ansible-playbook -i inventory.ini deploy.yml --syntax-check
pipx install ansible-lint && ansible-lint deploy.yml
```

**À retenir :** `serial` et `max_fail_percentage: 0` pour un déploiement par lots qui s'arrête au premier échec ; `pre_tasks` / `post_tasks` et `delegate_to` autour du répartiteur ; vérification de santé avec `until` ; tags ; `ansible-lint` et `--syntax-check` en CI avec versions épinglées ; Terraform pour l'infrastructure, Ansible pour la configuration, reliés par l'inventaire.
