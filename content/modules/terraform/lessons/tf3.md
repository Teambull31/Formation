# Sécurité : secrets, state et moindre privilège

Une configuration Terraform manipule des mots de passe, des clés et des permissions. Une erreur ici finit dans l'historique du dépôt, puis chez un attaquant.

## Aucun secret dans le code

!!Un mot de passe écrit dans un fichier .tf ou .tfvars versionné est compromis dès le premier commit!!

La bonne pratique : déclarer la variable avec `sensitive = true` et **sans valeur par défaut**, puis fournir la valeur à l'exécution, par exemple avec la variable d'environnement `TF_VAR_db_password` ou depuis un gestionnaire de secrets.

Avant, puis après :

```hcl
# AVANT : secure.tf hérité, le mot de passe est dans le dépôt
variable "db_password" {
  default = "Sup3rS3cret!"                       # ✗ la valeur est versionnée
}

resource "local_file" "db" {                     # ✗ fichier ordinaire : contenu affiché dans le plan
  filename = "${path.module}/db.conf"
  content  = "password=Sup3rS3cret!"             # ✗ et une seconde copie en dur
}
```

```hcl
# APRÈS : secure.tf corrigé
variable "db_password" {
  type        = string
  description = "Mot de passe de la base, injecté à l'exécution."
  sensitive   = true                             # ← masqué dans plan et apply
  # pas de default : la valeur vient de TF_VAR_db_password
}

resource "local_sensitive_file" "db" {           # ← variante « sensible » : contenu masqué
  filename = "${path.module}/db.conf"
  content  = "password=${var.db_password}"       # ← on lit la variable, jamais de valeur en dur
}

output "db_conf_path" {
  value = local_sensitive_file.db.filename       # le chemin n'est pas secret : output normal
}
```

Trois corrections, trois endroits :

1. Dans le bloc `variable` : `sensitive = true` ajouté, `default` supprimé.
2. Le **type** de la ressource change : `local_file` devient `local_sensitive_file`. C'est la première étiquette du bloc qui change, pas un argument.
3. Dans `content` : la valeur en dur devient l'interpolation `${var.db_password}`.

Pour fournir la valeur sans l'écrire nulle part :

```bash
read -rs TF_VAR_db_password && export TF_VAR_db_password   # saisie masquée, rien dans l'historique
terraform plan
```

## Le state contient les secrets en clair

`sensitive = true` masque la valeur dans l'affichage du plan, mais !!la valeur reste en clair dans le fichier de state!!. Le state est donc aussi sensible qu'un mot de passe. En équipe, on le place dans un **backend distant** chiffré, avec verrouillage et accès restreint. Un output qui expose un secret doit lui aussi porter `sensitive = true` :

```hcl
output "db_password" {
  value     = var.db_password
  sensitive = true          # ← sans lui, terraform refuse : « Output refers to sensitive values »
}
```

## Ce que Git ne doit jamais voir

Dans le fichier d'exclusion `.gitignore`, mettez `*.tfstate`, `*.tfstate.*`, `.terraform/` et `*.tfvars`. À l'inverse, le fichier de verrouillage `.terraform.lock.hcl` **se versionne** : il fige les versions des providers.

```
# Fichier : .gitignore (à la racine du dépôt)
*.tfstate          # le state : contient les secrets en clair
*.tfstate.*        # ses sauvegardes : terraform.tfstate.backup
.terraform/        # le cache des providers : se recrée avec terraform init
*.tfvars           # les valeurs propres à chaque environnement
# .terraform.lock.hcl n'est PAS listé : il se versionne
```

!!Une règle trop large comme * cache aussi votre propre code!!

## Moindre privilège

Pensez à l'attaquant qui vole l'identité de votre pipeline : il hérite de tout ce qu'elle peut faire. Plus ses droits sont étroits, plus l'incident reste petit.

Le compte qui lance Terraform ne reçoit que les droits nécessaires, comme un conteneur lancé sans être root limite les dégâts d'une compromission. Prévoyez une identité par environnement et évitez les politiques « tout autorisé » sur toutes les ressources.

## Pas à pas : colmater la fuite

1. Dans `secure.tf`, ouvrez le bloc `variable "db_password"`. Ajoutez `type = string` et `sensitive = true`, supprimez la ligne `default`.
2. Changez le type de la ressource en `local_sensitive_file`, en gardant le nom local `db`.
3. Dans son `content`, remplacez le mot de passe par `${var.db_password}`.
4. Cherchez une copie oubliée de l'ancien mot de passe : `grep -rn "password" *.tf *.tfvars`, puis relisez chaque ligne trouvée.
5. Si un output expose le mot de passe, ajoutez-lui `sensitive = true`.
6. Complétez `.gitignore` avec les quatre motifs, puis vérifiez avec `git status --ignored`.
7. Comme le secret a été versionné, changez-le : le supprimer du fichier ne l'efface pas de l'historique Git.

**À retenir :** secrets injectés à l'exécution et jamais écrits, `sensitive = true` sur la variable et l'output, `local_sensitive_file`, state protégé et hors de Git, lock file versionné, droits minimaux.
