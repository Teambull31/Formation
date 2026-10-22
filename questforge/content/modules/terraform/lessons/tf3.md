# Sécurité : secrets, state et moindre privilège

Une configuration Terraform manipule des identifiants, des mots de passe et des permissions. Une erreur ici se retrouve dans l'historique Git, dans le state, puis chez un attaquant.

## Les secrets ne vivent jamais dans le code
- !!Aucun secret ou mot de passe en dur!! dans un fichier `.tf` ou `.tfvars` versionné.
- Déclarez la variable avec `sensitive = true` et **sans valeur par défaut**.
- Injectez la valeur à l'exécution : variable d'environnement `TF_VAR_db_password`, ou lecture depuis un gestionnaire de secrets (Vault, coffre du cloud).

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

## Le state contient des secrets en clair
`sensitive = true` masque la valeur dans l'affichage du plan, mais !!la valeur reste en clair dans le fichier de state!!. Le state est donc aussi sensible qu'un secret.
- Ne commitez jamais `*.tfstate` ni `.terraform/`.
- En équipe, utilisez un **backend distant chiffré** avec **verrouillage**, accessible à un nombre minimal de personnes.

## Fichiers à exclure de Git
Dans `.gitignore` : `*.tfstate`, `*.tfstate.*`, `.terraform/` et `*.tfvars`.

## Moindre privilège
Le compte qui exécute Terraform ne doit détenir que les permissions strictement nécessaires, comme un conteneur lancé en utilisateur non-root limite les dégâts d'une compromission.
- Une identité par environnement, avec uniquement les droits requis.
- Évitez les politiques en `*` sur les actions et les ressources.

## Points clés
- **Secrets injectés à l'exécution**, jamais écrits dans le dépôt.
- **State = donnée sensible** : chiffré, verrouillé, à accès restreint.
- **Moindre privilège** pour l'identité d'exécution, afin de réduire la surface d'attaque.
