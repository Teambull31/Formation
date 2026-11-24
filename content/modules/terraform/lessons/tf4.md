# Expressions, boucles et locals

Trois environnements, trois blocs `resource` copiés-collés : au premier changement, l'un des trois est oublié. Terraform sait produire plusieurs objets à partir d'une seule déclaration, et calculer des valeurs une seule fois.

## Les types

Une variable bien typée refuse les erreurs avant le `plan` :

```hcl
variable "environments" {
  type = map(object({
    replicas = number
    debug    = bool
  }))
  description = "Paramètres par environnement."
}
```

Types simples : `string`, `number`, `bool`. Collections : `list(string)` (ordonnée), `set(string)` (sans doublon, sans ordre), `map(string)` (clé vers valeur), `object({...})` (structure fixe). `optional(type, défaut)` rend un attribut d'objet facultatif.

## locals : calculer une fois

```hcl
locals {
  prefix      = "${var.app_name}-${terraform.workspace}"
  common_tags = { app = var.app_name, managed_by = "terraform" }
}
```

On les lit avec `local.prefix`. Un `locals` évite de répéter la même expression dans dix ressources : on la corrige à un seul endroit.

!!Un locals ne remplace pas une variable : la valeur d'un local ne peut pas être changée par l'appelant, réservez-le aux calculs internes!!

## count ou for_each

`count = 3` crée `local_file.config[0]`, `[1]`, `[2]`. Simple, mais fragile : les objets sont repérés par leur **position**.

!!Avec count sur une liste, retirer le premier élément décale tous les index : Terraform détruit et recrée tout ce qui suit!!

`for_each` repère chaque objet par une **clé** stable :

```hcl
resource "local_file" "config" {
  for_each = var.environments
  filename = "${path.module}/out/${each.key}.conf"
  content  = "replicas=${each.value.replicas}\ndebug=${each.value.debug}\n"
}
```

Où placer `for_each` ? C'est un **méta-argument** : il ne décrit pas le fichier, il dit à Terraform combien d'objets fabriquer. Par convention, il s'écrit **en premier** dans le bloc, suivi d'une ligne vide, pour qu'on le voie avant de lire le reste. Même règle pour `count`.

Voici les trois fichiers du TP une fois factorisés, avec le trajet des valeurs :

```hcl
# Fichier : envs.tfvars : les DONNÉES, une entrée par environnement
environments = {
  dev     = { replicas = 1, debug = true }    # clé "dev" → each.key
  staging = { replicas = 2, debug = true }    # { ... } → each.value
  prod    = { replicas = 3, debug = false }
}
```

```hcl
# Fichier : variables.tf : le TYPE de ces données
variable "environments" {
  type = map(object({         # une map : des clés libres (dev, prod…)
    replicas = number         # chaque valeur est un objet à deux attributs fixes
    debug    = bool
  }))
  description = "Paramètres par environnement."
}
```

```hcl
# Fichier : main.tf : UNE ressource, autant d'objets que de clés
locals {                                       # niveau 0, hors de toute ressource
  out_dir = "${path.module}/out"
}

resource "local_file" "config" {
  for_each = var.environments                  # ← méta-argument : en premier

  filename = "${local.out_dir}/${each.key}.conf"                          # out/dev.conf…
  content  = "replicas=${each.value.replicas}\ndebug=${each.value.debug}\n"
}
```

```hcl
# Fichier : outputs.tf : une expression for sur toutes les instances
output "config_files" {
  value = { for k, f in local_file.config : k => f.filename }   # { dev = "out/dev.conf", … }
}
```

`each.key` est la clé (`dev`, `prod`), `each.value` la valeur. `each` n'existe que dans un bloc qui a un `for_each` ; ailleurs, `terraform validate` le refuse. Retirer `staging` ne touche que `local_file.config["staging"]`. Règle : **`for_each` pour une collection d'objets distincts**, `count` seulement pour « 0 ou 1 » (une ressource optionnelle).

```hcl
resource "local_file" "debug" {
  count    = var.enable_debug ? 1 : 0
  filename = "${path.module}/out/debug.txt"
  content  = "debug activé"
}
```

!!for_each n'accepte pas une liste : convertissez-la avec toset(var.noms), ou utilisez une map!!

## Les expressions utiles

- Condition : `var.env == "prod" ? 3 : 1`.
- Boucle `for` dans une valeur : `[for n in var.noms : upper(n)]` donne une liste, `{ for k, v in var.environments : k => v.replicas }` une map.
- Filtre : `[for k, v in var.environments : k if v.debug]`.
- Fonctions : `merge()`, `lookup()`, `contains()`, `length()`, `join()`, `format()`, `file()`, `templatefile()`, `jsonencode()`.
- Accès à toutes les instances : `local_file.config["prod"].filename`, ou en boucle `[for f in local_file.config : f.filename]`.

## Les blocs dynamic

Certaines ressources ont des blocs imbriqués répétables (règles de pare-feu, ports). `dynamic` les génère :

```hcl
dynamic "ingress" {
  for_each = var.ports
  content {
    from_port = ingress.value
    to_port   = ingress.value
    protocol  = "tcp"
  }
}
```

Le bloc `dynamic` se place **dans** la ressource, à l'endroit où l'on aurait écrit les blocs `ingress` à la main. Son étiquette (`"ingress"`) est le nom du bloc à générer, et c'est aussi le nom de l'itérateur : on lit `ingress.value`, pas `each.value`. Le contenu généré va dans le sous-bloc `content { }`.

```hcl
resource "aws_security_group" "web" {
  name = "web"

  dynamic "ingress" {              # ← génère un bloc « ingress » par port
    for_each = var.ports           # [80, 443]
    content {                      # ← ce qui irait dans chaque bloc ingress
      from_port   = ingress.value
      to_port     = ingress.value
      protocol    = "tcp"
      cidr_blocks = ["0.0.0.0/0"]
    }
  }
}
```

À utiliser avec modération : un bloc écrit en clair se relit mieux qu'une boucle.

## Pas à pas : factoriser trois ressources en une

1. Ouvrez `envs.tfvars` : les trois environnements y sont déjà, sous forme de map.
2. Dans `variables.tf`, déclarez `environments` avec `type = map(object({ replicas = number, debug = bool }))` et une `description`, sans `default`.
3. Dans `main.tf`, ajoutez un bloc `locals { }` au niveau 0 avec `out_dir`.
4. Supprimez deux des trois ressources. Dans la troisième, ajoutez `for_each = var.environments` en première ligne.
5. Remplacez le nom en dur dans `filename` par `${each.key}`, et les valeurs de `content` par `${each.value.replicas}` et `${each.value.debug}`.
6. Dans `outputs.tf`, écrivez `config_files` avec l'expression `for` sur `local_file.config`.
7. Testez l'expression dans `terraform console -var-file=envs.tfvars`, puis `terraform plan -var-file=envs.tfvars` : trois objets `local_file.config["dev"]`, `["staging"]`, `["prod"]`.

## Tester ses expressions

`terraform console` ouvre une invite où l'on évalue une expression avec les variables du dossier :

```bash
terraform console
> { for k, v in var.environments : k => v.replicas }
> toset(["a", "b", "a"])
```

## Labo réel

Terraform est installé sur votre poste. Dans le dossier du TP, une fois le code écrit :

```bash
terraform init
terraform plan -var-file=envs.tfvars
terraform apply -var-file=envs.tfvars
ls out/
terraform state list
```

Retirez ensuite `staging` de `envs.tfvars` et relancez `plan` : un seul objet doit être détruit.

**À retenir :** types précis (`map(object)`), `locals` pour calculer une fois, `for_each` avec `each.key` et `each.value` pour les collections, `count` pour 0 ou 1, `toset()` pour une liste, expressions `for` et conditions, `terraform console` pour tester.
