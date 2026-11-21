# Projet fil rouge : l'infrastructure en Terraform

Le cluster et les serveurs ne tombent pas du ciel. L'étape 4 les décrit dans **infra/**, avec les règles vues dans le module Terraform : versions épinglées, state distant, entrées validées, aucun secret.

## La structure

```
infra/
  main.tf        # terraform, providers, backend, ressources
  variables.tf   # environment validé
  outputs.tf     # ce que la suite lira
```

Pour s'entraîner gratuitement, le provider `local` suffit : il crée des fichiers à la place des serveurs. Le jour où vous passez sur un vrai cloud, seule la ressource change, la structure reste.

## Les règles du projet

- `required_version` et chaque provider avec une contrainte `~> X.Y`.
- Un **backend distant** chiffré et verrouillé (`encrypt`, `use_lockfile`), sans aucune clé.
- `variable "environment"` avec une `validation`.
- Des ressources en `for_each`, pas en `count`.
- Un `output` qui expose les serveurs : c'est le **contrat** avec Ansible.

!!Une clé d'accès dans le bloc backend finit dans Git et dans le state : les identifiants viennent de l'environnement ou d'OIDC!!

## Le .gitignore

À la racine du projet : `.terraform/`, `*.tfstate`, `*.tfstate.*`. Le fichier `.terraform.lock.hcl`, lui, **reste versionné** : il fige les versions des providers.

!!Un *.hcl dans le .gitignore cache aussi le fichier de verrouillage : chacun téléchargera alors une version différente du provider!!

## Brancher la CI

Le module Terraform a montré le workflow : `terraform plan` sur la pull request, `apply` après fusion avec un environnement protégé. Ajoutez-le au projet quand vous aurez un vrai backend.

!!Un apply déclenché par une pull request exécute le code d'un contributeur non relu sur votre infrastructure!!

## Labo réel

```bash
terraform -chdir=infra init -backend=false
terraform -chdir=infra validate
terraform -chdir=infra plan -var environment=dev
terraform -chdir=infra output -json web_servers
```

**À retenir :** versions épinglées ; backend distant chiffré, verrouillé et sans clé ; `environment` validé ; `for_each` ; un output comme contrat avec Ansible ; state hors Git, lock dans Git.
