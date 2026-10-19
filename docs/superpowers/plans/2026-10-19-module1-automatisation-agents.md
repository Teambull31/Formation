# Module 1 « Automatisation et agents IA » : plan d'implémentation

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Un module de contenu complet (12 leçons sur 4 semaines, boss Bronze, fiche « du perso au pro ») qui mène l'utilisateur de scripts simples à un agent local de synthèse de mails, avec une interface `MailSource` et deux connecteurs prêts à brancher (Outlook / Microsoft 365 et Gmail).

**Architecture:** Le module est un dossier de contenu `content/modules/automation-agents/` au format du plan 1 (`module.json`, leçons Markdown, QCM JSON, TP avec `check.sh`, `boss.json`) : aucun changement du code de l'appli. Le code Python fourni (interface, source fictive, connecteurs) vit dans `connecteurs/` à l'intérieur du module, avec ses propres tests ; l'utilisateur le copie ensuite à son poste de travail. Les TP tournent sur des mails fictifs et un faux serveur d'API local. Les connecteurs réels sont testés ici uniquement avec des transports HTTP simulés.

**Tech Stack:** Python >=3.12 (`uv`), `httpx`, `pytest` (déjà dans `backend/`) ; Ollama `qwen3:14b` pour l'agent ; `msal` (Outlook) et `google-auth-oauthlib` (Gmail) uniquement pour l'usage réel, listés dans `connecteurs/requirements-reel.txt` ; systemd `--user` (Fedora) pour la tâche planifiée.

**Spec:** `docs/superpowers/specs/2026-10-18-formation-gamifiee-design.md`
**Plan précédent (prérequis, socle V1):** `docs/superpowers/plans/2026-10-19-app-core.md`

**Hors de ce plan :** « Veille du jour », modules DevOps, vidéo. Aucun essai sur un compte réel n'est fait par ce plan : il n'y a ni identifiant ni jeton ici.

## Global Constraints

- Interface et contenus en français ; termes techniques en anglais.
- Aucun mail réel, aucun jeton, aucun identifiant dans le dépôt, dans les tests ou dans un prompt à Claude Code. Tous les mails du module sont fictifs.
- Les connecteurs demandent des droits en **lecture seule** (`Mail.Read`, `gmail.readonly`) ; aucun code d'envoi, de suppression ou de déplacement de mail.
- Les jetons mis en cache sont écrits en local avec les droits `0600` et le fichier est dans `.gitignore`.
- La réussite d'un TP se décide par script (`check.sh`), jamais par le LLM ; Qwen ne sert qu'à l'agent enseigné et aux indices, avec repli si Ollama est éteint.
- Les `check.sh` n'agissent que dans le `workspace` du TP : pas de modification du système (le TP « tâche planifiée » vérifie le fichier d'unité avec `systemd-analyze verify`, sans l'activer).
- Chaque TP : 1 à 3 indices progressifs pré-écrits, `timeout_s` <= 60, durée annoncée ≈ 15 min. Chaque leçon : micro-leçon 3-5 min, 5 questions de QCM avec explication et `remedial_lesson_id`.
- Points clés dans les cours : `**gras**` et `!!rouge!!`.
- Le module est produit entièrement par Claude (décision de la spec) ; l'utilisateur relit.
- Le plan ne fixe pas le contenu exact des phrases de cours, seulement ce que chaque fichier doit couvrir et prouver.

## Décisions du concepteur (à vérifier par l'utilisateur)

- **4 semaines, 3 leçons par semaine = 12 leçons** + boss Bronze + fiche. Les jours restants de la semaine servent aux quêtes bonus, au repos ou à un sujet imposé.
- **Outlook** : API Microsoft Graph via `msal`, flux « device code », autorité `consumers` pour le compte personnel ; l'utilisateur enregistre lui-même une application (guide dans la fiche). **Gmail** : API Gmail avec `google-auth-oauthlib` (flux « installed app »), pas d'IMAP avec mot de passe d'application.
- **API de test** : petit serveur local qui imite les réponses paginées de Graph, démarré par les `check.sh` et par le TP, sur `127.0.0.1` avec un port choisi par le script.
- **Source de test** : fichier JSON de 30 mails fictifs (dont des urgents, des newsletters, des pièges comme un faux mail de phishing), plus un mbox de 5 mails pour le TP « écrire son connecteur ».

## Review Focus

- Un connecteur qui oublie la pagination ou renvoie des mails en double : le test de contrat le détecte (tâche 3).
- Un jeton ou un mail réel qui se retrouve dans le dépôt : test qui scanne le module (tâche 9) ; `.gitignore` du cache de jeton (tâche 4).
- Un connecteur qui demande une portée d'écriture : test sur les portées demandées (tâches 4 et 5).
- Ollama éteint pendant le TP de l'agent : le `check.sh` simule un port fermé et exige le repli (tâche 8).
- Un `check.sh` qui boucle ou lance un serveur qui reste actif : coupé par timeout, serveur tué par `trap` (tâches 6 à 8).
- Un module qui ne se charge pas, ou un QCM invalide : `load_module` doit réussir sur le vrai module (tâche 9).

## Structure des fichiers

```
content/modules/automation-agents/
  module.json                         id, titre, skill, 12 leçons
  lessons/s1l1.md … s4l3.md           cours
  lessons/s1l1.qcm.json …             QCM (5 questions chacun)
  lessons/s1l1.tp/tp.json, check.sh   TP (instructions, indices, timeout, workspace)
  boss/boss.json, check_*.sh          boss Bronze : 5 phases-patterns
  fiche-perso-vers-pro.md             fiche « du perso au pro »
  fiche-ecrire-un-connecteur.md       guide pas à pas
  fixtures/mails_fictifs.json         30 mails fictifs
  fixtures/mails_fictifs.mbox         5 mails fictifs
  fixtures/api_test.py                faux serveur Graph paginé
  connecteurs/mail_source.py          interface MailSource + Mail
  connecteurs/fake_source.py          source JSON fictive
  connecteurs/mbox_source.py          exemple de « autre connecteur »
  connecteurs/outlook_graph.py        connecteur Microsoft Graph
  connecteurs/gmail_api.py            connecteur Gmail
  connecteurs/auth_cache.py           cache de jeton 0600
  connecteurs/requirements-reel.txt   msal, google-auth-oauthlib
  connecteurs/tests/                  contrat + un fichier par connecteur
backend/tests/test_module_automation.py   charge et valide le vrai module
```

---

### Task 0: Squelette du module et chargement

**Files:**
- Create: `content/modules/automation-agents/module.json`, `backend/tests/test_module_automation.py`, `.gitignore` (ajout `*.token.json`, `.cache-jeton/`)

**Interfaces:**
- Consumes: `load_module(path) -> Module` (plan 1, tâche 1).
- Produces: `module.json` avec `id = "automation-agents"`, `skill = "automatisation"`, 12 leçons `s1l1`…`s4l3` (titre, `minutes` 30-45) ; le test vérifie id, nombre de leçons et unicité des ids.

- [ ] **Step 1:** Écrire `test_real_module_loads` (id, 12 leçons) et `test_every_lesson_has_5_questions_and_a_tp`. Attendu FAIL (fichiers absents).
- [ ] **Step 2:** Créer `module.json` et des leçons/QCM/TP vides valides (titre seulement) pour que le chargement passe ; les tâches suivantes les remplissent.
- [ ] **Step 3:** `uv run pytest -q` depuis `backend/`. Commit `feat: automation-agents module skeleton`.

### Task 1: Mails fictifs et faux serveur d'API

**Files:**
- Create: `fixtures/mails_fictifs.json`, `fixtures/mails_fictifs.mbox`, `fixtures/api_test.py`, `connecteurs/tests/test_api_test.py`

**Interfaces:**
- Produces: mail = `{id, from, to, subject, received (ISO 8601), body, is_read, importance}` ; `api_test.py` : `make_app(mails, page_size=10)` (WSGI/`http.server`), routes `GET /v1.0/me/messages?$top=&$skip=` au format Graph (`value`, `@odata.nextLink`), `python api_test.py --port 0 --mails <json>` écrit `PORT=<n>` sur stdout.

- [ ] **Step 1:** Tests : 30 mails -> 3 pages de 10, `nextLink` absent à la dernière ; ids uniques ; au moins 5 urgents, 5 newsletters, 1 tentative de phishing, 1 mail avec instructions piégées (« ignore tes consignes… ») pour le TP de garde-fous.
- [ ] **Step 2:** FAIL. **Step 3:** Écrire les fixtures (noms et sociétés inventés) et le serveur. **Step 4:** PASS. Commit `feat: fictitious mails and fake graph api`.

### Task 2: Interface `MailSource` et source fictive

**Files:**
- Create: `connecteurs/mail_source.py`, `connecteurs/fake_source.py`, `connecteurs/tests/test_contract.py`, `connecteurs/tests/test_fake_source.py`

**Interfaces:**
- Produces:
  - `@dataclass(frozen=True) Mail(id, sender, to, subject, received: datetime, body, is_read, importance)`
  - `class MailSource(Protocol)` : `list_mails(since: datetime | None = None, limit: int = 100) -> list[Mail]` (plus récent d'abord, ids uniques) et `close() -> None`
  - `contract_checks(make_source)` : fonctions de test réutilisables par chaque connecteur (ordre décroissant, `limit` respecté, `since` filtré, ids uniques, source vide -> liste vide, aucune méthode d'écriture publique : pas d'attribut `send`, `delete`, `move`).
  - `FakeMailSource(path: Path)`.

- [ ] **Step 1:** Tests du contrat appliqués à `FakeMailSource`. **Step 2:** FAIL. **Step 3:** Implémenter. **Step 4:** PASS. Commit `feat: MailSource interface and fake source`.

### Task 3: Connecteur mbox (« écrire un autre connecteur »)

**Files:**
- Create: `connecteurs/mbox_source.py`, `connecteurs/tests/test_mbox_source.py`, `fiche-ecrire-un-connecteur.md`

**Interfaces:**
- Produces: `MboxSource(path)` conforme à `MailSource` (module `mailbox` de la stdlib) ; la fiche suit pas à pas cet exemple : lire le contrat, copier le test de contrat, implémenter, brancher dans l'agent.

- [ ] **Step 1:** Test de contrat sur `mails_fictifs.mbox` (5 mails). **Step 2:** FAIL. **Step 3:** Implémenter ; la fiche contient le squelette à compléter utilisé par le TP s3l3. **Step 4:** PASS. Commit `feat: mbox connector and connector guide`.

### Task 4: Connecteur Outlook / Microsoft Graph

**Files:**
- Create: `connecteurs/outlook_graph.py`, `connecteurs/auth_cache.py`, `connecteurs/requirements-reel.txt`, `connecteurs/tests/test_outlook_graph.py`, `connecteurs/tests/test_auth_cache.py`

**Interfaces:**
- Produces:
  - `SCOPES = ["Mail.Read"]`
  - `OutlookGraphSource(token_provider: Callable[[], str], base_url="https://graph.microsoft.com/v1.0", client: httpx.Client | None = None)` ; suit `@odata.nextLink` jusqu'à `limit`, convertit en `Mail`, envoie `Authorization: Bearer`, gère 401 (une relance du provider) et 429 (`Retry-After`, deux essais) sans boucle infinie.
  - `device_code_token_provider(client_id: str, authority="https://login.microsoftonline.com/consumers", cache_path: Path) -> Callable[[], str]` (msal importé tardivement : le module se charge sans `msal` installé).
  - `auth_cache.write_secret(path, text)` crée le fichier en `0600` ; `read_secret(path)` refuse un fichier lisible par d'autres.

- [ ] **Step 1: Tests**
```python
def test_contract_against_fake_graph(): contract_checks(lambda: OutlookGraphSource(lambda: "t", base_url=fake_url))
def test_follows_pagination_until_limit(): assert len(src.list_mails(limit=25)) == 25
def test_requests_only_read_scope(): assert SCOPES == ["Mail.Read"]
def test_401_refreshes_token_once_then_raises(): ...
def test_429_waits_retry_after_then_gives_up(): ...
def test_import_without_msal_installed(): importlib.reload(outlook_graph)
def test_cache_file_is_0600(tmp_path): assert oct(stat(p).st_mode & 0o777) == "0o600"
```
- [ ] **Step 2:** FAIL. **Step 3:** Implémenter ; aucun appel réseau réel dans les tests (transport `httpx.MockTransport` ou `api_test.py`). **Step 4:** PASS. Commit `feat: outlook graph connector`.

### Task 5: Connecteur Gmail

**Files:**
- Create: `connecteurs/gmail_api.py`, `connecteurs/tests/test_gmail_api.py`

**Interfaces:**
- Produces: `SCOPES = ["https://www.googleapis.com/auth/gmail.readonly"]` ; `GmailSource(token_provider, base_url="https://gmail.googleapis.com/gmail/v1", client=None)` : `users/me/messages` (liste d'ids paginée par `nextPageToken`) puis `messages/{id}?format=full` ; décode l'expéditeur, le sujet, la date et le corps `text/plain` en base64url ; `installed_app_token_provider(client_secrets: Path, cache_path: Path)` (import tardif de `google-auth-oauthlib`).

- [ ] **Step 1:** Tests : contrat avec un transport simulé ; corps multipart (texte + HTML) -> texte ; pagination par `nextPageToken` ; portée en lecture seule ; pas de `format=raw` ni de requête hors lecture (le transport simulé échoue sur tout verbe autre que GET).
- [ ] **Step 2:** FAIL. **Step 3:** Implémenter. **Step 4:** PASS. Commit `feat: gmail connector`.

### Task 6: Semaine 1, scripts et fichiers (s1l1 à s1l3)

**Files:**
- Create: `lessons/s1l1.*`, `lessons/s1l2.*`, `lessons/s1l3.*` (md, qcm.json, tp/tp.json, tp/check.sh)

Contenu et preuve de chaque TP (`workspace` = dossier du TP, mails = `fixtures/mails_fictifs.json`) :
- **s1l1 Premier script** : lire du JSON, boucler, afficher. TP : `compte.py` affiche le nombre de mails non lus par expéditeur. `check.sh` lance le script et compare la sortie à la valeur attendue calculée par `jq`.
- **s1l2 Trier et filtrer** : filtres, tri, `csv`. TP : `urgents.csv` (colonnes `date,expediteur,sujet`) trié du plus récent au plus ancien. `check.sh` compare avec un CSV attendu.
- **s1l3 Secrets et configuration** : variables d'environnement, fichier `0600`, ne jamais coder un jeton. TP : `config.py` lit `MAIL_SOURCE` et `TOKEN_FILE` ; le script refuse un fichier de jeton lisible par tous. `check.sh` crée un jeton `0644` et exige le refus, puis un `0600` et exige l'acceptation, et `grep` qu'aucune chaîne ressemblant à un jeton n'est dans le code.

- [ ] **Step 1:** Pour chaque leçon, écrire d'abord `check.sh` et vérifier qu'il **échoue** sur un dossier vide, puis qu'il **réussit** sur une solution de référence rangée dans `lessons/sXlY.tp/solution/` (non montrée à l'utilisateur ; le test de la tâche 9 l'utilise).
- [ ] **Step 2:** Rédiger cours (points clés en gras/rouge), 5 questions de QCM (une sur chaque notion, explications qui disent pourquoi), 3 indices. **Step 3:** Commit `feat: automation module week 1`.

### Task 7: Semaine 2, tâches planifiées et API (s2l1 à s2l3)

**Files:**
- Create: `lessons/s2l1.*` à `lessons/s2l3.*`

- **s2l1 Tâche planifiée** : `systemd --user` (service + timer), journal, cron en comparaison. TP : `digest.service` et `digest.timer` (tous les jours à 07:00, `Persistent=true`). `check.sh` : `systemd-analyze verify` sur les deux fichiers et `grep` des clés ; **n'active rien**.
- **s2l2 Appeler une API** : `httpx`, codes HTTP, JSON, pagination, délais d'attente. TP : `recupere.py` récupère tous les mails via le faux serveur Graph (3 pages) et écrit `mails.json`. `check.sh` démarre `api_test.py`, lance le script, compte 30 mails, tue le serveur (`trap`).
- **s2l3 Jetons, portées et erreurs** : OAuth en bref, portée minimale, 401/429, relance limitée. TP : ajouter au script la gestion de 401 (un seul nouvel essai) et 429 (`Retry-After`). `check.sh` utilise un faux serveur qui répond 429 puis 200, et un autre qui répond toujours 401 (le script doit s'arrêter avec un code non nul, sans boucle).

- [ ] **Step 1:** Même méthode que la tâche 6 (check qui échoue, solution de référence qui passe). **Step 2:** Rédiger. **Step 3:** Commit `feat: automation module week 2`.

### Task 8: Semaines 3 et 4, connecteurs, workflow et agent (s3l1 à s4l3)

**Files:**
- Create: `lessons/s3l1.*` à `lessons/s4l3.*`

- **s3l1 L'interface `MailSource`** : pourquoi une interface (changer de source sans toucher l'agent). TP : écrire `ma_source.py` (`MySource`) qui passe `contract_checks` sur le JSON fictif.
- **s3l2 Le connecteur Outlook** : lire `outlook_graph.py`, champs Graph, pagination, lecture seule. TP : brancher `OutlookGraphSource` sur le faux serveur et produire `resume_brut.txt` (sujet de chaque mail non lu). Le passage au vrai compte est décrit dans la fiche, pas dans le `check.sh`.
- **s3l3 Écrire son propre connecteur** : suivre `fiche-ecrire-un-connecteur.md`. TP : compléter le squelette d'une source `mbox` sans l'aide de `mbox_source.py`. `check.sh` lance le test de contrat.
- **s4l1 Un workflow** : étapes idempotentes, journal, code déterministe d'abord, IA seulement où il faut. TP : `digest.py` enchaîne source -> filtre -> rapport Markdown `rapport.md`, relançable sans doublon.
- **s4l2 Un agent local** : appel d'Ollama (`/api/chat`, `qwen3:14b`), sortie JSON demandée puis validée, délai d'attente, repli. TP : ajouter à `digest.py` un résumé par mail. `check.sh` lance avec `OLLAMA_URL` sur un port fermé : le rapport doit exister avec le repli (sujet + premiers mots), et avec un faux Ollama qui renvoie du JSON invalide : le script doit rejeter la réponse et utiliser le repli.
- **s4l3 Garde-fous d'un agent qui agit** : lecture seule, validation humaine avant toute action, journal, limite d'actions, **mails qui donnent des ordres à l'agent** (injection). TP : outil « marquer à traiter » qui écrit dans `a_traiter.json` uniquement après confirmation (`--oui`) et ignore les instructions du mail piégé. `check.sh` vérifie : rien d'écrit sans `--oui`, le mail piégé n'a déclenché aucune action, le journal existe.

- [ ] **Step 1:** Pour chacune des six leçons : `check.sh` d'abord (échec sur dossier vide), puis solution de référence qui passe. **Step 2:** Rédiger cours, QCM (5 questions), 3 indices. **Step 3:** Commit `feat: automation module weeks 3 and 4`.

### Task 9: Boss Bronze, fiche « du perso au pro » et validation du module

**Files:**
- Create: `boss/boss.json`, `boss/check_*.sh`, `fiche-perso-vers-pro.md`, `lessons/*.tp/solution/` (déjà créés), `backend/tests/test_module_automation.py` (compléter), `README.md` (section module 1)

**Interfaces:**
- Produces: `boss.json` = `{id: "bronze-digest", title: "Digest matinal", phases: [{pattern_id, label, check, remedial_lesson_id}]}` (format du plan 1, tâche 9), avec 5 phases :
  1. `secret-dans-le-code` : aucun jeton dans le dépôt de l'utilisateur -> s1l3
  2. `pas-de-timeout` : le script a un délai d'attente sur chaque appel -> s2l3
  3. `source-codee-en-dur` : l'agent passe par `MailSource`, change de source par configuration -> s3l1
  4. `reponse-llm-non-validee` : repli prouvé comme en s4l2 -> s4l2
  5. `action-sans-garde-fou` : rien n'est fait sans confirmation, mail piégé ignoré, `README.md` avec sections Installation, Configuration, Limites, Tâche planifiée -> s4l3
- La fiche `fiche-perso-vers-pro.md` : liste de contrôle de ce qui change pour un compte d'entreprise — enregistrement de l'application dans l'annuaire de l'entreprise, consentement administrateur, droits d'accès aux mails (délégués ou application), règles d'accès conditionnel, accord du service informatique, où l'agent tourne (poste de travail, jamais le PC perso), conservation des journaux, équivalent Google Workspace pour Gmail. Elle dit explicitement ce que l'appli ne tranche pas et que la connexion au compte pro se fait au travail, jamais depuis l'appli d'entraînement.

- [ ] **Step 1: Tests** (dans `test_module_automation.py`)
```python
def test_every_check_fails_on_empty_workspace_and_passes_on_reference(tmp_path): ...  # lance chaque check.sh via run_check (plan 1)
def test_boss_phases_point_to_existing_lessons(): ...
def test_no_secret_or_real_looking_address_in_module(): ...  # scanne le module : jetons, @gmail.com / @outlook.com réels, domaines non fictifs
def test_fiche_mentions_all_enterprise_changes(): ...  # les cinq points de la spec
```
- [ ] **Step 2:** FAIL. **Step 3:** Écrire boss, fiche, README ; faire passer les tests. **Step 4:** `uv run pytest -q` (backend + connecteurs : `uv run pytest ../content/modules/automation-agents/connecteurs/tests`). Commit `feat: bronze boss, personal-to-pro sheet and module validation`.

### Task 10: Vérification de bout en bout

- [ ] **Step 1:** Démarrer l'appli avec le vrai module : `GET /api/quest/today` propose s1l1 ; `POST /api/weekly/import` accepte le dossier ; le boss s'affiche avec ses 5 patterns.
- [ ] **Step 2:** Rejouer s1l1 -> s1l3 dans le terminal intégré avec les solutions de référence : les trois TP passent, XP et série avancent.
- [ ] **Step 3:** Écrire dans le README du module les essais réels à faire par l'utilisateur seul (Outlook personnel : enregistrement de l'application, `device_code_token_provider`, lancement de `digest.py` sur son compte), en rappelant que le contenu des mails ne quitte pas le PC et ne va jamais à Claude. Commit `docs: module 1 real-account checklist`.

## Questions pour l'utilisateur avant l'exécution

- 4 semaines et 3 leçons par semaine conviennent-elles, ou préférez-vous un module plus court ou plus long ?
- Gmail par OAuth (choix retenu) ou par IMAP avec mot de passe d'application (plus simple, moins propre) ?
- Les tâches répétitives réelles du travail ne sont pas encore listées : elles pourront devenir des TP supplémentaires dans une version 1.1.
