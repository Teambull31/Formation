# Fiche de révision : Terraform

## Le cycle

```bash
terraform init            # providers, modules, backend
terraform fmt -recursive  # mise en forme
terraform validate        # syntaxe et types
terraform plan -out=tfplan
terraform apply tfplan
terraform destroy         # avec prudence
terraform state list | show <adresse>
terraform output [-json]
terraform console         # tester une expression
```

- Déclaratif : on décrit l'état voulu, Terraform calcule l'écart.
- Idempotent : un second `apply` sans changement ne fait rien.
- Le **state** fait le lien code / objets réels. Il contient les secrets **en clair**.

## Squelette

```hcl
terraform {
  required_version = ">= 1.10.0"
  required_providers {
    aws = {
      source  = "hashicorp/aws"
      version = "~> 5.60"
    }
  }
  backend "s3" {
    bucket       = "acme-tfstate"
    key          = "web/prod.tfstate"
    region       = "eu-west-3"
    encrypt      = true
    use_lockfile = true
  }
}
```

- `~> 5.60` : 5.60 et plus, pas 6.0. Versionnez `.terraform.lock.hcl`.
- !!Jamais de clés dans le bloc backend ni dans un provider : environnement, profil ou OIDC!!

## Variables, outputs, locals

```hcl
variable "environment" {
  type        = string
  description = "dev, staging ou prod."
  validation {
    condition     = contains(["dev", "staging", "prod"], var.environment)
    error_message = "environment doit valoir dev, staging ou prod."
  }
}
variable "db_password" {
  type      = string
  sensitive = true          # pas de default
}
locals {
  prefix = "${var.app}-${var.environment}"
}
output "url" {
  description = "Adresse publique."
  value       = aws_lb.web.dns_name
}
```

- Sans `default` = obligatoire. Priorité : `-var` > `*.auto.tfvars` > `terraform.tfvars` > `TF_VAR_x` > default.
- Types : `string`, `number`, `bool`, `list()`, `set()`, `map()`, `object({})`, `optional()`.
- Output qui expose un secret : `sensitive = true`.

## Boucles et expressions

- `for_each = var.map` (ou `toset(list)`) : `each.key`, `each.value`. Stable par clé.
- `count = cond ? 1 : 0` : ressource optionnelle uniquement.
- `[for x in l : upper(x)]`, `{ for k, v in m : k => v.id }`, filtre `if`.
- `dynamic "bloc" { for_each = ... content { ... } }`.
- Adresses : `aws_instance.web["prod"]`, `aws_instance.web[0]`, `module.app.output`.

## Modules

- Dossier avec `variables.tf`, `main.tf`, `outputs.tf`. Pas de `provider` dedans.
- Appel : `module "web" { source = "./modules/app"  environment = var.environment }`.
- Tout est passé explicitement ; lecture par `module.web.<output>`.
- Registre : `version = "~> 5.8"`. Git : `?ref=v1.2.0`. `terraform init` après un changement de source.
- Un dossier par environnement plutôt que des workspaces pour dev/prod.

## Cycle de vie et refactoring

- `lifecycle { prevent_destroy = true }` : bases, buckets de state.
- `create_before_destroy`, `ignore_changes = [tags]`, `precondition` / `postcondition`.
- `moved { from = a  to = b }` : renommer sans détruire.
- `import { to = aws_s3_bucket.logs  id = "acme-logs" }` puis `plan -generate-config-out=gen.tf`.
- `terraform apply -replace=<adresse>` : forcer une recréation (remplace `taint`).
- Lire un plan : `+` créer, `-` détruire, `~` modifier, `-/+` remplacer, « forces replacement ».
- !!Destruction inattendue dans un plan : on s'arrête, on n'applique pas!!

## Sécurité

- `.gitignore` : `*.tfstate`, `*.tfstate.*`, `.terraform/`, `*.tfvars` (sauf exemples).
- State distant chiffré, verrouillé, versionné, accès restreint.
- Une identité par environnement, droits minimaux, pas de politique `*:*`.
- Scanners : `tflint`, `checkov`, `trivy config`.

## En CI

- PR : `fmt -check`, `init`, `validate`, `plan` (plan relu en revue).
- `main` : `apply` dans un environnement protégé, `id-token: write` sur ce seul job (OIDC).
- `-input=false` partout ; actions tierces épinglées sur SHA.

## Dépannage

- `Error acquiring the state lock` : un autre apply tourne, ou un verrou orphelin (`terraform force-unlock <id>` seulement si sûr).
- `Inconsistent dependency lock file` : `terraform init -upgrade` puis commit du lock.
- Dérive (quelqu'un a modifié à la main) : `terraform plan -refresh-only`.
- Cycle de dépendances : sortir la valeur commune dans un local ou une autre ressource.
- `TF_LOG=DEBUG terraform plan` pour les journaux du provider.

## Questions d'entretien

- Que contient le state, où le stocker, comment le protéger ?
- count ou for_each : lequel et pourquoi ?
- Renommer une ressource sans la détruire ?
- Comment Terraform et Ansible se complètent-ils ?
- Comment éviter qu'un apply parte depuis une PR non relue ?
