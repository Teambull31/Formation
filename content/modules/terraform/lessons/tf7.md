# Répare la panne : le plan qui veut tout détruire

Avec Terraform, la panne la plus coûteuse n'est pas l'erreur : c'est le `apply` lancé sur un plan mal lu. Cette leçon apprend à **lire un plan** comme un relevé d'incident, puis le TP vous donne cinq pannes à diagnostiquer.

## Lire un plan

| Symbole | Sens | Danger |
|---|---|---|
| `+` | création | faible |
| `~` | modification sur place | moyen |
| `-/+` | destruction puis recréation | élevé : données, IP, identifiants changent |
| `-` | destruction | élevé |
| `<=` | lecture d'une source de données | aucun |

La ligne **forces replacement** désigne l'attribut qui oblige à remplacer l'objet. C'est elle qu'il faut expliquer avant d'appliquer.

!!Un plan avec des destructions que personne n'explique ne s'applique pas : on s'arrête et on cherche!!

## Les familles de pannes

- **version** : `no available releases match` au `init`. La contrainte du provider vise une version inexistante ou incompatible.
- **validation** : `Invalid value for variable`. L'entrée est fausse ; on corrige le tfvars, pas la validation.
- **renommage** : « is not in configuration » et une création sous un autre nom. Il manque un bloc `moved`.
- **index** : retirer un élément au milieu d'une liste en `count` décale tous les suivants. `for_each` repère par clé.
- **dérive** : « Objects have changed outside of Terraform ». Quelqu'un a modifié l'infrastructure à la main.

!!Affaiblir une validation pour faire passer une valeur, c'est retirer le garde-fou qui protégeait la production!!

## Passer de count à for_each sans rien détruire

Changer `count` en `for_each` change toutes les adresses : `server[0]` devient `server["web-1"]`. Sans précaution, le plan détruit et recrée tout. Des blocs `moved` font la correspondance :

```hcl
moved {
  from = local_file.server[0]
  to   = local_file.server["web-1"]
}
```

Voici la migration complète, avant et après :

```hcl
# AVANT : count sur une liste, chaque serveur est repéré par sa position
variable "servers" {
  type    = list(string)
  default = ["web-1", "web-2", "web-3"]
}

resource "local_file" "server" {
  count    = length(var.servers)
  filename = "${path.module}/out/${var.servers[count.index]}.conf"
  content  = "name=${var.servers[count.index]}"
}
```

```hcl
# APRÈS : for_each sur un ensemble, chaque serveur est repéré par son nom
resource "local_file" "server" {
  for_each = toset(var.servers)          # ← liste convertie en set : for_each l'exige

  filename = "${path.module}/out/${each.key}.conf"   # each.key = "web-1"…
  content  = "name=${each.key}"
}

# Un bloc moved par objet existant : position → nom
moved {
  from = local_file.server[0]            # index entier, sans guillemets
  to   = local_file.server["web-1"]      # clé texte, avec guillemets
}
moved {
  from = local_file.server[1]
  to   = local_file.server["web-2"]
}
moved {
  from = local_file.server[2]
  to   = local_file.server["web-3"]
}
```

Dans les adresses, `[0]` sans guillemets désigne une **position** (count), `["web-1"]` avec guillemets désigne une **clé** (for_each). Confondre les deux donne `Resource instance not found`.

Avec un `set`, `each.key` et `each.value` sont identiques : le nom du serveur. Après la migration, retirer `web-2` de la liste ne touche que `local_file.server["web-2"]`.

`terraform state mv` fait la même chose en ligne de commande, mais sans trace dans le code.

## La dérive

Le code est la **source de vérité**. Face à une dérive, deux cas :

1. le changement manuel était une erreur : `apply` remet l'état décrit ;
2. il était voulu : on le reporte dans le code, puis `plan` doit annoncer « No changes ».

`terraform plan -refresh-only` montre la dérive seule, sans proposer de corrections.

!!Corriger la production à la main en urgence sans reporter le changement dans le code, c'est préparer la panne du prochain apply!!

## Le verrou

`Error acquiring the state lock` : un autre `plan` ou `apply` tourne, ou un job a été tué. Vérifiez d'abord qu'aucun run n'est en cours, puis seulement `terraform force-unlock <ID>`.

## Pas à pas : désamorcer le plan

1. Lisez `incidents/01-init.txt` et les suivants. Pour chacun, notez le message exact et le symbole du plan (`-`, `-/+`).
2. Classez chaque composant dans une famille et remplissez `diagnostic.yaml`.
3. **version** : dans `required_providers`, corrigez la contrainte `version` du provider vers une version qui existe (`~> 2.5` pour `hashicorp/local`).
4. **validation** : ouvrez `prod.tfvars` et corrigez la valeur refusée. Ne touchez pas au bloc `validation` de `variables.tf`.
5. **renommage** : ajoutez au niveau 0 un bloc `moved` de l'ancienne adresse vers la nouvelle.
6. **index** : passez la ressource en `for_each = toset(...)`, remplacez `count.index` par `each.key`, et ajoutez un `moved` par serveur existant.
7. **dérive** : rien à changer dans le code, mais notez dans le diagnostic qui doit reporter quoi.
8. Avec Terraform installé : `terraform init && terraform plan -var-file=prod.tfvars` doit annoncer `0 to destroy`.

## Labo réel

```bash
terraform init
terraform plan -var-file=prod.tfvars
terraform plan -refresh-only -var-file=prod.tfvars
terraform state list
terraform show -json plan.out | jq '.resource_changes[] | select(.change.actions | index("delete"))'
```

**À retenir :** lire `-/+` et « forces replacement » avant tout ; `moved` pour renommer ou passer de `count` à `for_each` ; corriger l'entrée, pas la validation ; la dérive se règle par le code ; `force-unlock` seulement quand aucun run n'est en cours.
