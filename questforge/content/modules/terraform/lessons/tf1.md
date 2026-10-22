# IaC déclaratif et workflow init / plan / apply

Avec l'**Infrastructure as Code**, l'infrastructure est décrite dans des fichiers versionnés plutôt que créée à la main. Terraform est **déclaratif** : vous décrivez l'état final souhaité, et l'outil calcule les actions nécessaires pour y arriver.

## Le workflow en trois temps
- `terraform init` télécharge les **providers** et initialise le répertoire de travail.
- `terraform plan` compare le code, le state et la réalité, puis affiche un **plan d'exécution** sans rien modifier.
- `terraform apply` exécute ce plan. !!Lisez toujours le plan avant d'appliquer!! : c'est votre dernier filet de sécurité.
- `terraform destroy` supprime toutes les ressources gérées par la configuration.

## Anatomie d'une configuration
Un bloc `terraform` fixe les contraintes de version, un bloc `provider` configure l'accès à la plateforme, et chaque bloc `resource` déclare un objet à gérer.

```hcl
terraform {
  required_version = ">= 1.5.0"

  required_providers {
    local = {
      source  = "hashicorp/local"
      version = "~> 2.5"
    }
  }
}

resource "local_file" "hello" {
  filename = "${path.module}/hello.txt"
  content  = "Hello IaC"
}
```

## Le state, mémoire de Terraform
Terraform conserve la correspondance entre votre code et les objets réels dans un fichier de **state**. Sans lui, impossible de savoir ce qui existe déjà.
- !!Ne modifiez jamais le state à la main!! : utilisez `terraform state` et `terraform import`.
- Une ressource modifiée hors Terraform provoque une **dérive** (drift) détectée au prochain `plan`.

## Points clés
- **Déclaratif** : on décrit le résultat, pas les étapes.
- **Idempotent** : relancer `apply` sans changement de code ne modifie rien.
- **Épingler les versions** des providers pour des déploiements reproductibles.
