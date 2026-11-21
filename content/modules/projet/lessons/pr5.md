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
