# Formation

Application d'entraînement gamifiée : quêtes quotidiennes, leçons audio, QCM, TP avec terminal intégré, boss, gacha.
Backend FastAPI (`backend/`), frontend React (`frontend/`).

## Prérequis

- Python 3.12+ et [uv](https://docs.astral.sh/uv/)
- Node.js et npm
- Audio des leçons : voix neuronale Microsoft via `edge-tts` (en ligne, installé avec le backend, le texte de la leçon est envoyé à Microsoft) ; `espeak-ng` sert de repli hors ligne. `FORMATION_TTS=espeak` force espeak, `FORMATION_TTS_VOICE` change la voix (défaut `fr-FR-VivienneMultilingualNeural`)
- Optionnel : [Ollama](https://ollama.com) avec le modèle `qwen3:14b` (indices et explications d'erreurs ; sans lui, le texte pré-écrit est affiché)

## Installation

```bash
cd backend && uv sync
cd ../frontend && npm install && npm run build
```

## Lancement

```bash
cd backend
uv run uvicorn app.main:app_factory --factory --host 0.0.0.0 --port 8000
```

Puis ouvrir http://localhost:8000. Le backend sert le frontend construit (`frontend/dist`).

Variables d'environnement optionnelles (par défaut sous `~/.formation`) :

- `FORMATION_DB` : base SQLite (défaut `~/.formation/formation.db`)
- `FORMATION_WORKSPACE` : répertoire de travail des TP et du terminal (défaut `~/.formation/workspace`)
- `FORMATION_CONTENT` : contenu (défaut `content/` du dépôt : module auto1 et son boss)

Le module auto1 se charge par défaut. Avec un `FORMATION_CONTENT` sans module, la quête est vide : importez un module (voir « Rituel du dimanche ») ou copiez `backend/tests/fixtures/demo_module` dans `<FORMATION_CONTENT>/modules/demo`.

## Module 1 : Automatisation et agents IA

Disponible dans `content/modules/auto1` (12 leçons, boss `auto1_boss`). Il se charge par défaut avec la commande de lancement ci-dessus (contenu = `content/` du dépôt).

Parcours et mode d'emploi : `content/modules/auto1/README.md`. Non vérifié en réel : essai Outlook perso, Ollama réel (le kit envoie `think: false` ; modèle choisi par `OLLAMA_MODEL`, défaut `qwen3:14b` ; un modèle à froid peut dépasser 60 s, voir `OLLAMA_TIMEOUT`), téléphone, inscription d'application Microsoft/Google (tout est validé contre des faux serveurs).

## Accès téléphone

Sur le même réseau : `http://<ip-du-pc>:8000`. Quête, leçons, QCM, audio, équipe et boss (consultation) fonctionnent.

Limites : le terminal, « Vérifier », « Défier », l'import de module et les indices sont réservés au PC (requêtes locales uniquement).
Ne passez pas par un proxy inverse pour `/ws/terminal` : le terminal est refusé s'il ne vient pas directement de la machine.

Avertissement sécurité : le terminal donne un shell sur le PC. N'exposez le port 8000 que sur un réseau domestique de confiance.

## Rituel du dimanche

Onglet « Semaine » (Préparation de la semaine) :

1. Saisir le sujet et le format, puis générer le brief.
2. Coller le brief dans Claude Code, qui produit un dossier de module.
3. Importer le module produit (chemin du dossier, depuis le PC) ; les erreurs de structure sont listées.
4. Relire le contenu importé avant de commencer la semaine.

## Contenu des modules

```
<FORMATION_CONTENT>/
  gacha.json                    récompenses du gacha
  boss/<id>/boss.json           boss (phases)
  modules/<id>/
    module.json                 id, title, skill, lessons[{id, title, minutes}], order (rang, défaut 100)
    fiche.md                    fiche de révision téléchargeable (facultative)
    lessons/<leçon>.md          cours (**gras**, !!rouge!! pour l'essentiel)
    lessons/<leçon>.qcm.json    questions (answer = index de la bonne option)
    lessons/<leçon>.tp/tp.json  TP (id, title, instructions_md, check, hints, timeout_s, workspace)
    lessons/<leçon>.tp/check.sh vérification scriptée
```

Exemple complet : `backend/tests/fixtures/demo_module`.

## Parcours DevOps en 30 jours

Les modules DevOps passent en tête de la quête (`order` dans `module.json`) : **CI/CD** (7 leçons), **Docker** (4), **Kubernetes** (7), **Terraform** (7), **Ansible** (7), chacun avec son boss, puis le **projet fil rouge** (5 étapes). Chaque leçon = cours audio, 5 QCM, un TP vérifié dans le terminal ; chaque leçon finit par un « Labo réel » optionnel.

- **Plan sur 30 jours** : carte en tête de l'onglet Quête (`content/plan.json`, `GET /api/plan`). « Commencer aujourd'hui » fixe le jour 1 ; le jour courant, les jours faits et le retard s'affichent, et le rappel push du jour cite le titre du jour.
- **Répare la panne** : ci7 (pipeline rouge), dk4 (pile qui ne repart pas), k6 (garde de nuit), tf7 (plan destructeur), an7 (parc qui dérape). Chaque TP donne des journaux d'incident, un `diagnostic.yaml` à remplir et des fichiers cassés à réparer.
- **Projet fil rouge** (`projet`, pr1 à pr5) : une API livrée dans un seul dépôt GitHub, avec CI, image ghcr.io, Kubernetes, Terraform, Ansible et README. Chaque étape revérifie les précédentes (dossier de TP `fil-rouge/`).
- **Labo réel** : bouton « Vrais outils » sur les TP DevOps (`content/modules/<id>/lessons/_real.sh`, `POST /api/tp/<id>/real`, réservé à la machine locale). Il lance ce qui est installé : actionlint, hadolint ou `docker compose config`, kubeconform ou `kubectl` (cluster kind), `terraform init -backend=false && validate`, `ansible-playbook --syntax-check`. Un outil absent est signalé avec sa commande d'installation.
- **Révisions** : quatre onglets. Questions : les QCM ratés en boîtes Leitner. Cartes : les pièges `!!` et termes `**` des leçons terminées, 10 nouvelles par jour. Examen : 15 questions de tout le module, chronométrées, réussite à 80 %. Entretien : 29 questions notées.
- Boss Terraform : 6 phases (tf1 à tf6, dossiers `tfboss/`, `tfboss-boucles/`, `tfboss-module/`, `tfboss-ci/`).

**Fiches de révision** : onglet Leçons, bouton « Fiche de révision ⬇ » par module ou « Télécharger toutes les fiches ». Le fichier HTML est autonome : il s'ouvre hors ligne sur téléphone et s'imprime en PDF depuis le navigateur. Source : `content/modules/<id>/fiche.md` (servie par `GET /api/fiche/<id>`).

## Parcours domotique ESP-IDF

Les modules `esp1` à `esp4` enseignent le C++ d'ESP-IDF (GPIO, FreeRTOS, Wi-Fi, MQTT sur TLS, OTA, retour arrière) sur un
contrôleur de piscine, contre un **simulateur** (`content/esp/sim/`) : aucune carte n'est nécessaire, le temps est virtuel et le
simulateur simplifie le matériel (chaque leçon dit ce qu'il simplifie). Les TP C++ et le boss final sont `local_only` : ils ne se
notent que depuis la machine locale. Ils exigent `g++`, `bwrap` (bubblewrap) et `openssl` (certificat de test des TP es10 à es12 et
des phases 2 et 3 du boss), absents de l'image Docker. Avec `FORMATION_REMOTE_EXEC=1`, le terminal distant (`/ws/terminal`) permet
encore de compiler et d'exécuter du C++ ; la garde `local_only` ne protège que la notation. Voir `DEPLOY.md`.

## Tests

```bash
cd backend && uv run pytest -q
cd frontend && npm test -- --run
```

## Déploiement

Mot de passe, Docker, HTTPS, Tailscale, sauvegarde et mise à jour : voir [DEPLOY.md](DEPLOY.md).
