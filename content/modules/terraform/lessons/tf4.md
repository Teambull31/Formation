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

`each.key` est la clé (`dev`, `prod`), `each.value` la valeur. Retirer `staging` ne touche que `local_file.config["staging"]`. Règle : **`for_each` pour une collection d'objets distincts**, `count` seulement pour « 0 ou 1 » (une ressource optionnelle).

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

À utiliser avec modération : un bloc écrit en clair se relit mieux qu'une boucle.

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
