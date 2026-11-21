# Fiche de révision : Ansible

## Vocabulaire

- **Nœud de contrôle** (où l'on lance), **hôtes gérés** (en SSH, Python requis, aucun agent).
- **Inventaire** : hôtes rangés en groupes. **Play** : des hôtes + des tâches. **Playbook** : liste de plays.
- **Module** : action idempotente (`ansible.builtin.apt`, `copy`, `template`, `service`, `user`, `file`, `uri`).
- **Rôle** : un composant réutilisable. **Collection** : un paquet de modules et rôles (`community.general`).
- **Facts** : informations collectées sur l'hôte (`ansible_os_family`, `ansible_default_ipv4`).

## Commandes

```bash
ansible-inventory -i inventory.ini --graph
ansible all -i inventory.ini -m ansible.builtin.ping
ansible web -i inventory.ini -b -m ansible.builtin.apt -a "name=htop state=present"
ansible-playbook -i inventory.ini site.yml --syntax-check
ansible-playbook -i inventory.ini site.yml --check --diff
ansible-playbook -i inventory.ini site.yml --limit web1 --tags config
ansible-playbook site.yml --list-hosts --list-tasks --list-tags
ansible-galaxy role init roles/nginx
ansible-galaxy install -r requirements.yml
ansible-vault encrypt|view|edit|rekey fichier.yml
ansible localhost -c local -m ansible.builtin.setup
```

## Inventaire INI

```ini
[web]
web1 ansible_host=10.0.1.11
[db]
db1 ansible_host=10.0.2.21
[prod:children]
web
db
[all:vars]
ansible_user=deploy
```

- !!Jamais ansible_password dans l'inventaire : clés SSH!!
- Inventaire dynamique : plugin `amazon.aws.aws_ec2`, groupes par étiquette.

## Playbook type

```yaml
- name: Serveurs web
  hosts: web
  become: true
  serial: "25%"
  max_fail_percentage: 0
  roles:
    - role: nginx
  tasks:
    - name: Déposer la configuration
      ansible.builtin.template:
        src: app.conf.j2
        dest: /etc/app/app.conf
        owner: root
        group: root
        mode: "0644"
        validate: app --check %s
      notify: Recharger app
  handlers:
    - name: Recharger app
      ansible.builtin.service:
        name: app
        state: reloaded
```

## Idempotence

- `state:` plutôt que `shell` : la tâche répond `ok` si rien à faire.
- Commandes : `creates:` / `removes:`, ou `changed_when: false` pour une lecture.
- Deuxième lancement : `changed=0` partout.
- Handlers : notifiés par une tâche `changed`, exécutés **une fois en fin de play**, nom identique au `notify`.
- `owner`, `group`, `mode: "0644"` (entre guillemets) sur chaque fichier.

## Variables et priorités (de faible à forte)

- `roles/x/defaults/main.yml` (réglages surchargeables)
- `group_vars/all.yml`, puis `group_vars/<groupe>.yml`, puis `host_vars/<hôte>.yml`
- `vars:` du play, `roles/x/vars/main.yml`
- `-e` en ligne de commande : gagne toujours
- `"{{ var }}"` entre guillemets quand la valeur commence par des accolades.

## Jinja2, boucles, conditions

- `{{ x | default(2) }}`, `{% for s in sites %}...{% endfor %}`, `{% if %}...{% endif %}`.
- `loop: "{{ liste }}"` et `item` ; une liste passée directement à `apt` plutôt qu'une boucle.
- `when: ansible_os_family == "Debian"` **sans accolades**.
- `register:` puis `until:`, `retries:`, `delay:` pour attendre.
- `validate: ... %s` sur `template` et `copy`.

## Rôles

```
roles/nginx/{tasks,handlers,defaults,vars,templates,files,meta}/
```

- `tasks/main.yml` = point d'entrée ; `templates/` cherché automatiquement.
- Variables préfixées (`nginx_port`). Réglages dans `defaults`, constantes dans `vars`.
- `import_role` (statique) / `include_role` (dynamique).
- `requirements.yml` avec `version:` pour chaque collection et rôle.
- Tests : `ansible-lint`, Molecule (idempotence vérifiée).

## Sécurité

- Vault : en-tête `$ANSIBLE_VAULT;1.1;AES256` ; motif `vars.yml` (`db_password: "{{ vault_db_password }}"`) + `vault.yml` chiffré.
- Mot de passe du coffre hors dépôt (`--vault-password-file ~/.vault_pass`, `chmod 600`), ou secret de la CI.
- `no_log: true` sur toute tâche qui manipule un secret.
- `host_key_checking` activé ; `become` au plus près, `become_user` pour un compte précis.
- !!Un secret affiché par -v ou par une erreur finit dans les journaux de la CI!!

## Déploiement progressif

- `serial: 1` / `"25%"` / `[1, 5, "50%"]` et `max_fail_percentage: 0`.
- `pre_tasks` : sortir du répartiteur (`delegate_to: localhost`) ; `post_tasks` : santé (`uri` + `until`) **puis** remise en service.
- `run_once: true` pour une migration de base unique.

## Dépannage

- `UNREACHABLE` : SSH (clé, utilisateur, `ansible_host`, pare-feu). Tester : `ssh -l deploy 10.0.1.11`.
- `Missing sudo password` : `--ask-become-pass` ou sudo sans mot de passe pour l'utilisateur de déploiement.
- `The task includes an option with an undefined variable` : variable absente des group_vars ou des defaults.
- `couldn't resolve module/action` : collection non installée, `ansible-galaxy install -r requirements.yml`.
- Plus de détails : `-vvv` (attention aux secrets sans `no_log`).
- Voir les variables d'un hôte : `ansible-inventory -i inventory.ini --host web1`.

## Questions d'entretien

- Pourquoi Ansible est-il dit « sans agent » et idempotent ?
- Handler ou tâche `state: restarted` : différence ?
- defaults ou vars dans un rôle ?
- Comment protéger un mot de passe de base dans un projet Ansible ?
- Comment mettre à jour 50 serveurs sans coupure ?
- Terraform ou Ansible : qui fait quoi ?
