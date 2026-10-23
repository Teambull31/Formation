# IaC déclaratif et workflow init / plan / apply

Créer des serveurs, des dossiers ou des droits à la main, c'est lent et impossible à rejouer. Avec l'**Infrastructure as Code**, on décrit l'infrastructure dans des fichiers versionnés, comme du code. Terraform est l'outil le plus répandu pour cela.

## Déclaratif : on décrit le résultat

Terraform est **déclaratif** : vous écrivez l'état final voulu, pas les étapes pour l'atteindre. L'outil compare ce que vous demandez avec ce qui existe, puis calcule seul les actions à faire. Un script impératif dit « crée un dossier » ; Terraform dit « ce dossier doit exister », et ne fait rien s'il existe déjà.

## Le workflow en trois temps

`terraform init` prépare le dossier de travail et récupère les **providers**, les modules d'extension qui savent parler à une plateforme. `terraform plan` calcule les différences et affiche un plan, sans rien modifier. `terraform apply` exécute ensuite ce plan.

!!Lisez toujours le plan avant d'appliquer : une ligne « destroy » oubliée supprime une ressource de production!!

## Anatomie d'une configuration

Le bloc `terraform` fixe la version minimale de l'outil et la liste des providers. Le bloc `resource` déclare un objet à gérer : son premier nom est le type, le second est le nom local.

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
  content  = "Bonjour IaC"
}
```

Ici `~> 2.5` accepte les versions 2.x à partir de 2.5, mais pas la 3.0 : on **épingle** les versions pour que le déploiement d'aujourd'hui ressemble à celui de l'an prochain.

!!Un provider sans contrainte de version peut changer de version majeure et casser votre code un lundi matin!!

## Le state, la mémoire de Terraform

Terraform note dans un fichier de **state** quel objet réel correspond à quelle ressource du code. Sans lui, il ne sait pas ce qui existe déjà. Si quelqu'un modifie un objet à la main, c'est une **dérive** : le prochain `plan` la détecte.

!!Ne modifiez jamais le fichier de state à la main : passez par les commandes terraform state!!

## Idempotence

Relancer `apply` sans changer le code ne modifie rien. Cette propriété, l'**idempotence**, rend les déploiements sûrs à répéter.

**À retenir :** déclaratif, init puis plan puis apply, relire le plan, versions épinglées, state jamais édité à la main.
