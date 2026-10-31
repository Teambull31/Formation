# Backlog

Idées retenues, pas encore planifiées. Source : branche `claude/ecstatic-sagan-9wq8qv` (projet parallèle QuestForge) et sessions précédentes.

## À faire ensuite
- **Arène de révision (Leitner)** : écran qui présente les questions dues (le backend programme déjà les révisions, aucun écran ne les montre).
- **Export Anki** des cartes de révision.

## Noté pour plus tard
- **Simulateur d'entretien, suite** : la v1 est livrée (15 questions fixes, notation Ollama ou repli par mots-clés). Idées : questions générées par Ollama, réponse à l'oral (reconnaissance vocale), entretien chronométré de 5 questions d'affilée.

## Écarté pour l'instant
- Simulateur de SLO, post-mortem, War Room, duels, ligues : fonctions simulées dans le navigateur, sans valeur pédagogique prouvée.

## Déjà parqué (app-core)
- Pas de fiche de révision imprimable ; le rang n'est pas lié au boss ; pas de mini-cours pour un sujet imposé ; le QCM donne 40 XP même si tout est faux  ; « Veille du jour » (plan à part) ; modules DevOps ; vidéo.
- Déploiement : images Docker en tags flottants (digests non figés : impossible de distinguer l'index multi-arch d'un manifeste unique avec podman, à faire avec `docker buildx imagetools inspect`) ; `docker compose` et Caddy jamais lancés (l'image, elle, a été construite et lancée avec podman : 401/200/403 et healthcheck OK).

## Domotique ESP-IDF
- **Ouverture à distance des TP C++ et du boss ESP** (`local_only` aujourd'hui). Blocages à lever d'abord : plafond cgroup de mémoire et de processus (pids) ; filtre seccomp ; tests du bac à sable exécutés sur le VPS avec `ESP_SANDBOX_REQUIRED=1` ; bwrap en version 0.10 ou plus ; restriction des espaces de noms utilisateur par AppArmor ; intégrité de la trace (la frontière réelle est là : un programme d'apprenant peut falsifier la trace, résidu documenté de la Task 5) ; pire cas mémoire du bac à sable (12 processus × 256 Mo, L2). À faire dans un changement séparé, après l'exécution des tests du bac à sable en production.
- **Portfolio ESP** : les modules esp1 à esp4 ne sont pas exportés en v1 (ruling M1), car `leak_reason` laisse passer des formes C courantes d'identifiants. À durcir pour le C : crochets `[]`, initialisation par accolades, `strcpy((char*)cfg.sta.password, "…")`, `#define *_PWD` et `*_MDP`, valeur contenant une espace, certificat PEM collé, `cfg.password = hunter;`. Ensuite, activer `"portfolio": true`, et faire viser esp4 aux tests `test_es10/11/12_solution_passes_the_export`. L'export ne couvre pas le dossier de travail du boss.
- **Second projet** : finir le dépôt `Domotique` (Teambull31/Domotique) avec des revues ECC, seulement sur demande du porteur.
- **Options futures** : MicroPython et Arduino.
- **Dette reportée** (reprise du registre de la tranche) :
  - lint de la Task 5 (points mineurs) ;
  - `parse_header` : valeur par défaut en ligne ;
  - `gpio_get_level` en mode INPUT_OUTPUT ;
  - planning codé en dur qui fait passer es4 à es6 ;
  - L5 : helpers dupliqués restants ;
  - L7 : la trace est analysée avant le contrôle de troncature ;
  - pas de test de dérive pour es7 ;
  - L6 et m6 : des tests modifient `sys.modules` et `sys.path` ;
  - détection du PEM dans un corps DER ;
  - état otadata UNDEFINED inatteignable ;
  - `ESP_ERROR_CHECK_WITHOUT_ABORT` absent du simulateur ;
  - m3, m4, m6 et m8 de la Task 22 (voir `progress.md`) ;
  - es11 lit la version dans le nom de fichier de l'URL ;
  - boss m4 : une compilation par exécution, le budget `WALL_S` de 40 s est à surveiller sur une machine lente ;
  - boss m5 : p3 modifie les tables de p2 à l'import ;
  - boss m8 : consignes non contrôlées à part ;
  - pas de test frontend de l'écran Boss (`tsc` et `vitest` non lancés) ;
  - trois commits portent le trailer Opus (6c09248, 41207c6, 76652ac) : poser la question au porteur avant tout amend ou merge.
- **Simulateur** : le NVS exige `nvs_commit` (plus strict que le vrai ESP-IDF, ruling M1 de la Task 15) ; un seul cas « carte flashée par câble » est modélisé alors que le résultat réel dépend de la table de partitions ; `esp_wifi_init` sans NVS renvoie `ESP_ERR_NVS_NOT_INITIALIZED`.
