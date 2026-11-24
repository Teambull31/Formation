# Projet fil rouge : Ansible, README et mise en vitrine

Dernière étape : configurer les serveurs hors cluster avec Ansible, puis écrire le **README** qui transforme un dépôt technique en preuve de compétence.

## Le playbook

`ansible/site.yml` sur le groupe `web` :

1. installe Docker (`ansible.builtin.apt`) ;
2. dépose un service systemd depuis un template (`owner`, `group`, `mode`) ;
3. démarre le service, et le **redémarre par un handler** quand le template change ;
4. un serveur à la fois : `serial: 1`, `max_fail_percentage: 0`.

L'inventaire vient de l'output Terraform de l'étape 4, sans aucun mot de passe : clés SSH seulement.

!!Un playbook qui redémarre tous les serveurs en même temps transforme une petite erreur en panne complète!!

## Les fichiers commentés

```ini
# Fichier : ansible/inventory.ini : les noms viennent de « terraform output web_servers »
[web]
web-1 ansible_host=10.0.1.11
web-2 ansible_host=10.0.1.12

[web:vars]
ansible_user=deploy
# aucun ansible_password : la connexion se fait par clé SSH
```

```jinja
# Fichier : ansible/templates/commandes.service.j2
# Géré par Ansible : toute modification à la main sera écrasée
[Service]
ExecStart=/usr/bin/docker run --rm --name commandes -p 127.0.0.1:8000:8000 {{ image }}
Restart=always
```

```yaml
# Fichier : ansible/site.yml
- name: Serveurs web
  hosts: web
  become: true
  serial: 1                              # clés du PLAY : un serveur à la fois…
  max_fail_percentage: 0                 # …et arrêt au premier échec
  vars:
    image: "ghcr.io/moncompte/commandes:3f2a9c1"   # le même SHA qu'à l'étape 3
  tasks:
    - name: Installer Docker
      ansible.builtin.apt:
        name: docker.io
        state: present
        update_cache: true

    - name: Déposer le service commandes
      ansible.builtin.template:
        src: templates/commandes.service.j2
        dest: /etc/systemd/system/commandes.service
        owner: root
        group: root
        mode: "0644"
      notify: Redémarrer commandes       # mot-clé de tâche : aligné sur le module

    - name: Démarrer commandes
      ansible.builtin.systemd_service:
        name: commandes
        state: started
        enabled: true
        daemon_reload: true              # systemd relit les fichiers .service

  handlers:                              # clé du PLAY : alignée sur tasks
    - name: Redémarrer commandes         # le nom exact cité par notify
      ansible.builtin.systemd_service:
        name: commandes
        state: restarted
        daemon_reload: true
```

Pourquoi `state: started` dans une tâche **et** `state: restarted` dans un handler ? La tâche garantit que le service tourne, à chaque passage, sans le couper (`ok` s'il tourne déjà). Le handler ne le redémarre que si le fichier `.service` a changé. Au second lancement, le récapitulatif doit afficher `changed=0`.

## Le squelette du README

```markdown
# Commandes : de l'application à la production

Une phrase : ce que fait le projet et ce qu'il démontre.

## Architecture
- `app/` : l'API et ses tests.
- `.github/workflows/ci.yml` : tests sur chaque PR, image publiée depuis main.
- `Dockerfile`, `k8s/`, `infra/`, `ansible/` : une ligne chacun.

## Démarrer en local
    pip install -r requirements.txt && pytest -q

## Déployer
1. Fusion dans main : la CI publie l'image.
2. `kubectl apply -k k8s/`
3. `terraform -chdir=infra plan` puis `apply`
4. `ansible-playbook -i ansible/inventory.ini ansible/site.yml`
```

Dans le vrai README, les commandes de « Démarrer en local » vont dans un bloc de code délimité par trois accents graves, avec `bash` après les premiers.

## Pas à pas : l'étape 5

1. Lancez `terraform -chdir=infra output web_servers` et recopiez les noms dans `ansible/inventory.ini`, sous `[web]`, avec leurs adresses.
2. Créez `ansible/templates/commandes.service.j2` avec l'en-tête « Géré par Ansible ».
3. Écrivez `ansible/site.yml` : les clés du play, puis les trois tâches, puis `handlers:` aligné sur `tasks:`.
4. Vérifiez : `ansible-playbook -i ansible/inventory.ini ansible/site.yml --syntax-check`.
5. Écrivez `README.md` à la racine avec les trois sections, et ajoutez le badge de la CI (onglet Actions, menu « … », **Create status badge**).
6. Poussez, vérifiez que la CI est verte, puis épinglez le dépôt sur votre profil GitHub.

## Le README

Un recruteur passe deux minutes sur votre dépôt. Le README doit répondre à trois questions :

- **Architecture** : qu'y a-t-il dans chaque dossier, et comment les briques se relient ;
- **Démarrer** : les commandes pour lancer les tests et l'application en local ;
- **Déployer** : les étapes réelles, dans l'ordre.

Ajoutez un schéma simple (texte ou image) et le badge de la CI.

!!Un README qui promet ce que le dépôt ne fait pas se voit en trente secondes : décrivez seulement ce qui marche!!

## Le présenter en entretien

Racontez le projet en quatre temps : le problème, l'architecture, **un choix difficile** (par exemple : pourquoi une étiquette par SHA, pourquoi `serial: 1`), et ce que vous feriez ensuite (monitoring, Argo CD, vrai cloud). Les questions d'entretien DevOps de l'application vous y entraînent.

!!Ne montrez jamais un dépôt dont l'historique contient un secret, même supprimé depuis : réécrivez l'historique et changez le secret!!

## Labo réel

```bash
ansible-playbook -i ansible/inventory.ini ansible/site.yml --syntax-check
ansible-playbook -i ansible/inventory.ini ansible/site.yml --check --diff
git add . && git commit -m "feat: configuration ansible et readme" && git push
gh repo edit --description "API livrée de bout en bout : CI, Docker, Kubernetes, Terraform, Ansible"
```

**À retenir :** un playbook idempotent, par lots, avec handler ; un inventaire sans mot de passe nourri par Terraform ; un README Architecture, Démarrer, Déployer ; un projet qu'on sait raconter.
