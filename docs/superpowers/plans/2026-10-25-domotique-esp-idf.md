# Parcours domotique ESP-IDF (simulé) Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Ajouter à Formation 4 modules de 3 leçons (domotique ESP32 en C++17 / ESP-IDF) plus un boss, dont les TP compilent et exécutent le code de l'apprenant contre un faux ESP-IDF déterministe, dans un sandbox.

**Architecture:** Un simulateur partagé sous `content/esp/` (bibliothèque C++ à temps virtuel avec ordonnanceur à passage de témoin, qui écrit une trace JSON ligne par ligne) est compilé une fois puis lié au code de l'apprenant. Un pilote Python (`content/esp/esp_check.py`) lance compilation et exécution dans `bwrap`, lit la trace et applique des vérifications propres à chaque TP (`content/esp/checks/<tp_id>.py`). Les TP C++ sont marqués `local_only` : refusés en exécution distante.

**Tech Stack:** C++17 (`g++` 15 sur le VPS), Python 3 stdlib (`-I -B`), `bwrap`, FastAPI/pytest existants, contenu Markdown/JSON au format des modules existants.

**Spec:** `docs/superpowers/specs/2026-10-25-domotique-esp-idf-design.md`

## Global Constraints

- Contenu en français avec accents ; identifiants de code et termes techniques en anglais.
- C++ compilé avec `-std=c++17`. Signatures et codes de retour conformes à ESP-IDF v5.x (dernière 5.x stable connue), API actuelles : ADC oneshot, pilote I2C maître nouvelle génération ; chaque signature vérifiée dans la documentation officielle.
- Format des modules existants : `module.json` (`id`, `title`, `skill`, `lessons[{id,title,minutes}]`, `portfolio: true`), `lessons/<id>.md`, `<id>.qcm.json`, `<id>.tp/{tp.json,check.sh,solution.sh,seed/}` ; boss dans `content/boss/<id>/` (`boss.json`, `phaseN_check.sh`, `phaseN_solution.sh`).
- Règles du validateur (`backend/tests/test_shipped_modules.py`) : exactement 5 questions QCM par leçon, chacune avec `explain` non vide et `remedial_lesson_id` dans le module ; au moins 3 paires `**…**` et 3 paires `!!…!!` hors code ; au moins 3 indices ; `timeout_s` ≤ 60 ; `solution.sh` présent ; le contrôle échoue sur le `seed` et réussit après `solution.sh` ; seules les adresses `@example.test` sont admises ; pas de lien symbolique dans `seed`.
- Identifiants (module, leçon, TP) : `[A-Za-z0-9_-]+`. Modules `esp1`…`esp4`, leçons `es1`…`es12`, TP `es1-tp`…`es12-tp`, boss `esp_boss`, `skill` : `esp32`.
- Les contrôles affichent `ECHEC : <cause en français> (relire : <section de la leçon>)` et sortent en code 1 ; `OK` en cas de succès (même convention que `_secu_check.py`).
- Les TP C++ sont `local_only` : refus 403 en exécution distante, même avec `FORMATION_REMOTE_EXEC=1`. L'ouverture à distance est un changement séparé, hors de ce plan.
- Aucun certificat, clé ni mot de passe réel ou plausible dans le contenu : les certificats de test sont générés à l'exécution dans le dossier de travail du TP.
- La suite de tests du backend (625 tests au départ) reste verte à chaque commit : `cd backend && uv run pytest -q`.

## Review Focus

Entrées que la spec laisse sous silence et qui peuvent casser le logiciel, par ordre de probabilité. Chacune a son test dans la tâche indiquée.

1. Le code de l'apprenant n'a pas `app_main`, définit `main`, ou ne compile pas : message clair, jamais de trace brute du compilateur sans résumé (Task 5).
2. Le code contourne le temps virtuel (`std::this_thread::sleep_for`, `usleep`, `std::thread`, `time`) : refusé avec un message qui dit d'utiliser `vTaskDelay` / les tâches FreeRTOS (Task 5).
3. Programme qui plante (SIGSEGV, `abort`) ou qui inonde la sortie : « le programme s'est arrêté brutalement (signal …) », sortie tronquée à une taille bornée (Tasks 3 et 5).
4. Deux contrôles simultanés (téléphone et portable) : le cache de la bibliothèque du simulateur ne se corrompt pas, deux dossiers de travail ne se mélangent pas (Task 1).
5. Fichier source non UTF-8, énorme ou lien symbolique : refus lisible (Task 5).

---

## Fichiers

- `content/esp/sim/include/…` : faux en-têtes ESP-IDF (un par en-tête réel). `content/esp/sim/src/*.cpp` : implémentation. `content/esp/sim/signatures.json` : tableau signature ↔ source officielle.
- `content/esp/sim/build.py` : compile et met en cache `libespsim.a`.
- `content/esp/sandbox.py` : exécution dans `bwrap` avec limites.
- `content/esp/esp_check.py` : pilote (analyse statique, compilation, exécution, trace, vérifications). `content/esp/checks/<tp_id>.py` : `SCENARIO` et `verify`.
- `content/modules/esp1…esp4/`, `content/boss/esp_boss/` : contenu pédagogique.
- `backend/app/content.py`, `backend/app/main.py`, `backend/app/boss.py` : drapeau `local_only`.
- Tests : `backend/tests/test_esp_sim.py`, `test_esp_sandbox.py`, `test_esp_check.py` (un fichier par tranche au besoin), `test_local_only.py`.

---

# Tranche 1 : simulateur, sandbox, garde-fou, module 1

### Task 1: Cœur du simulateur (temps virtuel, tâches, journaux)

**Files:**
- Create: `content/esp/sim/include/{esp_err.h,esp_log.h,esp_timer.h,freertos/FreeRTOS.h,freertos/task.h}`, `content/esp/sim/src/{core.cpp,sched.cpp,trace.cpp}`, `content/esp/sim/build.py`
- Test: `backend/tests/test_esp_sim.py`

**Interfaces:**
- Produces: `build.build_sim() -> Path` (dossier contenant `libespsim.a` et `include/`), construit une seule fois par empreinte du contenu de `sim/`, dans `$TMPDIR/formation-espsim-<hash>`, écriture atomique (dossier temporaire puis `rename`). Le programme final est lié avec `libespsim.a` et accepte `--scenario <fichier.json> --max-ms <int>` ; la sortie standard est la trace, un objet JSON par ligne : `{"t_ms": int, "ev": str, …}`. Événements de cette tâche : `log` (`level` `"I"|"W"|"E"|"D"`, `tag`, `msg`), `task_create` (`name`), `end` (`reason`: `"deadline"|"abort"|"busy_loop"|"crash"`).
- Produces (API simulée, signatures ESP-IDF réelles) : `ESP_LOGI/W/E/D(tag, fmt, …)`, `esp_err_t`, `ESP_OK`, `ESP_FAIL`, `ESP_ERROR_CHECK`, `esp_err_to_name`, `xTaskCreate`, `vTaskDelay`, `vTaskDelete`, `xTaskGetTickCount`, `pdMS_TO_TICKS`, `portTICK_PERIOD_MS`, `esp_timer_get_time`. Tick à 100 Hz (valeur par défaut d'ESP-IDF).

- [ ] **Step 1: Write the failing tests** dans `test_esp_sim.py`, avec un utilitaire `compile_and_run(src: str, max_ms: int) -> list[dict]` qui compile avec `g++ -std=c++17` et exécute (sans sandbox à ce stade) : `test_virtual_time_is_fast` (`vTaskDelay(pdMS_TO_TICKS(600000))` puis `ESP_LOGI` : événement à `t_ms == 600000`, exécution réelle < 2 s), `test_two_tasks_interleave_deterministically` (deux tâches qui journalisent chacune toutes les 100 ms et 150 ms : trace identique sur 5 exécutions et ordre égal à celui attendu au tick près), `test_busy_loop_is_reported` (`for(;;){}` sans `vTaskDelay` : dernier événement `end` avec `reason == "busy_loop"`, en moins de 5 s réelles), `test_build_cache_is_atomic_under_concurrency` (4 appels simultanés à `build_sim()` renvoient le même dossier, bibliothèque valide), `test_esp_error_check_aborts_with_name` (`ESP_ERROR_CHECK(ESP_FAIL)` : `end` avec `reason == "abort"` et un `log` `E` contenant `ESP_FAIL`).
- [ ] **Step 2: Run** `cd backend && uv run pytest tests/test_esp_sim.py -q` ; expected: FAIL (modules absents).
- [ ] **Step 3: Implement** le simulateur. Choix imposés par le design : vrais `std::thread`, un seul exécuté à la fois (passage de témoin), horloge virtuelle qui avance quand toutes les tâches attendent ; une tranche d'exécution sans appel bloquant au-delà d'une limite de temps réel déclenche `busy_loop` ; le harnais fournit `main` et appelle `extern "C" void app_main()` dans une tâche. Vérifier chaque signature dans la documentation officielle et la consigner (Task 6).
- [ ] **Step 4: Run** les tests ; expected: PASS.
- [ ] **Step 5: Commit** `feat(esp): cœur du simulateur ESP-IDF (temps virtuel, tâches, journaux)`.

### Task 2: GPIO et scénario d'entrées

**Files:**
- Create: `content/esp/sim/include/driver/gpio.h`, `content/esp/sim/src/gpio.cpp`
- Modify: `content/esp/sim/src/core.cpp` (lecture du scénario)
- Test: `backend/tests/test_esp_sim.py`

**Interfaces:**
- Consumes: Task 1.
- Produces: `gpio_config_t`, `gpio_config`, `gpio_set_direction`, `gpio_set_pull_mode`, `gpio_set_level`, `gpio_get_level`, `GPIO_MODE_INPUT/OUTPUT`, `GPIO_PULLUP_ENABLE`…, `gpio_num_t`. Événements : `gpio_config` (`pin`, `mode`, `pull_up`), `gpio_set` (`pin`, `level`). Scénario JSON : `{"gpio_in": [{"t_ms": int, "pin": int, "level": 0|1}]}` ; une broche d'entrée sans pull-up configuré et sans entrée scénario lit `0` (flottante simulée de façon déterministe) ; avec pull-up, elle lit `1` jusqu'à la première entrée scénario.

- [ ] **Step 1: Write the failing tests** : `test_gpio_output_traced` (deux `gpio_set_level` produisent deux événements `gpio_set` aux bons `t_ms`), `test_gpio_input_follows_scenario` (lecture à `t_ms=1000` et `1005` selon `gpio_in`), `test_floating_input_reads_zero_without_pullup`, `test_pullup_input_reads_one_by_default`.
- [ ] **Step 2: Run** ; expected: FAIL.
- [ ] **Step 3: Implement** `gpio.cpp` et la lecture de `--scenario` (JSON minimal sans dépendance : écrire un petit lecteur ; pas de bibliothèque externe).
- [ ] **Step 4: Run** ; expected: PASS.
- [ ] **Step 5: Commit** `feat(esp): GPIO simulé et scénario d'entrées`.

### Task 3: Sandbox d'exécution

**Files:**
- Create: `content/esp/sandbox.py`
- Test: `backend/tests/test_esp_sandbox.py`

**Interfaces:**
- Produces: `@dataclass Result: rc: int; out: str; timed_out: bool; signal: str | None` ; `run_sandboxed(argv: list[str], *, cwd: Path, rw: Sequence[Path] = (), ro: Sequence[Path] = (), wall_s: float, cpu_s: int, mem_mb: int, max_out: int = 200_000) -> Result` ; `class SandboxUnavailable(RuntimeError)` levée si `bwrap` est absent (le contrôle échoue fermé, jamais en exécution directe). Isolation : `bwrap --unshare-all --die-with-parent --new-session`, pas de réseau, racine reconstruite avec seulement `/usr`, `/lib*`, `/bin` en lecture seule, `/proc` et `/dev` minimaux, un `tmpfs` pour `/tmp`, `cwd` et `rw` en écriture, `ro` en lecture seule ; limites `RLIMIT_CPU`, `RLIMIT_AS`, `RLIMIT_NPROC`, `RLIMIT_FSIZE` ; sortie tronquée à `max_out`.

- [ ] **Step 1: Write the failing tests** : `test_infinite_loop_killed` (`wall_s=2` : `timed_out`), `test_memory_bomb_stopped` (allocation de 4 Go avec `mem_mb=256`), `test_cannot_read_host_files` (programme qui ouvre `/etc/hostname` échoue), `test_no_network` (`socket`+`connect` vers `127.0.0.1` échoue), `test_fork_bomb_bounded`, `test_output_truncated`, `test_segfault_reports_signal` (`signal == "SIGSEGV"`), `test_unavailable_when_bwrap_missing` (avec `PATH` vide : `SandboxUnavailable`), `test_compiler_runs_inside_sandbox` (compilation d'un programme d'essai par `g++` dans le sandbox).
- [ ] **Step 2: Run** `uv run pytest tests/test_esp_sandbox.py -q` ; expected: FAIL.
- [ ] **Step 3: Implement** `run_sandboxed` avec `subprocess` et `preexec_fn` pour les `RLIMIT_*`. Si une limite empêche `g++`, relever la valeur minimale nécessaire et la fixer en constante nommée, avec une ligne de justification.
- [ ] **Step 4: Run** ; expected: PASS.
- [ ] **Step 5: Relecture sécurité** : dispatcher l'agent `ecc:security-reviewer` sur `sandbox.py` ; corriger les remarques bloquantes avant de continuer.
- [ ] **Step 6: Commit** `feat(esp): sandbox bwrap pour compiler et exécuter le code apprenant`.

### Task 4: Garde-fou `local_only`

**Files:**
- Modify: `backend/app/content.py` (`Tp.local_only: bool = False`, lu depuis `tp.json`, type booléen validé), `backend/app/terminal.py` (ajouter `strictly_local(conn) -> bool` : pair loopback et Host local, sans `remote_hosts`), `backend/app/main.py` (`tp_check`), `backend/app/boss.py` ou `main.py` (`/api/boss/attempt` : `boss.json` peut porter `"local_only": true`)
- Test: `backend/tests/test_local_only.py`

**Interfaces:**
- Produces: `strictly_local(conn) -> bool`. `POST /api/tp/{tp_id}/check` et `/api/boss/attempt` répondent 403 `"Réservé à la machine locale"` si le TP (ou le boss) est `local_only` et que `strictly_local` est faux, même quand `exec_ok` est vrai.

- [ ] **Step 1: Write the failing tests** (en suivant la façon dont `test_auth.py` / `test_terminal.py` créent une app avec `remote_exec=True`, mot de passe et hôtes autorisés) : `test_cpp_tp_refused_for_remote_host` (hôte autorisé, mot de passe fourni, TP `local_only` : 403), `test_plain_tp_still_allowed_remotely` (TP ordinaire : 200), `test_cpp_tp_allowed_on_loopback`, `test_boss_local_only_refused_remotely`, `test_tp_local_only_must_be_boolean` (`"local_only": "oui"` : `ModuleError`).
- [ ] **Step 2: Run** `uv run pytest tests/test_local_only.py -q` ; expected: FAIL.
- [ ] **Step 3: Implement** le champ, `strictly_local` et les deux gardes. L'interface masque déjà le terminal sur 403 (`Lesson.tsx`, `isForbidden`) : vérifier à la main dans le navigateur qu'un 403 sur le contrôle affiche un message compréhensible, et ajuster `Lesson.tsx` seulement s'il est muet.
- [ ] **Step 4: Run** `uv run pytest -q` (suite entière) ; expected: PASS.
- [ ] **Step 5: Commit** `feat: TP et boss local_only (refus en exécution distante)`.

### Task 5: Pilote `esp_check.py`

**Files:**
- Create: `content/esp/esp_check.py`, `content/esp/trace.py`
- Test: `backend/tests/test_esp_check.py`

**Interfaces:**
- Consumes: `build.build_sim()`, `sandbox.run_sandboxed`.
- Produces: usage `python3 -I -B esp_check.py <tp_id>` (cwd = dossier du TP ; le fichier appris est `main.cpp`). `class CheckError(Exception)` ; `need(condition: bool, message: str) -> None`. `class Trace` : `events(ev: str, **match) -> list[dict]`, `gpio_levels(pin: int) -> list[tuple[int, int]]` (t_ms, niveau), `logs(tag: str | None = None, level: str | None = None) -> list[dict]`, `last_end() -> dict`. Module de vérification `content/esp/checks/<tp_id>.py` : `SCENARIO: dict`, `MAX_MS: int`, `verify(trace: Trace, source: str) -> None`.
- Étapes du pilote, dans cet ordre : (1) lecture de `main.cpp` (fichier régulier, pas de lien symbolique, UTF-8, ≤ 200 000 octets) ; (2) analyse statique : refus de `#include` à chemin absolu ou contenant `..`, de `#embed`, `asm`/`__asm__`, `std::thread`, `std::this_thread`, `usleep`, `sleep(`, `nanosleep`, `<chrono>` utilisé pour attendre, `system(`, `fork(`, avec un message qui renvoie vers `vTaskDelay` ; (3) présence d'un `app_main` déclaré en `extern "C"` et absence de `main` ; (4) compilation dans le sandbox, erreurs du compilateur résumées (5 premières lignes, chemins nettoyés) ; (5) exécution dans le sandbox jusqu'à `MAX_MS` ; (6) interprétation de `end` (`busy_loop` → « votre tâche ne rend jamais la main : ajoutez un `vTaskDelay` », `crash` → signal, `abort` → message de `ESP_ERROR_CHECK`) ; (7) `verify`.

- [ ] **Step 1: Write the failing tests** avec un TP d'essai `checks/_selftest.py` (qui exige une LED en GPIO 2 allumée à 500 ms) : `test_reference_passes`, `test_missing_app_main_message`, `test_defines_main_message`, `test_compile_error_summarised` (contient « main.cpp » et au plus 5 lignes d'erreur), `test_sleep_for_refused_mentions_vtaskdelay`, `test_absolute_include_refused`, `test_segfault_message`, `test_output_flood_truncated` (boucle d'`ESP_LOGI` : sortie ≤ borne, message de troncature), `test_non_utf8_source_refused`, `test_symlink_source_refused`, `test_oversized_source_refused`, `test_sandbox_unavailable_fails_closed` (échec avec message, jamais d'exécution directe).
- [ ] **Step 2: Run** ; expected: FAIL.
- [ ] **Step 3: Implement** le pilote et `Trace`. Les messages d'erreur sont des constantes françaises en haut du fichier.
- [ ] **Step 4: Run** ; expected: PASS.
- [ ] **Step 5: Commit** `feat(esp): pilote de contrôle (analyse, compilation, exécution, trace)`.

### Task 6: Tableau de signatures et test de fidélité

**Files:**
- Create: `content/esp/sim/signatures.json`
- Test: `backend/tests/test_esp_sim.py`

**Interfaces:**
- Produces: `signatures.json` : liste d'objets `{"header": str, "name": str, "decl": str, "source": str (URL de la documentation officielle), "idf": str}` ; une entrée par fonction ou type exposé par le simulateur. Les tâches suivantes y ajoutent leurs entrées.

- [ ] **Step 1: Write the failing test** `test_every_exposed_function_has_a_verified_signature` : analyse les en-têtes de `sim/include` (déclarations de fonctions et de types publics) et exige que chacune figure dans `signatures.json` avec une `source` non vide et que le texte de la déclaration normalisé (espaces) soit identique ; `test_no_stale_signature` (aucune entrée sans déclaration correspondante).
- [ ] **Step 2: Run** ; expected: FAIL.
- [ ] **Step 3: Implement** : relever les signatures des Tasks 1 et 2 dans la documentation officielle (outil Context7, ou site d'Espressif) et remplir le tableau.
- [ ] **Step 4: Run** ; expected: PASS.
- [ ] **Step 5: Commit** `test(esp): tableau de signatures vérifiées`.

### Gabarit commun des tâches « leçon »

Chaque tâche leçon livre, dans `content/modules/<module>/` : la leçon `lessons/<id>.md` (gabarit du design : problème concret en une phrase, notions dans l'ordre du TP, mini-référence des fonctions avec signature, retour et erreurs, pièges `!!…!!`, « À retenir ») ; `lessons/<id>.qcm.json` (5 questions) ; `lessons/<id>.tp/{tp.json,check.sh,solution.sh,seed/main.cpp}` avec `"local_only": true`, énoncé en étapes numérotées, 3 indices du plus vague au plus précis, `timeout_s` ≤ 60 ; `content/esp/checks/<tp_id>.py` ; et une suite de variantes fautives dans `backend/tests/test_esp_check.py` (`test_<tp_id>_reference_passes`, `test_<tp_id>_seed_refused`, une `test_<tp_id>_mutant_<nom>` par variante, chacune attendant `ECHEC` et le fragment de message indiqué). `check.sh` : `exec python3 -I -B "$LESSON_DIR/../../../../esp/esp_check.py" <tp_id>`. `solution.sh` : `cat > main.cpp <<'EOF' … EOF` (même convention que `secu`). Les messages d'erreur nomment la cause observée (« la LED est restée allumée après 40 s ») et la section de la leçon à relire. La tâche ajoute aussi les signatures utilisées à `signatures.json`.

### Task 7: es1 — premier programme, journaux et LED

**Files:** `content/modules/esp1/module.json` (3 leçons : es1, es2, es3 ; `skill: "esp32"`), `lessons/es1.*`, `content/esp/checks/es1-tp.py`.

**Contenu:** `app_main`, `ESP_LOGI`, `gpio_config` / `gpio_set_level`, `vTaskDelay`. TP : faire clignoter la LED du GPIO 2 (500 ms allumée, 500 ms éteinte) avec un journal `blink` à chaque changement. Scénario : 10 s simulées. Vérifications : broche configurée en sortie, premier niveau haut, période 500 ms ± 10 ms, au moins 10 changements, un `ESP_LOGI` de tag `blink` par changement.

**Variantes fautives (≥ 6) :** sans configuration de la direction (« GPIO 2 jamais configurée en sortie ») ; période 1000 ms ; `ESP_LOGE` au lieu de `ESP_LOGI` ; boucle sans `vTaskDelay` (`busy_loop`) ; mauvaise broche ; niveau jamais modifié après le premier ; journal absent.

- [ ] Suivre le gabarit commun (tests d'abord, voir échouer, implémenter, voir passer) puis lancer `uv run pytest tests/test_esp_check.py tests/test_shipped_modules.py -q`.
- [ ] Commit `feat(esp): module esp1, leçon es1 (LED et journaux)`.

### Task 8: es2 — bouton et anti-rebond

**Files:** `lessons/es2.*` dans `esp1`, `content/esp/checks/es2-tp.py` ; ajouter l'entrée de scénario correspondante.

**Contenu:** entrée GPIO avec pull-up, logique inversée (appui = 0), rebonds mécaniques, anti-rebond par durée de stabilité, sondage périodique. TP : le bouton du GPIO 4 inverse la LED du GPIO 2, une seule fois par appui. Scénario : 3 appuis, chacun avec rebonds (0,1,0,1,0 sur 20 ms) et un appui court de 80 ms. Vérifications : la LED change exactement 3 fois, chaque changement dans les 60 ms qui suivent le premier front stable.

**Variantes fautives (≥ 6) :** sans anti-rebond (plus de 3 changements) ; sondage toutes les 500 ms (appui de 80 ms manqué) ; réaction aussi au relâchement ; pull-up non configuré (entrée lue à 0) ; anti-rebond de 2 s (appuis rapprochés manqués) ; LED jamais initialisée.

- [ ] Gabarit commun ; commit `feat(esp): es2 (bouton et anti-rebond)`.

### Task 9: es3 — tâches FreeRTOS et files

**Files:** `lessons/es3.*` dans `esp1`, `content/esp/checks/es3-tp.py` ; **Modify** : `content/esp/sim/include/freertos/queue.h`, `content/esp/sim/src/queue.cpp` (`xQueueCreate`, `xQueueSend`, `xQueueReceive`, `portMAX_DELAY`, `uxQueueMessagesWaiting`), tests de file dans `test_esp_sim.py` (`test_queue_blocks_until_item`, `test_queue_receive_timeout_returns_pdFALSE`, `test_queue_full_send_times_out`).

**Contenu:** `xTaskCreate` (pile, priorité), blocage plutôt qu'attente active, communication par file. TP : une tâche lit le bouton (sondage 10 ms avec anti-rebond) et envoie un événement dans une file ; une autre tâche bloquée sur `xQueueReceive(…, portMAX_DELAY)` inverse la LED. Vérifications : au moins 2 tâches créées, aucun changement de LED sans appui, usage réel de la file, aucun `busy_loop`, taille de pile ≥ 2048.

**Variantes fautives (≥ 6) :** une seule tâche ; variable globale partagée sans file ; `xQueueReceive` avec délai 0 (attente active) ; pile de 256 octets ; délai de sondage nul ; `xQueueSend` hors tâche créée.

- [ ] Gabarit commun ; commit `feat(esp): es3 (tâches FreeRTOS et files)`.

### Task 10: Point de contrôle de la tranche 1

- [ ] **Step 1:** `cd backend && uv run pytest -q` ; expected : toute la suite verte (≥ 625 + nouveaux tests).
- [ ] **Step 2:** relecture par l'agent `ecc:code-reviewer` sur la branche ; corriger les remarques bloquantes.
- [ ] **Step 3:** vérification à la main dans l'app locale : module esp1 visible, TP es1 réussi avec la solution, sensible à une variante fautive ; test d'un accès simulé « distant » : 403 sur le contrôle C++.
- [ ] **Step 4:** pousser sur `main` ; **demander au porteur du projet avant tout déploiement sur le VPS** (les TP C++ y restent bloqués à distance ; `g++` et `bwrap` y sont installés).

---

# Tranche 2 : capteurs et contrôle (module esp2)

### Task 11: Simulateur ADC, I2C et modèle de bassin

**Files:** Create `sim/include/{esp_adc/adc_oneshot.h,driver/i2c_master.h}`, `sim/src/{adc.cpp,i2c.cpp,plant.cpp}` ; Test `test_esp_sim.py`.

**Interfaces:** Produces `adc_oneshot_new_unit`, `adc_oneshot_config_channel`, `adc_oneshot_read` (12 bits, 0..4095), `i2c_new_master_bus`, `i2c_master_bus_add_device`, `i2c_master_transmit_receive`, `i2c_master_transmit`, `i2c_master_receive` avec `ESP_ERR_TIMEOUT` sur NACK scénarisé. Scénario étendu : `adc: [{"t_ms", "channel", "raw"}]` (interpolation linéaire) ; `i2c: {"0x44": {"bytes": [..], "nack": [{"from_ms","to_ms"}]}}` ; `plant: {"tank": {"level_pct0", "fill_pct_per_min", "loss_pct_per_min", "relay_pin", "adc_channel", "raw_at_0", "raw_at_100", "stuck": [{"from_ms","to_ms"}]}}` : le niveau évolue selon l'état du relais et se projette sur l'ADC. Événements : `adc_read`, `i2c_xfer` (`addr`, `ok`).

- [ ] Tests d'abord : `test_adc_follows_scenario_interpolated`, `test_i2c_nack_returns_timeout`, `test_plant_level_rises_when_relay_on`, `test_plant_stuck_sensor_holds_value`. Implémenter, ajouter les signatures vérifiées à `signatures.json`, lancer la suite, commit `feat(esp): ADC, I2C et modèle de bassin simulés`.

### Task 12: es4 — lire un capteur analogique (ADC)

**Files:** `content/modules/esp2/module.json` (es4, es5, es6) ; `lessons/es4.*` ; `checks/es4-tp.py`.

**Contenu:** ADC oneshot, valeurs brutes 0..4095, conversion en pourcentage selon l'étalonnage (0 % ↔ 0,5 V, 100 % ↔ 3,0 V, plage 0..3,3 V), moyenne de 8 échantillons contre le bruit. TP : journaliser `level=NN%` chaque seconde. Vérifications : valeur conforme à ± 2 points à chaque seconde sur une rampe bruitée, lecture par `adc_oneshot_read` (événements `adc_read` ≥ 8 par seconde).

**Variantes fautives (≥ 6) :** sans étalonnage (division par 4095) ; pas de moyenne (bruit > 2 points) ; lecture unique par seconde ; canal non configuré ; échelle 3,3 V au lieu de 3,0 V ; journal absent.

- [ ] Gabarit commun ; commit `feat(esp): module esp2, leçon es4 (ADC)`.

### Task 13: es5 — relais et capteur I2C avec gestion d'erreur

**Files:** `lessons/es5.*`, `checks/es5-tp.py`.

**Contenu:** pilote I2C maître nouvelle génération, lecture sur 2 octets d'une température (adresse `0x44`), conversion, relais en GPIO 5, `esp_err_t` sans `ESP_ERROR_CHECK` fatal. TP : lecture toutes les 5 s, relais allumé au-dessus de 28,0 °C ; sur `ESP_ERR_TIMEOUT` conserver l'état précédent et journaliser une erreur sans planter. Scénario : montée en température, NACK de 12 s en plein milieu.

**Variantes fautives (≥ 6) :** `ESP_ERROR_CHECK` (abort pendant le NACK) ; relais coupé pendant le NACK ; seuil à 25 °C ; conversion erronée (octets inversés) ; pas d'hystérésis de journalisation (spam) ; adresse fausse.

- [ ] Gabarit commun ; commit `feat(esp): es5 (relais et I2C)`.

### Task 14: es6 — régulation du niveau de la piscine

**Files:** `lessons/es6.*`, `checks/es6-tp.py`.

**Contenu:** hystérésis (bornes basse et haute), état de la régulation, délai maximal de remplissage, état sûr. TP : pompe sur le relais GPIO 5 ; démarrer sous 60 %, arrêter au-dessus de 80 % ; couper et lever une alarme (`ESP_LOGE` tag `pool`) si la pompe tourne depuis 10 minutes sans que le niveau monte ou si le capteur reste figé. Scénarios : (a) cycle normal sur 2 h simulées avec évaporation ; (b) capteur bloqué à 40 % pendant 15 min.

**Vérifications :** relais jamais allumé au-dessus de 80 % (tolérance 1 s), allumé sous 60 %, aucun battement entre 60 % et 80 %, coupure à 10 min dans (b), alarme journalisée, relais éteint à la fin dans tous les cas.

**Variantes fautives (≥ 6) :** sans hystérésis (battements) ; sans délai maximal (la pompe tourne tout le scénario b) ; seuils inversés ; alarme sans coupure ; relais allumé au démarrage avant lecture ; arrêt à 100 % (débordement).

- [ ] Gabarit commun ; lancer la suite ; commit `feat(esp): es6 (régulation de piscine)`. Point de contrôle : même vérification qu'à la Task 10, puis demander avant déploiement.

---

# Tranche 3 : connecté et fiable (module esp3)

### Task 15: Simulateur NVS, événements, Wi-Fi, MQTT, watchdog

**Files:** Create `sim/include/{nvs_flash.h,nvs.h,esp_event.h,esp_netif.h,esp_wifi.h,mqtt_client.h,esp_task_wdt.h,esp_system.h}`, `sim/src/{nvs.cpp,event.cpp,wifi.cpp,mqtt.cpp,wdt.cpp}` ; Test `test_esp_sim.py`.

**Interfaces:** Produces `nvs_flash_init`, `nvs_open`, `nvs_get_*`/`nvs_set_*`, `nvs_commit`, `esp_event_loop_create_default`, `esp_event_handler_register`, `esp_netif_init`, `esp_wifi_init/set_config/start/connect`, `WIFI_EVENT_STA_*`, `IP_EVENT_STA_GOT_IP`, `esp_mqtt_client_init/register_event/start/publish/subscribe/stop`, événements `MQTT_EVENT_CONNECTED/DISCONNECTED/DATA/ERROR`, `esp_task_wdt_*`, `esp_restart`, `esp_reset_reason`. Scénario étendu : `wifi: {"up_from_ms", "down": [{"from_ms","to_ms"}], "fail_attempts": n}` ; `mqtt: {"broker_down": [{"from_ms","to_ms"}], "incoming": [{"t_ms","topic","payload"}]}` ; `reboots_at_ms: [..]` (l'application redémarre ; la NVS persiste) ; événements `wifi`, `mqtt_publish` (`topic`, `payload`, `retain`, `qos`), `mqtt_subscribe`, `nvs_set`, `wdt_reset`, `reboot`. Les messages MQTT suivent les topics de l'ancien projet : `home/devices/<device_id>/telemetry|status|command`.

- [ ] Tests d'abord : `test_nvs_persists_across_scripted_reboot`, `test_wifi_fails_n_attempts_then_connects`, `test_mqtt_publish_traced_with_flags`, `test_mqtt_reconnect_after_broker_outage`, `test_wdt_fires_when_task_not_fed`. Implémenter ; signatures ; commit `feat(esp): NVS, événements, Wi-Fi, MQTT et watchdog simulés`.

### Task 16: es7 — Wi-Fi et boucle d'événements

**Files:** `content/modules/esp3/module.json` (es7, es8, es9) ; `lessons/es7.*`, `checks/es7-tp.py`.

**Contenu:** initialisation NVS (`ESP_ERR_NVS_NO_FREE_PAGES`), `esp_netif`, boucle d'événements par défaut, gestionnaires, reconnexion avec attente croissante. TP : se connecter avec retries (maximum 10, attente 1 s doublée jusqu'à 8 s) ; journaliser l'adresse obtenue. Scénario : 3 échecs puis succès ; variante : réseau absent.

**Variantes fautives (≥ 6) :** NVS non initialisée ; reconnexion immédiate en boucle serrée ; aucune limite d'essais ; gestionnaire non enregistré ; mot de passe écrit en dur (refusé par analyse statique) ; arrêt définitif après le premier échec.

- [ ] Gabarit commun ; commit `feat(esp): module esp3, leçon es7 (Wi-Fi)`.

### Task 17: es8 — MQTT : télémétrie, commandes, statut

**Files:** `lessons/es8.*`, `checks/es8-tp.py`.

**Contenu:** client MQTT, abonnement, publication, QoS, `retain`, testament (`last will`). TP : publier `home/devices/pool-ctl/telemetry` toutes les 10 s au format JSON `{"level": 72.5, "relay": false}` ; publier `home/devices/pool-ctl/status` `online` (retained) à la connexion avec testament `offline` ; exécuter la commande reçue sur `.../command` `{"relay": true}` sans jamais dépasser la limite de sécurité d'es6. Scénario : commande « relais allumé » reçue quand le niveau est à 85 % (doit être refusée et journalisée).

**Variantes fautives (≥ 6) :** topic erroné ; JSON invalide ; statut non retenu ; pas de testament ; commande exécutée au-dessus de 80 % ; pas d'abonnement ; intervalle de 1 s.

- [ ] Gabarit commun ; commit `feat(esp): es8 (MQTT)`.

### Task 18: es9 — robustesse : reconnexion, NVS, watchdog, erreurs

**Files:** `lessons/es9.*`, `checks/es9-tp.py`.

**Contenu:** reprise après coupure du courtier, réabonnement, consigne sauvegardée en NVS et restaurée après redémarrage, watchdog de tâche, gestion d'erreur à la place de `ESP_ERROR_CHECK`. TP : consigne de niveau haut modifiable par MQTT et persistante ; réabonnement après coupure de 60 s ; watchdog alimenté. Scénario : coupure du courtier, redémarrage à 120 s, commande de consigne avant le redémarrage.

**Variantes fautives (≥ 6) :** consigne perdue au redémarrage ; pas de réabonnement ; watchdog jamais alimenté (déclenchement) ; écriture NVS sans `nvs_commit` ; `ESP_ERROR_CHECK` sur la publication (abort pendant la coupure) ; relais allumé au démarrage avant relecture de la consigne.

- [ ] Gabarit commun ; suite complète ; commit `feat(esp): es9 (robustesse)`. Point de contrôle comme Task 10 (dont revue `ecc:code-reviewer`), puis demander avant déploiement.

---

# Tranche 4 : livrable chez un client (module esp4) et boss

### Task 19: Simulateur TLS et OTA

**Files:** Create `sim/include/{esp_https_ota.h,esp_ota_ops.h,esp_http_client.h,esp_app_format.h,esp_tls.h}`, `sim/src/{tls.cpp,ota.cpp}` ; **Modify** `mqtt.cpp` (transport `mqtts://`) ; Test `test_esp_sim.py`.

**Interfaces:** Produces `esp_https_ota`, `esp_https_ota_config_t`, `esp_ota_get_running_partition`, `esp_ota_get_state_partition`, `esp_ota_mark_app_valid_cancel_rollback`, `esp_ota_mark_app_invalid_rollback_and_reboot`, `esp_app_get_description`, `ESP_ERR_OTA_VALIDATE_FAILED`, `esp_ota_img_states_t`, configuration MQTT `broker.verification.certificate` / `skip_cert_common_name_check`. Scénario : `tls: {"server_cert_valid": bool, "handshake_fail": [{"from_ms","to_ms"}]}` ; `ota: {"images": [{"url", "version", "valid": bool, "drop_at_pct": int|null}]}` ; `boot: {"first_boot_after_ota": bool, "self_test_fails": bool}`. Événements : `tls_handshake` (`ok`, `verify`), `ota_begin`/`ota_end` (`url`, `ok`, `err`), `ota_mark` (`valid`), `rollback`. Le certificat de test est généré à l'exécution par `esp_check.py` (`openssl` dans le sandbox ou module Python `ssl` hors sandbox) dans le dossier de travail, jamais dans le contenu.

- [ ] Tests d'abord : `test_mqtts_refuses_unverified_when_cert_invalid`, `test_skip_cn_check_flagged_in_trace`, `test_ota_valid_image_reboots`, `test_ota_corrupt_returns_validate_failed`, `test_ota_dropped_connection_keeps_running_slot`, `test_rollback_when_not_marked_valid`. Implémenter ; signatures ; commit `feat(esp): TLS et OTA simulés`.

### Task 20: es10 — MQTT sur TLS

**Files:** `content/modules/esp4/module.json` (es10, es11, es12) ; `lessons/es10.*`, `checks/es10-tp.py`.

**Contenu:** TLS, chaîne de certificats, autorité de certification, pourquoi ne jamais désactiver la vérification, `mqtts://`, certificat embarqué, identifiants lus en NVS (jamais dans le code), échec de poignée de main et attente croissante. TP : passer le client es8 en `mqtts://` avec vérification du certificat serveur. Scénarios : certificat valide ; poignée de main en échec 2 minutes ; certificat invalide.

**Vérifications :** `tls_handshake` avec `verify == true`, aucune option de contournement dans le code source, aucun identifiant ou secret en clair (analyse statique), relais en état sûr pendant l'échec, nouvelle tentative avec attente croissante.

**Variantes fautives (≥ 6) :** `skip_cert_common_name_check = true` ; certificat non fourni ; identifiants en dur ; abandon définitif après l'échec ; reconnexion en boucle serrée ; relais laissé allumé pendant la panne.

- [ ] Gabarit commun ; en plus : vérifier que l'export portfolio ne bloque pas à tort les solutions es10 (`test_portfolio.py`, nouveau cas) ; adapter `leak_reason` seulement si nécessaire, avec ses tests. Commit `feat(esp): module esp4, leçon es10 (TLS)`.

### Task 21: es11 — mises à jour OTA

**Files:** `lessons/es11.*`, `checks/es11-tp.py`.

**Contenu:** table de partitions à deux slots, `esp_https_ota`, comparaison de version, signature et validation, quand redémarrer. TP : à réception de la commande `{"ota": "<url>"}`, mettre à jour seulement vers une version strictement plus récente, gérer `ESP_ERR_OTA_VALIDATE_FAILED` et une connexion coupée, redémarrer uniquement après succès. Scénarios : image valide plus récente ; image corrompue ; version identique ; coupure à 60 %.

**Variantes fautives (≥ 6) :** mise à jour vers une version identique ou plus ancienne ; redémarrage malgré l'échec ; image corrompue ignorée sans message ; `ESP_ERROR_CHECK` sur `esp_https_ota` ; certificat non vérifié ; relais non sûr pendant la mise à jour.

- [ ] Gabarit commun ; commit `feat(esp): es11 (OTA)`.

### Task 22: es12 — retour arrière et état sûr

**Files:** `lessons/es12.*`, `checks/es12-tp.py`.

**Contenu:** `CONFIG_BOOTLOADER_APP_ROLLBACK_ENABLE`, état de l'image (`ESP_OTA_IMG_PENDING_VERIFY`), auto-test au premier démarrage (capteur lisible et MQTT connecté en moins de 60 s), validation ou retour arrière, relais forcé hors tension avant toute autre initialisation. TP : au premier démarrage après OTA, faire l'auto-test et appeler `esp_ota_mark_app_valid_cancel_rollback` ou `esp_ota_mark_app_invalid_rollback_and_reboot`. Scénarios : auto-test réussi ; échec du capteur ; MQTT jamais connecté ; coupure de courant en plein démarrage.

**Variantes fautives (≥ 6) :** validation immédiate sans auto-test ; pas de retour arrière en cas d'échec ; délai d'auto-test infini ; relais configuré après le Wi-Fi (fenêtre où il peut rester allumé) ; auto-test qui ignore le capteur ; deux appels contradictoires.

- [ ] Gabarit commun ; commit `feat(esp): es12 (retour arrière et état sûr)`.

### Task 23: Boss — le contrôleur de piscine livrable

**Files:** Create `content/boss/esp_boss/{boss.json,phase1_check.sh,phase1_solution.sh,phase2_check.sh,phase2_solution.sh,phase3_check.sh,phase3_solution.sh}` avec `"local_only": true`, `content/esp/checks/esp_boss_p{1,2,3}.py`.

**Phases (cumulatives, dans `espboss/main.cpp`, `remedial_lesson_id` indiqué) :** 1. régulation et sécurité de la pompe avec capteur bloqué (es6) ; 2. connecté : Wi-Fi, MQTT sur TLS, reconnexion, consigne en NVS (es10, es9) ; 3. livrable : OTA valide et corrompue, coupure en plein OTA, certificat invalide, retour arrière (es11, es12). Dans toutes les pannes, le relais retombe en état sûr et ne déborde jamais le bassin ; chaque phase échoue sur un dossier vide et réussit après la solution de la phase précédente complétée.

- [ ] Tests d'abord : `test_esp_boss_phases_fail_on_empty_workspace`, `test_esp_boss_solutions_pass_in_sequence`, `test_esp_boss_mutants` (une variante par panne : relais laissé allumé après coupure MQTT, OTA corrompue acceptée, vérification TLS désactivée, consigne perdue, rollback manquant). Implémenter ; suite complète ; commit `feat(esp): boss final (contrôleur de piscine livrable)`.

### Task 24: Clôture

- [ ] **Step 1:** `uv run pytest -q` ; expected : suite entière verte.
- [ ] **Step 2:** mettre à jour `docs/BACKLOG.md` : ouverture à distance des TP C++ (changement séparé, à faire quand les tests du sandbox auront tourné en production) ; second projet « finir `Domotique` » ; MicroPython et Arduino en option.
- [ ] **Step 3:** relecture finale `ecc:code-reviewer` puis `ecc:security-reviewer` sur le diff de la branche ; corriger les remarques bloquantes.
- [ ] **Step 4:** pousser sur `main` ; **demander au porteur du projet avant le déploiement** sur le VPS (`git pull --ff-only`, rebuild du front si le front a changé, redémarrage de `formation.service`) ; vérifier que `g++` et `bwrap` répondent sur le VPS avant la première exécution.
