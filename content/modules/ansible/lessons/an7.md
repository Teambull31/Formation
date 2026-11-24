# Répare la panne : le parc qui dérape

Ansible parle beaucoup : `ok`, `changed`, `failed`, `unreachable`, des avertissements jaunes. Savoir **lire le récapitulatif** suffit à localiser la plupart des pannes. Le TP vous met devant cinq pannes à la fois.

## Lire un PLAY RECAP

```text
web1 : ok=12  changed=1  unreachable=0  failed=0  skipped=2  rescued=0  ignored=0
db1  : ok=0   changed=0  unreachable=1  failed=0
```

- `unreachable` : Ansible n'a même pas pu se connecter. Le problème est **SSH**, pas le playbook.
- `failed` : la tâche a tourné et échoué. Lire le message `msg` de la tâche.
- `changed` au deuxième passage sans modification : une tâche **non idempotente**.

!!Un changed qui revient à chaque passage n'est pas anodin : il cache un fichier qui grossit ou un service redémarré pour rien!!

## Les familles de pannes

| Symptôme | Famille | Correction |
|---|---|---|
| `changed` à chaque passage | idempotence | un module à état (`copy`, `lineinfile`, `template`) |
| handler « not found », service pas rechargé | handler | `notify` identique au `name` (ou `listen`) |
| `UNREACHABLE`, `No route to host` | inventaire | `ansible_host`, utilisateur, clé |
| avertissement sur les accolades dans `when` | condition | expression sans `{{ }}` |
| secret lisible dans un journal | fuite | `no_log: true`, puis changer le secret |

## Chaque panne, avec sa correction en place

### Idempotence : un fichier qui grossit

```yaml
# FAUX : ajoute la ligne à chaque passage
    - name: Activer la compression
      ansible.builtin.shell: echo "gzip on;" >> /etc/nginx/conf.d/gzip.conf

# JUSTE : décrit l'état voulu ; la ligne est ajoutée une fois, puis « ok »
    - name: Activer la compression
      ansible.builtin.lineinfile:
        path: /etc/nginx/conf.d/gzip.conf
        line: "gzip on;"
        create: true
        owner: root
        group: root
        mode: "0644"
      notify: Recharger nginx
```

### Handler : le nom ne correspond pas

```yaml
  tasks:
    - name: Déposer le site
      ansible.builtin.template:
        src: site.conf.j2
        dest: /etc/nginx/conf.d/site.conf
      notify: Recharger nginx          # ← texte cité…
  handlers:
    - name: Recharger nginx            # ← …identique ici, majuscules comprises
      ansible.builtin.service:
        name: nginx
        state: reloaded
```

### Inventaire : l'adresse est fausse

```ini
[db]
db1 ansible_host=10.0.2.21   # ← l'adresse réelle, sur la même ligne que le nom de l'hôte
```

### Condition : des accolades qui cassent tout

```yaml
# FAUX : les accolades produisent un texte « Debian == 'Debian' » ou « RedHat == 'Debian' »
#        au lieu d'un booléen : la condition ne fait pas ce qu'on croit
      when: "{{ ansible_os_family }} == 'Debian'"

# JUSTE : une expression nue ; sur Rocky, la tâche est sautée (skipped) au lieu de planter
      when: ansible_os_family == "Debian"
```

`ansible_distribution` vaut `Debian`, `Ubuntu`, `Rocky`… ; `ansible_os_family` regroupe : `Debian` pour Debian et Ubuntu, `RedHat` pour Rocky, Alma et RHEL. ufw n'existe que dans la famille Debian : sur Rocky, une tâche ufw correctement conditionnée apparaît `skipped` dans le récapitulatif, ce qui est le comportement voulu.

### Fuite : le mot de passe dans le journal

```yaml
    - name: Créer les comptes
      ansible.builtin.user:
        name: "{{ item.name }}"
        password: "{{ item.password_hash }}"
      loop: "{{ comptes }}"
      no_log: true          # ← mot-clé de tâche : masque aussi chaque item de la boucle
```

## Pas à pas : remettre le parc d'aplomb

1. Lisez `incidents/01-deuxieme-passage.txt` et les suivants. Dans chaque `PLAY RECAP`, repérez la colonne qui sort de l'ordinaire.
2. Classez chaque composant dans une famille et remplissez `diagnostic.yaml`.
3. Dans `inventory.ini`, corrigez l'`ansible_host` de db1.
4. Dans `site.yml`, remplacez la commande de compression par un module à état.
5. Alignez le texte du `notify` sur le `name` du handler, caractère pour caractère.
6. Réécrivez la condition du pare-feu sans accolades, sur `ansible_os_family`.
7. Ajoutez `no_log: true` sur la tâche des comptes, aligné sur le module.
8. Vérifiez la syntaxe : `ansible-playbook -i inventory.ini site.yml --syntax-check`.

## Les outils de diagnostic

```bash
ansible-inventory -i inventory.ini --host db1      # variables réellement utilisées
ansible db1 -i inventory.ini -m ansible.builtin.ping
ansible-playbook -i inventory.ini site.yml --check --diff
ansible-playbook -i inventory.ini site.yml --start-at-task "Ouvrir le port 443"
ansible-playbook -i inventory.ini site.yml --step
ansible-playbook -i inventory.ini site.yml -vvv    # attention aux secrets
```

`--check --diff` montre ce qui changerait sans rien toucher : c'est le `plan` d'Ansible.

!!-vvv affiche les arguments des modules : sans no_log, les mots de passe passent dans le terminal et dans les journaux!!

## Après une fuite

Ajouter `no_log` protège les prochains lancements, pas le passé. Un secret qui a été affiché est **compromis** :

1. changer le secret (et le mettre à jour dans le coffre) ;
2. restreindre ou purger le journal exposé ;
3. noter l'incident, pour que la cause ne revienne pas.

!!Masquer le secret sans le changer laisse une porte ouverte à quiconque a déjà lu le journal!!

## Labo réel

```bash
ansible-playbook -i inventory.ini site.yml --syntax-check
ansible-lint site.yml
ansible-playbook -i inventory.ini site.yml --list-tasks
```

**À retenir :** `unreachable` = SSH, `failed` = la tâche, `changed` répété = pas idempotent ; `notify` identique au handler ; l'inventaire suit la source de vérité ; `when` sans accolades ; `no_log` sur les secrets, et un secret exposé se change.
