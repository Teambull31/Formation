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

`terraform state mv` fait la même chose en ligne de commande, mais sans trace dans le code.

## La dérive

Le code est la **source de vérité**. Face à une dérive, deux cas :

1. le changement manuel était une erreur : `apply` remet l'état décrit ;
2. il était voulu : on le reporte dans le code, puis `plan` doit annoncer « No changes ».

`terraform plan -refresh-only` montre la dérive seule, sans proposer de corrections.

!!Corriger la production à la main en urgence sans reporter le changement dans le code, c'est préparer la panne du prochain apply!!

## Le verrou

`Error acquiring the state lock` : un autre `plan` ou `apply` tourne, ou un job a été tué. Vérifiez d'abord qu'aucun run n'est en cours, puis seulement `terraform force-unlock <ID>`.

## Labo réel

```bash
terraform init
terraform plan -var-file=prod.tfvars
terraform plan -refresh-only -var-file=prod.tfvars
terraform state list
terraform show -json plan.out | jq '.resource_changes[] | select(.change.actions | index("delete"))'
```

**À retenir :** lire `-/+` et « forces replacement » avant tout ; `moved` pour renommer ou passer de `count` à `for_each` ; corriger l'entrée, pas la validation ; la dérive se règle par le code ; `force-unlock` seulement quand aucun run n'est en cours.
