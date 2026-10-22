# Module 1 : Automatisation et agents IA (auto1)

12 leçons (25 min chacune) et un boss, sur 3 semaines. Chaque leçon : cours audio/texte, QCM, TP avec contrôle scripté. Tout tourne sur votre PC.

## Parcours

| Semaine | Leçons | Thème |
|---|---|---|
| 1 | l01 à l04 | Scripts shell fiables, cron/timers, appeler une API, JSON |
| 2 | l05 à l08 | Source de mails derrière une interface, Ollama, résumés, injection de prompt |
| 3 | l09 à l12 + boss | Boucle d'agent, connecteur Outlook, Gmail/IMAP, digest quotidien idempotent, boss « La boîte de réception piégée » |

Le boss (3 phases : injection, idempotence, résilience quand Ollama est en panne) lance votre `l12/quotidien.py`. Terminez donc le TP 12 avant de le défier.

## Prérequis

- Linux/macOS avec bash, Python 3.12+ (la bibliothèque standard suffit pour les TP).
- L'appli de formation lancée (voir le README racine) : le module auto1 se charge par défaut depuis le `content/` du dépôt. Si vous définissez `FORMATION_CONTENT`, depuis `backend/` utilisez `../content`.
- Optionnel : Ollama (modèle par défaut `qwen3:14b`, changez-le avec `OLLAMA_MODEL`) pour les indices et explications d'erreurs. Les TP utilisent des faux serveurs locaux (Graph, Gmail, Ollama), donc Ollama réel n'est pas requis pour valider un TP.

## Le kit (`kit/`)

Copié dans votre espace de travail par les TP : `mail_source.py` (interface), `imap_source.py`, `outlook_graph.py`, `gmail_api.py`, `llm.py`, des faux serveurs (`mock_graph.py`, `mock_gmail.py`, `mock_ollama.py`), des mails fictifs en `@example.test` (`fixtures/`), et deux fiches : `FICHE_ecrire_un_connecteur.md` et `FICHE_perso_vers_pro.md`.

## Règle de confidentialité

!!Les vrais mails restent en local.!! Aucun contenu de mail réel n'est envoyé à Claude ni à un service externe : le connecteur lit, votre script trie, avec Ollama sur votre machine. Les journaux ne contiennent que des compteurs. Le compte professionnel se branche au travail, jamais depuis l'appli d'entraînement.

## Essai réel (facultatif, après l10/l11)

- **Outlook perso** (outlook.com, hotmail.com) : inscrivez une application dans le portail Microsoft Entra, type « comptes Microsoft personnels uniquement » (tenant `consumers`), puis suivez `kit/FICHE_perso_vers_pro.md`. Libellés Microsoft susceptibles de changer.
- **Gmail** : créez un projet Google Cloud et un identifiant OAuth (application de bureau), droit en lecture seule, puis utilisez `kit/gmail_api.py` (voir la leçon 11 et la fiche).
- Commencez toujours par des lectures seules, sur un dossier de test.

## Non vérifié

Le module est validé de bout en bout contre des faux serveurs. Ces points n'ont **pas** été vérifiés en réel :

- un vrai essai Outlook perso (inscription d'application, consentement, jeton) ;
- Ollama réel avec d'autres modèles que ceux essayés : le kit envoie `think: false` et lit `OLLAMA_MODEL`, mais un modèle froid peut mettre plus de 60 s (réchauffez-le d'abord ou augmentez `OLLAMA_TIMEOUT`) ;
- l'usage sur téléphone (terminal, vérification et boss sont réservés au PC) ;
- une vraie inscription d'application Microsoft ou Google.
