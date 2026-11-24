# Idempotence, handlers et variables

Un bon playbook se relance sans crainte : la deuxième fois, il ne change rien et le dit. Cette leçon montre comment l'obtenir, comment ne redémarrer un service que s'il le faut, et où ranger les variables.

## Le playbook d'arrivée

Lisez-le d'abord en entier. Chaque section de la leçon explique ensuite un bloc et sa place.

```yaml
# Fichier : site.yml
- name: Serveurs web
  hosts: web
  become: true
  # pas de « vars: nginx_port » ici : la valeur vit dans group_vars/web.yml
  tasks:
    - name: Lire la version de nginx
      ansible.builtin.command: nginx -v
      register: nginx_version           # ← mot-clé de TÂCHE : aligné sur le module
      changed_when: false               # ← idem : une lecture ne change rien

    - name: Déposer la configuration
      ansible.builtin.copy:
        dest: /etc/nginx/conf.d/app.conf
        content: |                      # « | » : texte sur plusieurs lignes, sauts conservés
          server {
            listen {{ nginx_port }};
          }
        owner: root
        group: root
        mode: "0644"                    # guillemets : sinon YAML lit un nombre octal
      notify: Recharger nginx           # ← mot-clé de TÂCHE, aligné sur ansible.builtin.copy

  handlers:                             # ← clé du PLAY : alignée sur tasks, pas dedans
    - name: Recharger nginx             # ← le nom exact cité par notify
      ansible.builtin.service:
        name: nginx
        state: reloaded
```

```yaml
# Fichier : group_vars/web.yml : lu automatiquement pour les hôtes du groupe web
nginx_port: 8080
```

## Idempotence : ok ou changed

Chaque tâche rapporte `ok` (rien à faire) ou `changed` (elle a modifié quelque chose). Les modules comparent l'état voulu et l'état réel avant d'agir. Les modules `command` et `shell`, eux, ne savent pas : ils exécutent toujours et répondent `changed`.

Quand on n'a pas le choix d'une commande, on lui dit comment reconnaître le travail déjà fait :

```yaml
    - name: Initialiser la base
      ansible.builtin.command: /opt/app/bin/init-db
      args:                                  # paramètres annexes de command
        creates: /var/lib/app/.initialised   # si ce fichier existe : tâche sautée
    - name: Lire la version
      ansible.builtin.command: /opt/app/bin/app --version
      register: app_version
      changed_when: false
```

`creates` saute la commande si le fichier existe. `changed_when: false` déclare qu'une commande de lecture ne change rien.

## La règle d'or de l'indentation : tâche ou module ?

Dans une tâche, il y a deux sortes de clés, et elles ne vont pas au même niveau :

| Sorte | Exemples | Où |
| --- | --- | --- |
| Mots-clés de **tâche** | `name`, `register`, `changed_when`, `notify`, `when`, `loop`, `become`, `tags` | alignés sur le module |
| Paramètres du **module** | `dest`, `owner`, `mode`, `state`, `name` (du paquet) | indentés sous le module |

Les mots-clés de tâche sont valables pour **n'importe quel** module ; les paramètres dépendent du module choisi.

```yaml
# FAUX : notify est sous copy, Ansible le prend pour un paramètre de copy
      ansible.builtin.copy:
        dest: /etc/nginx/conf.d/app.conf
        notify: Recharger nginx       # ✗ « Unsupported parameters for copy: notify »

# JUSTE : notify est un mot-clé de tâche
      ansible.builtin.copy:
        dest: /etc/nginx/conf.d/app.conf
      notify: Recharger nginx
```

!!Un playbook qui affiche changed à chaque lancement ne permet plus de voir le vrai changement le jour où il arrive!!

## Les handlers : redémarrer seulement si besoin

Redémarrer nginx à chaque lancement coupe le service pour rien. Un **handler** est une tâche qui ne s'exécute que si une autre tâche la **notifie** et a été `changed`.

- Le texte de `notify` doit être **exactement** le `name` du handler.
- La section `handlers:` est une clé du **play**, au même niveau que `tasks:` et `hosts:`. Placée sous `tasks:`, elle serait lue comme une tâche invalide.
- Les handlers tournent une seule fois, **à la fin du play**, même s'ils ont été notifiés dix fois.
- `reloaded` relit la configuration sans couper les connexions ; `restarted` coupe tout.

!!Une faute de frappe dans notify fait échouer le play : le nom doit être identique, majuscules comprises!!

## Les variables

On les lit avec la syntaxe Jinja2 `"{{ nginx_port }}"`. Toujours entre guillemets quand la valeur commence par `{{`, sinon le YAML est invalide : YAML croit qu'une accolade ouvre un dictionnaire.

```yaml
# FAUX : la valeur commence par une accolade, YAML refuse
        port: {{ nginx_port }}
# JUSTE
        port: "{{ nginx_port }}"
# JUSTE aussi : la valeur ne commence pas par l'accolade
        line: listen {{ nginx_port }};
```

Où les définir, du plus général au plus précis :

- `group_vars/all.yml` : pour tous les hôtes ;
- `group_vars/web.yml` (ou `group_vars/web/`) : pour le groupe `web` ;
- `host_vars/web1.yml` : pour un hôte ;
- `vars:` dans le play ;
- `-e nginx_port=9090` en ligne de commande : priorité maximale.

Les fichiers `group_vars/` et `host_vars/` sont lus automatiquement s'ils sont à côté de l'inventaire ou du playbook. C'est l'endroit normal : le playbook reste générique, les valeurs vivent par groupe.

```
projet/
├── inventory.ini
├── site.yml
└── group_vars/
    └── web.yml        ← le nom du fichier = le nom du groupe dans l'inventaire
```

!!Une variable définie à la fois dans group_vars et en -e prend la valeur de -e : en cas de surprise, cherchez d'abord la ligne de commande!!

## Les facts

Au début de chaque play, Ansible collecte des **facts** sur l'hôte : `ansible_distribution`, `ansible_os_family`, `ansible_default_ipv4.address`, la mémoire, les disques. Ils s'utilisent comme des variables. `gather_facts: false` accélère un play qui n'en a pas besoin.

## Permissions des fichiers

Indiquez toujours `owner`, `group` et `mode` (entre guillemets : `"0644"`) sur `copy`, `template` et `file`. Sans eux, les droits dépendent de l'umask de la machine, et un fichier de configuration peut devenir lisible par tous.

## Pas à pas : rendre le playbook idempotent

1. Créez `group_vars/web.yml` avec `nginx_port: 8080`, et supprimez le bloc `vars:` du play.
2. Remplacez la tâche `shell: echo ... > fichier` par `ansible.builtin.copy:` avec `dest`, `content: |` et le texte, puis `owner`, `group`, `mode: "0644"` sous le module.
3. Ajoutez `notify: Recharger nginx` aligné sur `ansible.builtin.copy:`.
4. Supprimez la tâche qui fait `state: restarted`.
5. Au niveau du play, aligné sur `tasks:`, ajoutez `handlers:` avec le handler `Recharger nginx` en `state: reloaded`.
6. Sur la tâche `nginx -v`, ajoutez `changed_when: false` aligné sur le module.
7. Lancez deux fois `ansible-playbook -i inventory.ini site.yml --check --diff` : la seconde fois, le récapitulatif doit montrer `changed=0`.

## Labo réel

```bash
ansible-playbook -i inventory.ini site.yml --check --diff   # ce qui changerait
ansible-inventory -i inventory.ini --host web1               # variables vues par web1
ansible localhost -c local -m ansible.builtin.debug -a "var=ansible_os_family"
```

**À retenir :** `ok` contre `changed` ; `creates` et `changed_when` pour les commandes ; mots-clés de tâche alignés sur le module, paramètres sous le module ; `notify` vers un handler au nom identique, `handlers:` au niveau du play ; `reloaded` plutôt que `restarted` ; variables dans `group_vars/` et `host_vars/`, `-e` gagne toujours ; `"{{ }}"` entre guillemets ; `owner`, `group`, `mode` sur chaque fichier.
