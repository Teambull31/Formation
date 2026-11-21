# Idempotence, handlers et variables

Un bon playbook se relance sans crainte : la deuxième fois, il ne change rien et le dit. Cette leçon montre comment l'obtenir, comment ne redémarrer un service que s'il le faut, et où ranger les variables.

## Idempotence : ok ou changed

Chaque tâche rapporte `ok` (rien à faire) ou `changed` (elle a modifié quelque chose). Les modules comparent l'état voulu et l'état réel avant d'agir. Les modules `command` et `shell`, eux, ne savent pas : ils exécutent toujours et répondent `changed`.

Quand on n'a pas le choix d'une commande, on lui dit comment reconnaître le travail déjà fait :

```yaml
    - name: Initialiser la base
      ansible.builtin.command: /opt/app/bin/init-db
      args:
        creates: /var/lib/app/.initialised
    - name: Lire la version
      ansible.builtin.command: /opt/app/bin/app --version
      register: app_version
      changed_when: false
```

`creates` saute la commande si le fichier existe. `changed_when: false` déclare qu'une commande de lecture ne change rien.

!!Un playbook qui affiche changed à chaque lancement ne permet plus de voir le vrai changement le jour où il arrive!!

## Les handlers : redémarrer seulement si besoin

Redémarrer nginx à chaque lancement coupe le service pour rien. Un **handler** est une tâche qui ne s'exécute que si une autre tâche la **notifie** et a été `changed` :

```yaml
  tasks:
    - name: Déposer la configuration
      ansible.builtin.copy:
        src: files/nginx.conf
        dest: /etc/nginx/nginx.conf
        owner: root
        group: root
        mode: "0644"
      notify: Recharger nginx
  handlers:
    - name: Recharger nginx
      ansible.builtin.service:
        name: nginx
        state: reloaded
```

- Le texte de `notify` doit être **exactement** le `name` du handler.
- Les handlers tournent une seule fois, **à la fin du play**, même s'ils ont été notifiés dix fois.
- `reloaded` relit la configuration sans couper les connexions ; `restarted` coupe tout.

!!Une faute de frappe dans notify fait échouer le play : le nom doit être identique, majuscules comprises!!

## Les variables

On les lit avec la syntaxe Jinja2 `"{{ nginx_port }}"`. Toujours entre guillemets quand la valeur commence par `{{`, sinon le YAML est invalide.

Où les définir, du plus général au plus précis :

- `group_vars/all.yml` : pour tous les hôtes ;
- `group_vars/web.yml` (ou `group_vars/web/`) : pour le groupe `web` ;
- `host_vars/web1.yml` : pour un hôte ;
- `vars:` dans le play ;
- `-e nginx_port=9090` en ligne de commande : priorité maximale.

Les fichiers `group_vars/` et `host_vars/` sont lus automatiquement s'ils sont à côté de l'inventaire ou du playbook. C'est l'endroit normal : le playbook reste générique, les valeurs vivent par groupe.

!!Une variable définie à la fois dans group_vars et en -e prend la valeur de -e : en cas de surprise, cherchez d'abord la ligne de commande!!

## Les facts

Au début de chaque play, Ansible collecte des **facts** sur l'hôte : `ansible_distribution`, `ansible_os_family`, `ansible_default_ipv4.address`, la mémoire, les disques. Ils s'utilisent comme des variables. `gather_facts: false` accélère un play qui n'en a pas besoin.

## Permissions des fichiers

Indiquez toujours `owner`, `group` et `mode` (entre guillemets : `"0644"`) sur `copy`, `template` et `file`. Sans eux, les droits dépendent de l'umask de la machine, et un fichier de configuration peut devenir lisible par tous.

## Labo réel

```bash
ansible-playbook -i inventory.ini site.yml --check --diff   # ce qui changerait
ansible-inventory -i inventory.ini --host web1               # variables vues par web1
ansible localhost -c local -m ansible.builtin.debug -a "var=ansible_os_family"
```

**À retenir :** `ok` contre `changed` ; `creates` et `changed_when` pour les commandes ; `notify` vers un handler au nom identique, exécuté une fois en fin de play ; `reloaded` plutôt que `restarted` ; variables dans `group_vars/` et `host_vars/`, `-e` gagne toujours ; `"{{ }}"` entre guillemets ; `owner`, `group`, `mode` sur chaque fichier.
