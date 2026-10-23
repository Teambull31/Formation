# Variables, outputs et contrat d'un module

Un **module** Terraform est un dossier de configuration réutilisable. Ses entrées sont les `variable`, ses sorties les `output` : ensemble, ils forment le **contrat** du module. Les appelants ne dépendent que de ce contrat, jamais des ressources internes.

## Les variables d'entrée

Une bonne variable déclare un `type` et une `description`. Le type fait rejeter tôt une valeur absurde, avant toute modification ; la description est la documentation, lue par vos collègues et par les outils.

!!Une variable sans type accepte n'importe quoi et reporte l'erreur au moment le plus coûteux!!

## Obligatoire ou facultative

Avec un attribut `default`, la variable est facultative. **Sans `default`, elle est obligatoire** : Terraform la demande, ou échoue en CI s'il ne peut pas poser la question. Pour une valeur sans bon défaut, comme l'environnement visé, mieux vaut forcer l'appelant à choisir.

## Les outputs : exposer le minimum

Un `output` publie une valeur calculée : un chemin, une adresse, un identifiant. Chaque output devient un engagement de compatibilité envers les appelants.

!!N'exposez pas la ressource entière : un output ne doit livrer que ce dont l'appelant a besoin!!

```hcl
variable "app_name" {
  type        = string
  description = "Nom de l'application, préfixe des fichiers générés."
  default     = "demo"
}

output "config_path" {
  description = "Chemin du fichier de configuration généré."
  value       = local_file.config.filename
}
```

## Référencer et appeler

Dans un module, les ressources, les variables et les outputs se répondent par leur nom : c'est ce graphe de références qui permet à Terraform de choisir l'ordre de création.

On lit une variable avec `var.app_name` et un attribut de ressource avec `local_file.config.filename`. Un appelant utilise un module par un bloc `module`, puis lit ses sorties avec `module.app.config_path`. La référence doit viser quelque chose de **déclaré** : une faute de frappe fait échouer le plan.

!!Ne lisez jamais le contenu interne d'un module depuis l'extérieur : passez par ses outputs!!

**À retenir :** type et description partout, pas de default pour une valeur obligatoire, peu d'outputs, références qui existent.
