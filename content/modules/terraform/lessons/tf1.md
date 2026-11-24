# IaC déclaratif et workflow init / plan / apply

Créer des serveurs, des dossiers ou des droits à la main, c'est lent et impossible à rejouer. Avec l'**Infrastructure as Code**, on décrit l'infrastructure dans des fichiers versionnés, comme du code. Terraform est l'outil le plus répandu pour cela.

## Déclaratif : on décrit le résultat

Terraform est **déclaratif** : vous écrivez l'état final voulu, pas les étapes pour l'atteindre. L'outil compare ce que vous demandez avec ce qui existe, puis calcule seul les actions à faire. Un script impératif dit « crée un dossier » ; Terraform dit « ce dossier doit exister », et ne fait rien s'il existe déjà.

## Le workflow en trois temps

`terraform init` prépare le dossier de travail et récupère les **providers**, les modules d'extension qui savent parler à une plateforme. `terraform plan` calcule les différences et affiche un plan, sans rien modifier. `terraform apply` exécute ensuite ce plan.

!!Lisez toujours le plan avant d'appliquer : une ligne « destroy » oubliée supprime une ressource de production!!

## La syntaxe HCL : blocs et arguments

Terraform s'écrit en **HCL**. Contrairement au YAML, ce ne sont pas les espaces qui font la structure, ce sont les **accolades**. L'indentation (2 espaces) sert seulement à la lecture, et `terraform fmt` la remet d'aplomb tout seul.

Deux formes à ne pas confondre :

```hcl
# Un BLOC : un mot-clé, des étiquettes entre guillemets, des accolades, PAS de « = »
resource "local_file" "hello" {
  # Un ARGUMENT : un nom, « = », une valeur
  filename = "hello.txt"
}
```

- Un **bloc** s'ouvre par un mot-clé (`terraform`, `resource`, `variable`…) et des accolades.
- Un **argument** s'écrit `nom = valeur`, une ligne par argument, sans virgule ni point-virgule.
- Les `=` d'arguments voisins s'alignent par convention ; `terraform fmt` le fait pour vous.

## Le fichier complet, ligne par ligne

```hcl
# Fichier : main.tf
terraform {                              # bloc de réglage de Terraform lui-même
  required_version = ">= 1.5.0"          # argument : version minimale du binaire

  required_providers {                   # bloc imbriqué : la liste des providers
    local = {                            # ← ARGUMENT « local = { } » : une map, d'où le « = »
      source  = "hashicorp/local"        # où le télécharger : éditeur/nom
      version = "~> 2.5"                 # quelle version accepter
    }
  }
}

resource "local_file" "hello" {          # bloc resource : type "local_file", nom local "hello"
  filename = "${path.module}/hello.txt"  # chemin du fichier, à côté du main.tf
  content  = "Bonjour IaC"               # ce qu'il contient
}
```

Pourquoi `local = {` prend-il un `=` alors que `required_providers {` n'en prend pas ? Parce que `required_providers` est un **bloc** prévu par Terraform, alors que `local` est un nom que **vous** choisissez, associé à une valeur (une map). Oublier ce `=` donne l'erreur `Unsupported block type`.

```hcl
# FAUX : local est traité comme un bloc
  required_providers {
    local {
      source = "hashicorp/local"
    }
  }

# JUSTE : local est un argument dont la valeur est une map
  required_providers {
    local = {
      source = "hashicorp/local"
    }
  }
```

Le bloc `terraform` se place en haut du fichier, par convention : on lit d'abord avec quoi le code fonctionne, puis ce qu'il crée. Les deux étiquettes d'une `resource` ont chacune un rôle : le **type** (`local_file`) vient du provider et ne s'invente pas ; le **nom local** (`hello`) est libre et sert à référencer la ressource ailleurs (`local_file.hello.filename`).

Ici `~> 2.5` accepte les versions 2.x à partir de 2.5, mais pas la 3.0 : on **épingle** les versions pour que le déploiement d'aujourd'hui ressemble à celui de l'an prochain.

!!Un provider sans contrainte de version peut changer de version majeure et casser votre code un lundi matin!!

## Le state, la mémoire de Terraform

Terraform note dans un fichier de **state** quel objet réel correspond à quelle ressource du code. Sans lui, il ne sait pas ce qui existe déjà. Si quelqu'un modifie un objet à la main, c'est une **dérive** : le prochain `plan` la détecte.

!!Ne modifiez jamais le fichier de state à la main : passez par les commandes terraform state!!

## Idempotence

Relancer `apply` sans changer le code ne modifie rien. Cette propriété, l'**idempotence**, rend les déploiements sûrs à répéter.

## Lire un plan

```
  # local_file.hello will be created
  + resource "local_file" "hello" {
      + content  = "Bonjour IaC"
      + filename = "./hello.txt"
    }

Plan: 1 to add, 0 to change, 0 to destroy.
```

Le symbole en début de ligne dit l'action : `+` créer, `~` modifier sur place, `-` détruire, `-/+` détruire puis recréer. La dernière ligne résume : c'est elle qu'on lit en premier.

## Pas à pas : votre première configuration

1. Créez un dossier vide et, dedans, le fichier `main.tf`.
2. Écrivez le bloc `terraform { }` avec `required_version = ">= 1.5.0"`.
3. Dans ce bloc, ajoutez `required_providers { }`, puis dedans `local = { source = "hashicorp/local", version = "~> 2.5" }` sur trois lignes, sans virgules.
4. Sous le bloc `terraform`, écrivez `resource "local_file" "hello" { }` avec `filename` et `content`.
5. Lancez `terraform fmt` : il corrige l'alignement. Puis `terraform init` : il télécharge le provider et crée `.terraform.lock.hcl`.
6. Lancez `terraform plan` et lisez la ligne `Plan:` : `1 to add`.
7. Lancez `terraform apply`, tapez `yes`, puis `cat hello.txt`.
8. Relancez `terraform plan` : `No changes`, c'est l'idempotence.

**À retenir :** déclaratif, init puis plan puis apply, relire le plan, blocs avec accolades et arguments avec `=`, `local = { }` est un argument, versions épinglées, state jamais édité à la main.
