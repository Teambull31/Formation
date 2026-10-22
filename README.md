# Formation

Application d'entraînement gamifiée : quêtes quotidiennes, leçons audio, QCM, TP avec terminal intégré, boss, gacha.
Backend FastAPI (`backend/`), frontend React (`frontend/`).

## Prérequis

- Python 3.12+ et [uv](https://docs.astral.sh/uv/)
- Node.js et npm
- `espeak-ng` (lecture audio des leçons)
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
- `FORMATION_CONTENT` : contenu (défaut `content/` du dépôt, qui ne contient que `gacha.json`)

Sans module dans `<FORMATION_CONTENT>/modules/`, la quête est vide : importez un module (voir « Rituel du dimanche ») ou copiez `backend/tests/fixtures/demo_module` dans `<FORMATION_CONTENT>/modules/demo`.

## Module 1 : Automatisation et agents IA

Disponible dans `content/modules/auto1` (12 leçons, boss `auto1_boss`). Pour le charger :

```bash
cd backend
FORMATION_CONTENT=../content uv run uvicorn app.main:app_factory --factory --host 0.0.0.0 --port 8000
```

Parcours et mode d'emploi : `content/modules/auto1/README.md`. Non vérifié en réel : essai Outlook perso, Ollama réel `qwen3:14b` (délais à froid, texte de raisonnement cassant le JSON), téléphone, inscription d'application Microsoft/Google (tout est validé contre des faux serveurs).

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
    module.json                 id, title, skill, lessons[{id, title, minutes}]
    lessons/<leçon>.md          cours (**gras**, !!rouge!! pour l'essentiel)
    lessons/<leçon>.qcm.json    questions (answer = index de la bonne option)
    lessons/<leçon>.tp/tp.json  TP (id, title, instructions_md, check, hints, timeout_s, workspace)
    lessons/<leçon>.tp/check.sh vérification scriptée
```

Exemple complet : `backend/tests/fixtures/demo_module`.

## Tests

```bash
cd backend && uv run pytest -q
cd frontend && npm test -- --run
```
