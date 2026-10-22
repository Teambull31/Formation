# Variables, outputs et contrat d'un module

Un **module** Terraform est un dossier de configuration réutilisable. Ses `variable` sont ses entrées, ses `output` ses sorties : ensemble, ils forment le **contrat** du module. Les appelants ne dépendent que de ce contrat, jamais des ressources internes.

## Variables d'entrée
Une variable bien conçue déclare un `type`, une `description` et, si c'est pertinent, une valeur par défaut ou une règle de validation.

```hcl
variable "app_name" {
  type        = string
  description = "Nom de l'application, utilisé comme préfixe des ressources."
  default     = "demo"

  validation {
    condition     = length(var.app_name) > 2
    error_message = "app_name doit contenir au moins 3 caractères."
  }
}
```

## Sorties
Les outputs exposent uniquement ce dont les appelants ont besoin : un identifiant, une adresse, un chemin.

```hcl
output "config_path" {
  description = "Chemin du fichier de configuration généré."
  value       = local_file.config.filename
}
```

## Appeler un module
```hcl
module "app" {
  source   = "./modules/app"
  app_name = "billing"
}
```
La valeur d'un output se lit ensuite avec `module.app.config_path`.

## Points clés
- **Typer et documenter** chaque variable : la `description` est la documentation du module, affichée dans `terraform-docs` et dans l'éditeur.
- !!Une variable sans type accepte n'importe quoi!! et reporte l'erreur à l'exécution.
- **Exposer le minimum** : chaque output ajouté devient un engagement de compatibilité envers les appelants.
- Une variable sans `default` est **obligatoire** : Terraform refuse de planifier tant qu'elle n'est pas fournie.
