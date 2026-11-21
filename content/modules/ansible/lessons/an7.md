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
