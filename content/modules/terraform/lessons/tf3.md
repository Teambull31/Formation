# Sécurité : secrets, state et moindre privilège

Une configuration Terraform manipule des mots de passe, des clés et des permissions. Une erreur ici finit dans l'historique du dépôt, puis chez un attaquant.

## Aucun secret dans le code

!!Un mot de passe écrit dans un fichier .tf ou .tfvars versionné est compromis dès le premier commit!!

La bonne pratique : déclarer la variable avec `sensitive = true` et **sans valeur par défaut**, puis fournir la valeur à l'exécution, par exemple avec la variable d'environnement `TF_VAR_db_password` ou depuis un gestionnaire de secrets.

```hcl
variable "db_password" {
  type        = string
  description = "Mot de passe de la base, injecté à l'exécution."
  sensitive   = true
}

resource "local_sensitive_file" "db" {
  filename = "${path.module}/db.conf"
  content  = "password=${var.db_password}"
}
```

## Le state contient les secrets en clair

`sensitive = true` masque la valeur dans l'affichage du plan, mais !!la valeur reste en clair dans le fichier de state!!. Le state est donc aussi sensible qu'un mot de passe. En équipe, on le place dans un **backend distant** chiffré, avec verrouillage et accès restreint. Un output qui expose un secret doit lui aussi porter `sensitive = true`.

## Ce que Git ne doit jamais voir

Dans le fichier d'exclusion `.gitignore`, mettez `*.tfstate`, `*.tfstate.*`, `.terraform/` et `*.tfvars`. À l'inverse, le fichier de verrouillage `.terraform.lock.hcl` **se versionne** : il fige les versions des providers. !!Une règle trop large comme * cache aussi votre propre code!!

## Moindre privilège

Pensez à l'attaquant qui vole l'identité de votre pipeline : il hérite de tout ce qu'elle peut faire. Plus ses droits sont étroits, plus l'incident reste petit.

Le compte qui lance Terraform ne reçoit que les droits nécessaires, comme un conteneur lancé sans être root limite les dégâts d'une compromission. Prévoyez une identité par environnement et évitez les politiques « tout autorisé » sur toutes les ressources.

**À retenir :** secrets injectés à l'exécution et jamais écrits, state protégé et hors de Git, droits minimaux.
