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

## Les fichiers commentés

```hcl
# Fichier : infra/main.tf
terraform {
  required_version = ">= 1.6"

  required_providers {
    local = {                          # argument (avec « = ») : nom choisi par vous
      source  = "hashicorp/local"
      version = "~> 2.5"
    }
  }

  backend "s3" {                       # DANS le bloc terraform : lu par init, avant les variables
    bucket       = "moncompte-tfstate"
    key          = "commandes/prod.tfstate"   # un chemin par projet et par environnement
    region       = "eu-west-3"
    encrypt      = true
    use_lockfile = true
    # aucune access_key : les identifiants viennent de l'environnement
  }
}

locals {
  servers = toset(["web-1", "web-2"])  # set : for_each l'exige, et chaque nom est une clé stable
}

resource "local_file" "server" {
  for_each = local.servers             # méta-argument : en premier

  filename = "${path.module}/out/${each.key}.ini"
  content  = "env=${var.environment}\n"
}
```

```hcl
# Fichier : infra/variables.tf
variable "environment" {
  type        = string
  description = "Environnement visé : dev, staging ou prod."

  validation {                         # bloc imbriqué : pas de « = »
    condition     = contains(["dev", "staging", "prod"], var.environment)
    error_message = "environment doit valoir dev, staging ou prod."
  }
}
```

```hcl
# Fichier : infra/outputs.tf
output "web_servers" {
  description = "Noms des serveurs web, lus pour générer l'inventaire Ansible."
  value       = sort(keys(local_file.server))   # ["web-1", "web-2"] : le contrat avec l'étape 5
}
```

`keys(local_file.server)` renvoie les clés du `for_each`, et `sort()` fixe leur ordre : l'inventaire Ansible généré sera identique d'un lancement à l'autre.

## Pas à pas : l'étape 4

1. Créez `infra/` et écrivez `main.tf` : le bloc `terraform` avec `required_providers` et `backend "s3"`, puis `locals` et la ressource en `for_each`.
2. Écrivez `variables.tf` avec le bloc `validation`.
3. Écrivez `outputs.tf` avec `web_servers`.
4. À la racine du dépôt, complétez `.gitignore` (voir ci-dessous).
5. Sans bucket réel, initialisez sans backend : `terraform -chdir=infra init -backend=false`, puis `validate`.
6. Testez la validation : `terraform -chdir=infra plan -var environment=qa` doit afficher votre message d'erreur.
7. `terraform -chdir=infra fmt` avant de commiter.

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
