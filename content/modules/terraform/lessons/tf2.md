# Variables, outputs et contrat d'un module

Un **module** Terraform est un dossier de configuration réutilisable. Ses entrées sont les `variable`, ses sorties les `output` : ensemble, ils forment le **contrat** du module. Les appelants ne dépendent que de ce contrat, jamais des ressources internes.

## Un fichier par rôle

Terraform lit **tous** les fichiers `.tf` d'un dossier comme un seul ensemble : le découpage en fichiers est une convention de lecture, pas une obligation. La convention que tout le monde suit :

```
mon-module/
├── main.tf        ← les ressources : ce que le module fabrique
├── variables.tf   ← les entrées : ce que l'appelant fournit
└── outputs.tf     ← les sorties : ce que le module rend
```

Une personne qui découvre le module lit d'abord `variables.tf` et `outputs.tf` : c'est son mode d'emploi.

## Les variables d'entrée

Une bonne variable déclare un `type` et une `description`. Le type fait rejeter tôt une valeur absurde, avant toute modification ; la description est la documentation, lue par vos collègues et par les outils.

```hcl
# Fichier : variables.tf
variable "app_name" {                  # bloc variable : le nom entre guillemets
  type        = string                 # 1. le type d'abord : ce que la variable accepte
  description = "Nom de l'application, préfixe des fichiers générés."
  default     = "demo"                 # 3. présent = variable FACULTATIVE
}

variable "environment" {
  type        = string
  description = "Environnement visé : dev, staging ou prod."
  # pas de default : variable OBLIGATOIRE, l'appelant doit choisir
}
```

L'ordre `type`, `description`, `default` n'est pas imposé par Terraform, mais c'est celui de la documentation officielle : on lit ce que c'est, à quoi ça sert, puis la valeur par défaut.

Le type n'a **pas** de guillemets : `string`, `number`, `bool`, `list(string)`, `map(string)`. Avec des guillemets (`type = "string"`), Terraform récent refuse le fichier.

!!Une variable sans type accepte n'importe quoi et reporte l'erreur au moment le plus coûteux!!

## Obligatoire ou facultative

Avec un attribut `default`, la variable est facultative. **Sans `default`, elle est obligatoire** : Terraform la demande, ou échoue en CI s'il ne peut pas poser la question. Pour une valeur sans bon défaut, comme l'environnement visé, mieux vaut forcer l'appelant à choisir.

Trois façons de fournir une valeur, de la plus faible à la plus forte :

```bash
# 1. un fichier terraform.tfvars ou *.auto.tfvars, lu automatiquement
environment = "dev"
# 2. une variable d'environnement préfixée TF_VAR_
export TF_VAR_environment=staging
# 3. la ligne de commande : gagne sur tout le reste
terraform plan -var 'environment=prod'
```

## Les outputs : exposer le minimum

Un `output` publie une valeur calculée : un chemin, une adresse, un identifiant. Chaque output devient un engagement de compatibilité envers les appelants.

```hcl
# Fichier : outputs.tf
output "config_path" {
  description = "Chemin du fichier de configuration généré."
  value       = local_file.config.filename   # type.nom.attribut d'une ressource de main.tf
}
```

!!N'exposez pas la ressource entière : un output ne doit livrer que ce dont l'appelant a besoin!!

## Référencer et appeler

Dans un module, les ressources, les variables et les outputs se répondent par leur nom : c'est ce graphe de références qui permet à Terraform de choisir l'ordre de création.

On lit une variable avec `var.app_name` et un attribut de ressource avec `local_file.config.filename`. Un appelant utilise un module par un bloc `module`, puis lit ses sorties avec `module.app.config_path`. La référence doit viser quelque chose de **déclaré** : une faute de frappe fait échouer le plan.

Voici les trois fichiers reliés, avec le chemin d'une valeur :

```hcl
# main.tf du module : utilise les variables
resource "local_file" "config" {
  filename = "${path.module}/${var.app_name}-${var.environment}.conf"   # ← lit variables.tf
  content  = "env=${var.environment}\n"
}

# main.tf de l'appelant, dans le dossier parent
module "app" {                       # « app » : nom local du module, choisi par vous
  source      = "./mon-module"       # dossier du module
  environment = "prod"               # ← remplit la variable obligatoire
}                                    #   app_name garde son default "demo"

output "fichier" {
  value = module.app.config_path     # ← lit l'output du module, jamais local_file.config
}
```

`"${...}"` insère une valeur dans un texte : c'est l'**interpolation**. Quand la valeur est seule, on écrit directement `var.app_name`, sans guillemets ni `${}`.

!!Ne lisez jamais le contenu interne d'un module depuis l'extérieur : passez par ses outputs!!

## Pas à pas : écrire le contrat d'un module

1. Ouvrez `main.tf` et repérez les `var.` qu'il utilise et la ressource `local_file.config` : ce sont vos entrées et votre sortie.
2. Dans `variables.tf`, écrivez un bloc `variable "app_name" { }` avec `type = string`, une `description` et `default = "demo"`.
3. Écrivez `variable "environment" { }` avec `type` et `description`, **sans** `default`.
4. Dans `outputs.tf`, écrivez `output "config_path" { }` avec `description` et `value = local_file.config.filename`.
5. Lancez `terraform fmt` puis `terraform validate` : une référence vers un nom inexistant est signalée ici.
6. Lancez `terraform plan` sans valeur : Terraform demande `environment`. Relancez avec `-var 'environment=dev'`.

**À retenir :** un fichier par rôle, type sans guillemets et description partout, pas de default pour une valeur obligatoire, peu d'outputs, `var.`, `type.nom.attribut` et `module.nom.output` comme références.
