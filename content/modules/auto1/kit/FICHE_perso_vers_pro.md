# Du compte perso au compte pro

Cette fiche explique comment passer du kit d'entraînement (mails fictifs en @example.test) à une vraie boîte, d'abord la vôtre, puis celle de l'entreprise.

Rappel : !!la connexion au compte professionnel se fait au travail, jamais depuis l'appli d'entraînement.!! Et **aucun mail réel ne va à Claude ou à un service externe** : le connecteur lit, votre script trie, tout reste sur votre machine.

## Essai réel avec votre compte Outlook personnel

Un compte perso (outlook.com, hotmail.com) suffit pour tester sans rien demander à personne. (libellés Microsoft susceptibles de changer)

!!Connectez-vous au portail avec votre compte personnel.!! Si Microsoft propose de créer un annuaire gratuit (tenant) pour pouvoir inscrire l'application, acceptez : il peut être créé automatiquement.

1. Ouvrez le portail Microsoft Entra (ex-Azure) avec votre compte personnel et cherchez la section « Inscriptions d'applications » (App registrations).
2. Créez une inscription : nom libre, type de comptes « comptes Microsoft personnels uniquement ». Cela correspond au tenant `consumers`.
3. Dans l'authentification de l'application, ajoutez la plateforme « Applications mobiles et de bureau », puis activez « Autoriser les flux de client public ». Pas de secret client : l'appli est un **public client**.
4. Dans les autorisations d'API, ajoutez Microsoft Graph, autorisation déléguée `Mail.Read` et rien d'autre. !!Jamais Mail.ReadWrite ni Mail.Send.!!
5. Copiez l'identifiant d'application (client id) et passez-le à `OutlookGraphSource` : `OutlookGraphSource(client_id, tenant="consumers")`.
6. Lancez le script : le connecteur utilise le **device code flow**. Il affiche une adresse et un code ; ouvrez l'adresse dans un navigateur, saisissez le code, acceptez `Mail.Read`.
7. Le jeton est enregistré dans `~/.config/formation-auto1/` (`token_path` par défaut), fichier en **0600** (lisible par vous seul). Ne le copiez jamais dans un dépôt git.
8. Pour révoquer : supprimez le fichier de jeton, puis retirez l'application dans les paramètres de votre compte Microsoft (page des applications autorisées). !!Un jeton oublié reste valable tant qu'il n'est pas révoqué.!!

Gmail, l'essentiel avec `GmailSource` et le scope `gmail.readonly` :

- Dans la console Google Cloud, créez un projet et activez la **Gmail API**.
- Configurez l'écran de consentement OAuth et ajoutez votre adresse comme **utilisateur de test**.
- Créez un identifiant OAuth de type **application de bureau** et téléchargez son fichier JSON : c'est `credentials_path`.
- !!En mode test, le jeton expire après 7 jours.!! Il faut alors se reconnecter.

Sur Windows, le dossier du jeton est sous votre profil utilisateur (`Path.home()`, équivalent de `%USERPROFILE%\.config\formation-auto1`) : les droits reposent sur les ACL du profil, pas sur le mode 0600.

## Perso contre pro

| | Compte perso | Compte pro |
|---|---|---|
| Tenant | `consumers` | identifiant ou domaine du tenant donné par l'IT (`organizations` seulement pour une appli multi-tenant ; `common` accepte les deux, surtout pour des tests) |
| Qui consent | vous | vous ou un administrateur, selon la politique |
| Scopes | `Mail.Read` | `Mail.Read` seul, validé par l'IT |
| Accès conditionnel | aucun | appareil conforme, MFA, lieu, selon l'entreprise |
| Durée de vie du jeton | longue, renouvelable | souvent courte, session imposée par l'IT |

## Enregistrement de l'application dans l'annuaire de l'entreprise

Au travail, l'application doit exister dans l'annuaire (Entra ID) de l'entreprise. Vous n'avez peut-être pas le droit de la créer : demandez-le. Précisez : client public, flux device code, scope `Mail.Read`, un seul propriétaire nommé. Pour `tenant`, utilisez l'identifiant de tenant ou le domaine donné par le service informatique (inscription à tenant unique). `organizations` ne sert que pour une appli multi-tenant ; `common` accepte comptes perso et pro, surtout utile pour des tests.

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

- **Export de vos mails** (solution réaliste) : exportez une copie depuis votre client. Outlook produit un fichier PST ; passez par un outil de conversion vers mbox, fichier `.mbox` (p. ex. via Thunderbird), puis lisez le résultat avec `MboxMailSource(path)`. Aucune connexion, aucun jeton. !!Ce fichier contient de vrais mails : gardez-le en local et supprimez-le après usage.!!
- **IMAP en lecture seule** : `ImapSource(host, user, password_env)` ne convient qu'à une boîte qui accepte encore le mot de passe. Microsoft 365 et Outlook.com n'autorisent plus l'IMAP en authentification simple (il faut OAuth, XOAUTH2, absent du kit). Gmail exige un mot de passe d'application.

!!Dans tous les cas, le reste de votre automatisation ne change pas.!! Seul le connecteur change : c'est le but du contrat `MailSource`.
