# Modules réutilisables et state distant

Un **module** est un dossier de fichiers `.tf`. Le dossier où vous lancez `terraform` est le module racine ; il appelle d'autres modules comme on appelle des fonctions. En équipe, le state ne peut plus vivre sur le portable de quelqu'un : il part dans un **backend distant** verrouillé.

## Structure d'un module

```
modules/app/
  main.tf        ressources
  variables.tf   entrées (le contrat)
  outputs.tf     sorties (le contrat)
main.tf          module racine : appelle modules/app
```

```hcl
module "web" {
  source      = "./modules/app"
  app_name    = "web"
  environment = var.environment
}

output "web_config" {
  value = module.web.config_path
}
```

La correspondance entre l'appel et le module se lit ligne à ligne :

```
main.tf (racine)                     modules/app/variables.tf
module "web" {
  source      = "./modules/app"  ──► (méta-argument : où est le module, pas une variable)
  app_name    = "web"            ──► variable "app_name"    { default = "demo" }
  environment = var.environment  ──► variable "environment" { pas de default : obligatoire }
}                                     
                                      modules/app/outputs.tf
module.web.config_path           ◄── output "config_path" { value = local_file.config.filename }
```

À gauche du `=`, le nom d'une variable **du module** ; à droite, une valeur **de l'appelant** (ici `var.environment`, la variable de la racine). Un argument qui ne correspond à aucune variable du module (`replicas = 3` alors que le module ne déclare pas `replicas`) donne `Unsupported argument`.

Chaque argument du bloc `module` est une **variable** du module appelé. Une variable sans `default` est obligatoire : l'oublier fait échouer `plan`. On lit une sortie avec `module.<nom>.<output>` : seul ce que le module déclare dans `outputs.tf` est visible.

!!Un module ne voit pas les variables du module racine : tout ce qu'il utilise doit lui être passé explicitement!!

## Les sources de modules

- Local : `source = "./modules/app"`, versionné avec le dépôt.
- Registre : `source = "terraform-aws-modules/vpc/aws"` avec **`version = "~> 5.8"`**.
- Git : `source = "git::https://git.example.test/infra/modules.git//app?ref=v1.3.0"`.

!!Un module du registre sans version, ou un module Git sans ?ref=, change sous vos pieds à chaque terraform init!!

Après avoir ajouté ou modifié un `source`, relancez `terraform init` : il télécharge les modules dans `.terraform/modules`.

## Bien découper

- Un module = une responsabilité (un réseau, une application, une base).
- Entrées typées et décrites, sorties minimales : le module est une boîte noire.
- Pas de bloc `provider` dans un module réutilisable : c'est l'appelant qui le configure.
- Évitez les modules qui n'enveloppent qu'une seule ressource : ils ajoutent une couche sans rien cacher.

## Le state distant

Le state local pose trois problèmes en équipe : il n'est pas partagé, deux `apply` simultanés le corrompent, et il contient des secrets sur un disque de portable. Le backend distant les règle :

```hcl
terraform {
  backend "s3" {
    bucket       = "acme-tfstate"
    key          = "web/prod.tfstate"
    region       = "eu-west-3"
    encrypt      = true
    use_lockfile = true
  }
}
```

Le bloc `backend` vit **à l'intérieur** du bloc `terraform`, à côté de `required_providers`, jamais au niveau 0 : c'est un réglage de Terraform lui-même, pas une ressource. Il ne peut pas lire de variable (`var.` y est interdit), car il est lu par `terraform init`, avant que les variables existent. Les valeurs y sont donc écrites en dur, ou passées par `terraform init -backend-config=prod.hcl`.

```hcl
# FAUX : identifiants dans le code, pas de verrou, une seule clé pour tout
terraform {
  backend "s3" {
    bucket     = "acme-tfstate"
    key        = "terraform.tfstate"
    region     = "eu-west-3"
    access_key = "AKIA..."           # ✗
    secret_key = "wJalr..."          # ✗
  }
}
```

- `encrypt = true` : chiffrement côté stockage.
- `use_lockfile = true` (Terraform 1.10 et plus ; avant : `dynamodb_table`) : un **verrou** empêche deux `apply` en même temps.
- Une `key` par composant et par environnement : un incident sur le state de dev ne touche pas la prod.
- Le bucket a le versionnage activé : on peut restaurer un state abîmé.

!!Jamais de access_key ni de secret_key dans un bloc backend : les identifiants viennent de l'environnement ou d'OIDC!!

Autres backends : `gcs`, `azurerm`, `http`, ou HCP Terraform (`cloud {}`). Changer de backend se fait avec `terraform init -migrate-state`.

## Workspaces ou dossiers ?

`terraform workspace new prod` crée un second state pour la même configuration. C'est pratique pour des copies identiques et temporaires. Pour dev et prod, qui diffèrent en taille, en droits et en compte cloud, préférez **un dossier par environnement** (`envs/dev`, `envs/prod`) qui appelle les mêmes modules : on voit les différences dans le code.

## Lire l'infrastructure des autres

- `data "aws_vpc" "main" { tags = { Name = "main" } }` : lire un objet existant sans le gérer.
- `terraform_remote_state` lit les outputs d'un autre state ; il expose tout ce state, préférez une `data` source ou un paramètre partagé.

## Pas à pas : réparer l'appel de module et le backend

1. Ouvrez `modules/app/variables.tf` et notez les noms de variables, et lesquelles n'ont pas de `default`. C'est la liste exacte des arguments acceptés.
2. Dans `modules/app/outputs.tf`, ajoutez `output "config_path"` avec `value = local_file.config.filename`.
3. Dans `main.tf`, bloc `module "web"` : retirez tout argument absent du module, et ajoutez `environment = var.environment`.
4. Dans le bloc `module "naming"`, ajoutez `?ref=v1.2.0` à la fin de l'URL `source`, après le `//sous-dossier`.
5. Dans `terraform { backend "s3" { } }`, supprimez `access_key` et `secret_key`, ajoutez `encrypt = true` et `use_lockfile = true`, et une `key` comme `web/prod.tfstate`.
6. Dans `outputs.tf` de la racine, faites lire à `web_config` la sortie `module.web.config_path`.
7. Lancez `terraform fmt -recursive` pour aligner tous les fichiers, sous-dossiers compris.

## Labo réel

Le bucket et le dépôt Git du TP sont fictifs. Pour un essai réel sur votre poste, copiez le dossier, retirez le bloc `backend` et le module `naming`, puis :

```bash
terraform init
terraform plan -var environment=dev
terraform apply -var environment=dev
terraform state list          # module.web.local_file.config
terraform output web_config
```

**À retenir :** un module = un dossier avec un contrat (variables, outputs) ; tout est passé explicitement ; `module.<nom>.<output>` ; versions épinglées (registre `version`, Git `?ref=`) ; `terraform init` après chaque changement de source ; backend distant chiffré, verrouillé, une clé par environnement, sans identifiants dans le code.
