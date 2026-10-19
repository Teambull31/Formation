# Du compte perso au compte pro

Cette fiche explique comment passer du kit d'entraînement (mails fictifs en @example.test) à une vraie boîte, d'abord la vôtre, puis celle de l'entreprise.

Rappel : !!la connexion au compte professionnel se fait au travail, jamais depuis l'appli d'entraînement.!! Et **aucun mail réel ne va à Claude ou à un service externe** : le connecteur lit, votre script trie, tout reste sur votre machine.

## Essai réel avec votre compte Outlook personnel

Un compte perso (outlook.com, hotmail.com) suffit pour tester sans rien demander à personne. Les libellés du portail changent souvent : (le libellé exact peut varier) pour chaque étape.

1. Ouvrez le portail Microsoft Entra (ex-Azure) avec votre compte personnel et cherchez la section « Inscriptions d'applications » (App registrations).
2. Créez une inscription : nom libre, type de comptes « comptes Microsoft personnels uniquement » (le libellé exact peut varier). Cela correspond au tenant `consumers`.
3. Dans l'authentification de l'application, ajoutez la plateforme « client public / mobile et bureau » et activez les flux client public (le libellé exact peut varier). Pas de secret client : l'appli est un **public client**.
4. Dans les autorisations d'API, ajoutez Microsoft Graph, autorisation déléguée `Mail.Read` et rien d'autre. !!Jamais Mail.ReadWrite ni Mail.Send.!!
5. Copiez l'identifiant d'application (client id) et passez-le à `OutlookGraphSource` : `OutlookGraphSource(client_id, tenant="consumers")`.
6. Lancez le script : le connecteur utilise le **device code flow**. Il affiche une adresse et un code ; ouvrez l'adresse dans un navigateur, saisissez le code, acceptez `Mail.Read`.
7. Le jeton est enregistré dans `~/.config/formation-auto1/` (`token_path` par défaut), fichier en **0600** (lisible par vous seul). Ne le copiez jamais dans un dépôt git.
8. Pour révoquer : supprimez le fichier de jeton, puis retirez l'application dans les paramètres de votre compte Microsoft (page des applications autorisées, le libellé exact peut varier). !!Un jeton oublié reste valable tant qu'il n'est pas révoqué.!!

Gmail suit la même logique avec `GmailSource` et le scope `gmail.readonly` (fichier `credentials_path` à créer dans la console Google Cloud).

## Perso contre pro

| | Compte perso | Compte pro |
|---|---|---|
| Tenant | `consumers` | `organizations` ou l'identifiant du tenant de l'entreprise |
| Qui consent | vous | vous ou un administrateur, selon la politique |
| Scopes | `Mail.Read` | `Mail.Read` seul, validé par l'IT |
| Accès conditionnel | aucun | appareil conforme, MFA, lieu, selon l'entreprise |
| Durée de vie du jeton | longue, renouvelable | souvent courte, session imposée par l'IT |

## Enregistrement de l'application dans l'annuaire de l'entreprise

Au travail, l'application doit exister dans l'annuaire (Entra ID) de l'entreprise. Vous n'avez peut-être pas le droit de la créer : demandez-le. Précisez : client public, flux device code, scope `Mail.Read`, un seul propriétaire nommé. Le tenant devient `organizations` ou l'identifiant fourni par l'IT.

## Consentement administrateur

Beaucoup d'entreprises interdisent le consentement individuel : un administrateur doit approuver l'application. C'est normal. **Sans ce consentement, la connexion échoue**, même avec le bon code. N'essayez pas de le contourner.

## Droits d'accès aux mails

Demandez le minimum : lecture seule (`Mail.Read`), sur votre boîte uniquement. !!Pas d'accès aux boîtes des autres, pas d'envoi, pas de suppression.!! Le kit ne fait que des requêtes GET sur un hôte unique.

## Règles d'accès conditionnel

L'entreprise peut exiger un appareil géré, un MFA, ou un réseau précis. Une connexion depuis un poste personnel peut être bloquée. Ne cherchez pas à les contourner : c'est une règle de sécurité, pas un bug. Si l'appareil n'est pas autorisé, travaillez depuis le poste fourni.

## Accord du service informatique

!!Ne branchez rien sur la boîte pro sans accord écrit du service informatique.!! Envoyez-leur ce message, adaptable :

> Objet : demande d'autorisation, automatisation de lecture de ma boîte mail
>
> - [ ] Inscription d'une application (client public) dans l'annuaire, propriétaire : moi
> - [ ] Flux device code autorisé pour cette application
> - [ ] Consentement administrateur pour le scope `Mail.Read` (lecture seule)
> - [ ] Accès limité à ma seule boîte
> - [ ] Règles d'accès conditionnel applicables (appareil, MFA, lieu) : lesquelles ?
> - [ ] Durée de vie du jeton et procédure de révocation
> - [ ] Où stocker le jeton (dossier utilisateur, droits 0600) et sur quelle machine
> - [ ] Confirmation qu'aucun mail ne quitte la machine

Rappel : **la connexion au compte professionnel se fait au travail**, avec l'accord de l'IT.

## Si l'accès API est refusé

C'est fréquent, et ce n'est pas un échec. Deux solutions sans API :

- **IMAP en lecture seule** : `ImapSource(host, user, password_env)`, si l'IT ouvre IMAP. Le mot de passe vient d'une variable d'environnement, la boîte est ouverte en lecture seule.
- **Export `.mbox`** : exportez une copie de vos mails depuis votre client, puis lisez-la avec `MboxMailSource(path)`. Aucune connexion, aucun jeton.

!!Dans les deux cas, le reste de votre automatisation ne change pas.!! Seul le connecteur change : c'est le but du contrat `MailSource`.
