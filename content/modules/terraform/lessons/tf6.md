# Cycle de vie, refactoring et Terraform en CI

Écrire du Terraform est la moitié du métier. L'autre moitié : le faire évoluer sans rien détruire par accident, et le faire appliquer par une CI plutôt que depuis un poste.

## Valider les entrées

Un bloc `validation` refuse une valeur absurde avant même le plan :

```hcl
variable "environment" {
  type        = string
  description = "Environnement visé."
  validation {
    condition     = contains(["dev", "staging", "prod"], var.environment)
    error_message = "environment doit valoir dev, staging ou prod."
  }
}
```

`condition` est une expression booléenne qui utilise la variable ; `error_message` est une phrase complète qui dit quoi corriger. Pour des contrôles sur les ressources, `precondition` et `postcondition` dans `lifecycle`, et les blocs `check`, suivent le même principe.

## Le bloc lifecycle

```hcl
resource "local_file" "db_config" {
  filename = "${path.module}/out/db.conf"
  content  = "port=5432"
  lifecycle {
    prevent_destroy = true
  }
}
```

- `prevent_destroy = true` : tout plan qui détruirait la ressource échoue. Pour une base de données ou un bucket de state, c'est une ceinture de sécurité.
- `create_before_destroy = true` : la nouvelle version est créée avant la suppression de l'ancienne (certificats, groupes de machines).
- `ignore_changes = [tags]` : Terraform ignore un attribut modifié par un autre outil.

!!Sans prevent_destroy, une faute de frappe dans le nom d'une ressource de base de données se traduit par « 1 to destroy » et la perte des données!!

## Renommer sans détruire : moved

Renommer `local_file.hello` en `local_file.greeting` dans le code, c'est pour Terraform supprimer l'un et créer l'autre. Le bloc `moved` lui dit que c'est le même objet :

```hcl
moved {
  from = local_file.hello
  to   = local_file.greeting
}
```

Le plan annonce alors « has moved to » et zéro destruction. Même chose pour déplacer une ressource dans un module (`to = module.app.local_file.config`).

## Adopter l'existant : import

Une ressource créée à la main se rattache au state sans être recréée :

```hcl
import {
  to = aws_s3_bucket.logs
  id = "acme-logs"
}
```

`terraform plan -generate-config-out=generated.tf` écrit même le bloc `resource` correspondant, à relire et nettoyer.

## Lire un plan comme un relecteur

- `+` création, `-` destruction, `~` modification sur place, `-/+` **remplacement** (destruction puis création).
- Cherchez `forces replacement` : l'attribut qui oblige à recréer.
- Le résumé `Plan: 2 to add, 1 to change, 0 to destroy` se lit en premier.

!!Un plan qui annonce une destruction inattendue s'arrête là : on ne lance pas apply en espérant que ça passe!!

## Terraform dans la CI

Le flux d'équipe classique :

1. Sur chaque pull request : `terraform fmt -check`, `terraform init`, `terraform validate`, `terraform plan`. Le plan est relu dans la revue.
2. Après fusion sur `main` : `terraform apply` du plan, dans un environnement GitHub protégé.

```yaml
name: Terraform
on:
  pull_request:
  push:
    branches: [main]
permissions:
  contents: read
jobs:
  plan:
    runs-on: ubuntu-latest
    timeout-minutes: 15
    steps:
      - uses: actions/checkout@v4
      - uses: hashicorp/setup-terraform@b9cd54a3c349d3f38e8881555d616ced269862dd
      - run: terraform fmt -check -recursive
      - run: terraform init -input=false
      - run: terraform validate
      - run: terraform plan -input=false -out=tfplan
  apply:
    needs: plan
    if: github.ref == 'refs/heads/main' && github.event_name == 'push'
    runs-on: ubuntu-latest
    timeout-minutes: 30
    environment: production
    permissions:
      contents: read
      id-token: write
    steps:
      - uses: actions/checkout@v4
      - uses: hashicorp/setup-terraform@b9cd54a3c349d3f38e8881555d616ced269862dd
      - run: terraform init -input=false
      - run: terraform apply -input=false -auto-approve
```

Le SHA est un exemple : prenez celui de la version voulue sur la page des releases. Les identifiants cloud viennent d'OIDC (`id-token: write` sur le seul job `apply`), comme dans le module CI/CD.

!!Un terraform apply déclenché par une pull request exécute du code non relu avec les droits de la production!!

Outils complémentaires : **tflint** (erreurs propres à chaque provider), **checkov** ou **trivy config** (failles de configuration : bucket public, chiffrement absent), `terraform test` (tests natifs).

## Labo réel

```bash
terraform fmt -recursive
terraform validate
terraform plan            # avec le bloc moved : « has moved to », 0 to destroy
terraform plan -destroy   # avec prevent_destroy : erreur attendue
```

**À retenir :** `validation` avec un `error_message` clair, `prevent_destroy` sur ce qui contient des données, `moved` pour renommer, `import` pour adopter, lire `-/+` et `forces replacement`, `fmt`, `validate` et `plan` sur chaque PR, `apply` seulement sur `main` dans un environnement protégé avec OIDC.
