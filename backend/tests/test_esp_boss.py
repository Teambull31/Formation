"""Le boss final de la formation ESP-IDF, « le contrôleur de piscine livrable » (content/boss/esp_boss).

Trois phases cumulatives dans espboss/main.cpp : la régulation et la sécurité de la pompe avec un capteur qui ment (es6), la liaison (Wi-Fi, MQTT sur TLS,
reprise, consigne en NVS : es10, es9), la livraison (OTA valide ou corrompue, coupure de courant, certificat invalide, retour arrière : es11, es12).
Chaque phase échoue sur un espace de travail vide et réussit après sa solution ; chaque panne a sa variante de programme qui doit être refusée, et des
variantes différentes mais correctes doivent passer. Les tests qui compilent demandent bwrap : ils sautent quand il est inutilisable (ESP_SANDBOX_REQUIRED=1 :
ils échouent).
"""
import json
import os
import re
import shutil
import subprocess
import time
import importlib.util
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

import pytest
from starlette.testclient import TestClient

from app.main import create_app
from app.portfolio import leak_reason

ROOT = Path(__file__).resolve().parents[2]
ESP = ROOT / "content" / "esp"
BOSS = ROOT / "content" / "boss" / "esp_boss"
LESSONS = ROOT / "content" / "modules"
FX = Path(__file__).parent / "fixtures"
REQUIRED = os.environ.get("ESP_SANDBOX_REQUIRED") == "1"
PHASES = (1, 2, 3)


def _load(name: str, path: Path):
    spec = importlib.util.spec_from_file_location(name, path)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


@pytest.fixture(scope="module")
def bwrap_ok(tmp_path_factory):
    sandbox = _load("esp_sandbox_probe_boss", ESP / "sandbox.py")
    try:
        sandbox.run_sandboxed(["/usr/bin/true"], cwd=tmp_path_factory.mktemp("probe"), wall_s=30, cpu_s=5, mem_mb=64)
    except sandbox.SandboxUnavailable as e:
        msg = f"bwrap indisponible sur cette machine : {e}"
        if REQUIRED:
            pytest.fail(msg)
        pytest.skip(msg)


def _env() -> dict:
    return {"PATH": os.environ["PATH"], "HOME": os.environ.get("HOME", "/"), "LESSON_DIR": str(BOSS)}


def _solution_source(n: int) -> str:
    text = (BOSS / f"phase{n}_solution.sh").read_text(encoding="utf-8")
    return text.split("<<'EOF'\n", 1)[1].rsplit("\nEOF", 1)[0] + "\n"


def _check(ws: Path, n: int, src: str | None = None) -> tuple[int, str]:
    """La phase n sur le programme `src` (écrit dans espboss/main.cpp), ou sur l'espace de travail tel quel."""
    if src is not None:
        (ws / "espboss").mkdir(exist_ok=True)
        (ws / "espboss" / "main.cpp").write_text(src, encoding="utf-8")
    r = subprocess.run(["bash", str(BOSS / f"phase{n}_check.sh")], cwd=ws, env=_env(), capture_output=True, text=True, timeout=120)
    return r.returncode, r.stdout + r.stderr


def _failed(code: int, out: str) -> bool:
    return code == 1 and out.startswith("ECHEC")


def _mutant(n: int, *edits: tuple[str, str]) -> str:
    src = _solution_source(n)
    for old, new in edits:
        assert src.count(old) >= 1, old
        src = src.replace(old, new)
    return src


# ---- les trois tests de la tâche ----

def test_esp_boss_phases_fail_on_empty_workspace(tmp_path, bwrap_ok):
    for n in PHASES:
        ws = tmp_path / f"vide{n}"
        ws.mkdir()
        code, out = _check(ws, n)  # ni espboss/ ni main.cpp
        assert _failed(code, out) and "espboss" in out, (n, out)
        (ws / "espboss").mkdir()
        code, out = _check(ws, n)  # dossier vide
        assert _failed(code, out) and "main.cpp" in out, (n, out)
        code, out = _check(ws, n, 'extern "C" void app_main(void) {}\n')  # un programme qui ne fait rien
        assert _failed(code, out) and "relire" in out, (n, out)


def test_esp_boss_solutions_pass_in_sequence(tmp_path, bwrap_ok):
    """Les solutions s'enchaînent dans le même espace de travail, comme dans attempt_boss : chaque phase réussit après la sienne."""
    for n in PHASES:
        subprocess.run(["bash", str(BOSS / f"phase{n}_solution.sh")], cwd=tmp_path, env=_env(), check=True, capture_output=True, timeout=60)
        start = time.monotonic()
        code, out = _check(tmp_path, n)
        assert code == 0 and out.startswith("OK"), (n, out)
        assert time.monotonic() - start < 30, f"phase {n} trop lente : {time.monotonic() - start:.1f} s (WALL_S = 40 s partagées)"
    for n in PHASES:  # les phases précédentes restent vraies avec le programme final : le jugement est cumulatif
        code, out = _check(tmp_path, n)
        assert code == 0, (n, out)


# nom -> (phase, remplacements, fragments attendus dans le message d'échec)
P1_NOT_PLAUSIBLE = "    if (brut < RAW_MIN_OK || brut > RAW_MAX_OK) {\n"
MUTANTS = {
    # phase 1
    "p1_no_plausibility_check": (1, [(P1_NOT_PLAUSIBLE, "    if (false) {\n")], ["scénario e", "n'est pas un niveau de 0 %"]),
    "p1_upper_bound_missing": (1, [("RAW_MAX_OK = 3900;", "RAW_MAX_OK = 4095;")], ["scénario f", "court-circuit"]),
    "p1_alarm_not_latched": (1, [("    etat = Etat::ALARM;\n", "    etat = Etat::IDLE;\n")], ["alarme"]),
    "p1_pump_not_safe_at_start": (1, [("    ESP_ERROR_CHECK(gpio_set_level(POMPE_GPIO, 0));\n}\n\n// Allume", "}\n\n// Allume")], ["état sûr"]),
    # phase 2 : une variante par panne
    "p2_relay_left_on_after_the_mqtt_cut": (2, [("        liaison = false;  // app_main éteint la pompe au prochain tour (au plus 1 s)\n", "")],
                                            ["scénario h", "la pompe est encore allumée après la perte de la liaison"]),
    "p2_tls_verification_disabled": (2, [("    cfg.broker.verification.certificate = _binary_server_cert_pem_start;\n",
                                          "    cfg.broker.verification.certificate = _binary_server_cert_pem_start;\n"
                                          "    cfg.broker.verification.skip_cert_common_name_check = true;\n")],
                                     ["skip_cert_common_name_check"]),
    "p2_tls_verification_dropped_by_a_flag": (2, [("    cfg.broker.verification.certificate = _binary_server_cert_pem_start;\n", "    cfg.broker.verification.skip_cert_common_name_check = true;\n")],
                                              ["skip_cert_common_name_check"]),
    "p2_setpoint_not_committed": (2, [("        err = nvs_commit(h);\n", "        err = ESP_OK;\n")], ["scénario g", "consigne enregistrée"]),
    "p2_setpoint_not_reloaded_at_boot": (2, [("    haut = charger_consigne();  // la consigne enregistrée, relue avant toute régulation\n", "")],
                                         ["scénario g", "consigne enregistrée"]),
    "p2_setpoint_never_written": (2, [("        err = nvs_commit(h);\n", "        err = ESP_OK;\n"), ("    err = nvs_set_i32(h, NVS_CLE_HAUT, valeur);\n", "    err = ESP_OK;\n")],
                                  ["scénario g", "consigne"]),
    "p2_no_resubscribe_after_a_reconnection": (2, [("        esp_mqtt_client_subscribe_single(ev->client, TOPIC_COMMANDE, 1);  // la session est propre : on se réabonne à chaque connexion\n", "")],
                                               ["abonnement", "MQTT_EVENT_CONNECTED"]),
    "p2_pump_runs_without_a_link": (2, [("        if (liaison && niveau < consigne - ECART) {\n", "        if (niveau < consigne - ECART) {\n")],
                                    ["la pompe s'allume", "liaison"]),
    "p2_out_of_bounds_setpoint_accepted": (2, [("    if (valeur < HAUT_MIN || valeur > HAUT_MAX) {\n", "    if (false) {\n")], ["scénario g", "95"]),
    "p2_credentials_in_the_code": (2, [("    cfg.credentials.username = utilisateur;\n", '    cfg.credentials.username = "piscine-ctl-07";\n')], ["identifiant", "clair"]),
    "p2_wifi_not_reconnected": (2, [("(id == WIFI_EVENT_STA_START || id == WIFI_EVENT_STA_DISCONNECTED)", "id == WIFI_EVENT_STA_START")],
                                ["scénario i", "esp_wifi_connect"]),
    "p2_tls_failure_not_logged": (2, [('ESP_LOGW(TAG_TLS, "échec TLS', 'ESP_LOGD(TAG_TLS, "échec TLS')], ["scénario j", "journalisé"]),
    "p2_relay_after_the_wifi": (2, [("    init_pompe();  // tout premier geste : pompe éteinte avant la NVS, le Wi-Fi, le capteur et MQTT\n", ""),
                                    ("    wifi_connecter();\n", "    wifi_connecter();\n    init_pompe();\n")], ["démarrage", "tout premier"]),
    # phase 3
    "p3_corrupt_ota_accepted": (3, [('        ESP_LOGE(TAG_OTA, "mise à jour échouée : %s", esp_err_to_name(err));\n        return;\n', '        ESP_LOGE(TAG_OTA, "mise à jour échouée : %s", esp_err_to_name(err));\n')],
                                ["scénario l", "la carte a redémarré"]),
    "p3_corrupt_ota_treated_as_success": (3, [("    if (err != ESP_OK) {\n        ESP_LOGE(TAG_OTA", "    if (err != ESP_OK && err != ESP_ERR_OTA_VALIDATE_FAILED) {\n        ESP_LOGE(TAG_OTA")],
                                          ["scénario l", "la carte a redémarré"]),
    "p3_rollback_missing": (3, [("    esp_err_t err = esp_ota_mark_app_invalid_rollback_and_reboot();  // ne revient pas si le retour arrière réussit\n", "    esp_err_t err = ESP_OK;\n")],
                            ["scénario o", "aucune décision"]),
    "p3_failed_selftest_confirms_the_image": (3, [('    ESP_LOGE(TAG_TEST, "auto-test échoué : retour à la version précédente");\n',
                                                   '    ESP_LOGE(TAG_TEST, "auto-test échoué : retour à la version précédente");\n    esp_ota_mark_app_valid_cancel_rollback();\n    return;\n')],
                                                 ["scénario o", "confirmée"]),
    "p3_tls_verification_disabled_for_the_ota": (3, [("    http.cert_pem = _binary_server_cert_pem_start;",
                                                      "    http.cert_pem = _binary_server_cert_pem_start;\n    http.skip_cert_common_name_check = true;")],
                                                 ["skip_cert_common_name_check"]),
    "p3_pump_left_on_during_the_ota": (3, [("    mettre_en_securite();  // pompe éteinte pendant toute la mise à jour ; ensuite la régulation reprend d'elle-même\n", "")],
                                       ["scénario k", "pas éteinte"]),
    "p3_http_address_accepted": (3, [('    if (strncmp(url, "https://", 8) != 0) {\n', "    if (false) {\n")], ["scénario p", "http://"]),
    "p3_versions_compared_as_text": (3, [("    if (!version_plus_recente(version, courante)) {\n", "    if (strcmp(version, courante) <= 0) {\n")], ["scénario k", "strictement plus récente"]),
    "p3_same_version_accepted": (3, [("    if (!version_plus_recente(version, courante)) {\n", "    if (strcmp(version, courante) < 0) {\n")], ["scénario"]),
    "p3_no_selftest": (3, [("    if (image_a_confirmer()) {\n", "    if (false) {\n")], ["scénario k", "n'est jamais confirmée"]),
    "p3_ota_failure_not_logged": (3, [('        ESP_LOGE(TAG_OTA, "mise à jour échouée : %s", esp_err_to_name(err));\n', "")], ["scénario l", "n'est pas journalisé"]),
    "p3_error_check_around_the_ota": (3, [("    esp_err_t err = esp_https_ota(&cfg);\n", "    esp_err_t err = ESP_OK;\n    ESP_ERROR_CHECK(esp_https_ota(&cfg));\n")], ["ESP_ERROR_CHECK"]),
    "p3_selftest_on_every_boot_even_if_confirmed": (3, [("    if (image_a_confirmer()) {", "    if (true) {")], ["scénario k", "marquages"]),
    "p3_selftest_does_not_wait_for_mqtt": (3, [("pdMS_TO_TICKS(delai_restant_ms())", "0")], ["scénario k", "redémarrages"]),
    "p3_version_not_announced": (3, [('    ESP_LOGI(TAG, "démarrage, version %s", esp_app_get_description()->version);\n', "")], ["versions annoncées"]),
}

# nom -> (phase, remplacements) : des programmes différents de la référence mais corrects, qui doivent passer
VARIANTS = {
    "p1_wider_plausible_range": (1, [("RAW_MIN_OK = 300;", "RAW_MIN_OK = 100;"), ("RAW_MAX_OK = 3900;", "RAW_MAX_OK = 4000;")]),
    "p1_two_laps_per_second": (1, [("PAS_MS = 1000;", "PAS_MS = 500;")]),
    "p2_setpoint_stored_as_a_byte": (2, [("    err = nvs_set_i32(h, NVS_CLE_HAUT, valeur);\n", "    err = nvs_set_u8(h, NVS_CLE_HAUT, (uint8_t)valeur);\n"),
                                         ("    esp_err_t err = nvs_get_i32(h, NVS_CLE_HAUT, &valeur);\n",
                                          "    uint8_t octet = 0;\n    esp_err_t err = nvs_get_u8(h, NVS_CLE_HAUT, &octet);\n    valeur = octet;\n")]),
    "p2_faster_loop_slower_telemetry_count": (2, [("PAS_MS = 1000;", "PAS_MS = 500;"), ("TOURS_TELEMETRIE = 10;", "TOURS_TELEMETRIE = 20;")]),
    "p2_pump_cut_from_the_event_handler": (2, [("        liaison = false;  // app_main éteint la pompe au prochain tour (au plus 1 s)\n", "        liaison = false;\n        pompe(false);  // tout de suite, sans attendre le prochain tour\n")]),
    "p3_longer_selftest_delay": (3, [("DELAI_AUTOTEST_MS = 60000;", "DELAI_AUTOTEST_MS = 65000;")]),
    "p3_english_failure_messages": (3, [('"mise à jour échouée : %s"', '"update failed: %s"')]),
}


def _in_pool(tmp_path: Path, cases: dict) -> dict[str, tuple[int, str]]:
    """Exécute chaque programme dans son propre espace de travail, 4 à la fois : nom -> (code, sortie)."""
    def one(item):
        name, (n, edits, *_) = item
        ws = tmp_path / name
        ws.mkdir()
        return name, _check(ws, n, _mutant(n, *edits))

    with ThreadPoolExecutor(max_workers=4) as pool:
        return dict(pool.map(one, cases.items()))


def test_esp_boss_mutants(tmp_path, bwrap_ok):
    """Une panne = un programme refusé, avec le message qui la nomme."""
    results = _in_pool(tmp_path, MUTANTS)
    problems = []
    for name, (n, _, fragments) in MUTANTS.items():
        code, out = results[name]
        if not _failed(code, out):
            problems.append(f"{name} (phase {n}) : accepté ({out[:200]})")
        elif not all(f.lower() in out.lower() for f in fragments):
            problems.append(f"{name} (phase {n}) : refusé sans les fragments {fragments} : {out[:400]}")
        elif "relire" not in out:
            problems.append(f"{name} : le message ne renvoie à aucune section")
    assert not problems, "\n".join(problems)


def test_esp_boss_valid_variants_pass(tmp_path, bwrap_ok):
    """Des programmes différents de la référence mais corrects ne sont pas refusés à tort."""
    results = _in_pool(tmp_path, {k: (n, edits) for k, (n, edits) in VARIANTS.items()})
    problems = [f"{name} : refusé : {out[:400]}" for name, (code, out) in results.items() if code != 0]
    assert not problems, "\n".join(problems)


# ---- le contenu du boss ----

def _boss() -> dict:
    return json.loads((BOSS / "boss.json").read_text(encoding="utf-8"))


def test_esp_boss_json_declares_three_local_only_phases():
    boss = _boss()
    assert boss["id"] == "esp_boss" and boss["local_only"] is True and len(boss["phases"]) == 3
    lessons = {p.name.split(".")[0] for m in LESSONS.glob("esp*/lessons/*.md") for p in [m]}
    for ph, remedial in zip(boss["phases"], ("es6", "es10", "es11")):
        assert ph["remedial_lesson_id"] == remedial and remedial in lessons, ph
        assert ph["timeout_s"] <= 60, ph
        assert ph["check"] == f'bash "$LESSON_DIR/phase{boss["phases"].index(ph) + 1}_check.sh"'
    assert len({ph["pattern_id"] for ph in boss["phases"]}) == 3
    assert all(not (BOSS / f"phase{n}_check.sh").read_text(encoding="utf-8").startswith("﻿") for n in PHASES)


def test_esp_boss_every_phase_has_its_files():
    for n in PHASES:
        assert (BOSS / f"phase{n}_check.sh").is_file() and (BOSS / f"phase{n}_solution.sh").is_file()
        assert (ESP / "checks" / f"esp_boss_p{n}.py").is_file()


# Ce que chaque contrôle impose doit figurer dans l'énoncé de sa phase (le libellé est tout ce que l'apprenant lit).
STATED = {
    1: ["espboss/main.cpp", "GPIO 5", "canal 6", "620", "3723", "60 %", "80 %", "10 min", "pool", "ESP_LOGE", "une seule", "[300, 3900]", "12 s",
        "30 s", "42 s", "1 s", "e (", "f (", "9 min 30 s", "10 min 15 s", "esp_timer_get_time", "10 s", "cumulatif"],
    2: ["mqtts://", "broker.local", "8883", "server_cert", "_binary_server_cert_pem_start", "user", "pass", "home/devices/pool-ctl/command",
        "home/devices/pool-ctl/telemetry", "level", "relay", "high", "40", "80", "20 points", "setpoint refused: high=", "ESP_LOGW", "nvs_commit",
        "NVS", "2 s", "5 s", "30 s", "tls", "esp_tls_last_esp_err", "10 s", "9 s", "11 s", "skip_cert_common_name_check", "liaison", "8 s", "5 tentatives"],
    3: ["{\"ota\"", "https://", "x.y.z", "strictement plus récente", "esp_https_ota", "cert_pem", "ota", "ESP_LOGE", "esp_err_to_name", "démarrage, version",
        "PENDING_VERIFY", "[300, 3900]", "60 s", "autotest", "esp_ota_mark_app_valid_cancel_rollback", "esp_ota_mark_app_invalid_rollback_and_reboot",
        "55 s", "70 s", "10 s", "5 s", "15 s", "ESP_ERROR_CHECK", "ESP_LOGW", "updates.example.net", "42 s", "simulateur"],
}


@pytest.mark.parametrize("n", PHASES)
def test_esp_boss_labels_state_every_enforced_rule(n):
    label = _boss()["phases"][n - 1]["label"]
    missing = [s for s in STATED[n] if s not in label]
    assert not missing, missing


def test_esp_boss_labels_are_french_with_accents():
    for ph in _boss()["phases"]:
        assert re.search(r"[éèêàùç]", ph["label"]) and ph["label"].startswith("Phase "), ph["label"][:80]


def test_esp_boss_tls_sections_use_the_generated_certificate():
    """Toute section tls des scénarios demande le certificat fabriqué par le pilote (sans server_cert le pilote échoue)."""
    for n in (2, 3):
        mod = _load_check(n)
        for name, (scenario, _) in mod.SCENARIOS.items():
            if "tls" in scenario:
                assert scenario["tls"].get("server_cert") == "@generate", (n, name)


def _load_check(n: int):
    import sys
    sys.path.insert(0, str(ESP))
    try:
        trace = _load("esp_trace", ESP / "trace.py")
        sys.modules["esp_trace"] = trace
        return trace.load_check(f"esp_boss_p{n}")
    finally:
        sys.path.remove(str(ESP))


def test_esp_boss_scenario_budget():
    """Le temps d'un attempt_boss : au plus 60 s par phase, 40 s de mur partagées entre les exécutions d'une phase, RUN_CPU_S = 5 par exécution,
    douze tâches au plus, traces plafonnées : les durées virtuelles et les plafonds de chaque contrôle restent dans les limites du pilote."""
    driver = _load("esp_driver_probe", ESP / "esp_check.py")
    for n in PHASES:
        mod = _load_check(n)
        assert len(mod.SCENARIOS) <= {1: 6, 2: 10, 3: 16}[n]
        assert min(getattr(mod, "MAX_OUT", driver.MAX_OUT), driver.MAX_OUT_LIMIT) <= driver.MAX_OUT_LIMIT
        assert all(ms <= 7_300_000 for _, ms in mod.SCENARIOS.values())


def test_esp_boss_check_sections_exist_in_the_lessons():
    """Chaque « relire : <section> » des contrôles du boss renvoie à un titre réel d'une leçon es1 à es12."""
    titles = set()
    for md in LESSONS.glob("esp*/lessons/es*.md"):
        titles |= set(re.findall(r"^## (.+)$", md.read_text(encoding="utf-8"), re.M))
    for n in PHASES:
        mod = _load_check(n)
        cited = {v for k, v in vars(mod).items() if k.startswith("S_") and isinstance(v, str)}
        source = (ESP / "checks" / f"esp_boss_p{n}.py").read_text(encoding="utf-8")
        cited |= set(re.findall(r"relire : « ([^»{]+) »", source))
        assert cited and cited <= titles, (n, cited - titles)


def test_esp_boss_test_credentials_live_only_in_the_check_modules():
    """Le contrôle cherche les identifiants d'essai dans le programme de l'apprenant : ils ne figurent ni dans l'énoncé ni dans les solutions."""
    es10 = _load_check(2).es10
    texts = [(BOSS / "boss.json").read_text(encoding="utf-8")] + [_solution_source(n) for n in PHASES]
    for text in texts:
        assert es10.USER not in text and es10.PASS not in text


# ---- les solutions ne se publient pas telles quelles si elles fuient : elles ne fuient pas ----

@pytest.mark.parametrize("n", PHASES)
def test_esp_boss_solutions_do_not_leak(n):
    """Le portfolio refuse tout secret en clair : les solutions du boss le passent sans l'affaiblir (le moteur n'exporte pas les espaces de travail de
    boss, seulement ceux des TP des modules ; ce test garde la solution publiable si cela change)."""
    assert leak_reason(_solution_source(n)) is None
    assert leak_reason((BOSS / f"phase{n}_solution.sh").read_text(encoding="utf-8")) is None


# ---- l'API ----

def _app(tmp_path: Path, peer: str, base_url: str, **kw):
    content = tmp_path / "content"
    shutil.copytree(FX / "demo_module", content / "modules" / "demo")
    shutil.copytree(BOSS, content / "boss" / "esp_boss")
    shutil.copy(ROOT / "content" / "gacha.json", content / "gacha.json")
    ws = tmp_path / "ws"
    ws.mkdir()
    return TestClient(create_app(str(tmp_path / "f.db"), content, ws, **kw), base_url=base_url, client=(peer, 50000))


def test_esp_boss_attempt_refused_remotely(tmp_path):
    import base64
    pw = "correct-horse-battery"
    c = _app(tmp_path, "172.18.0.2", "http://formation.example", password=pw, remote_exec=True, allowed_hosts=["formation.example"])
    auth = {"Authorization": "Basic " + base64.b64encode(f"moi:{pw}".encode()).decode()}
    r = c.post("/api/boss/attempt", params={"id": "esp_boss"}, headers={"host": "formation.example", **auth})
    assert r.status_code == 403 and r.json()["detail"] == "Réservé à la machine locale"
    assert c.get("/api/boss", params={"id": "esp_boss"}, headers={"host": "formation.example", **auth}).json()["phases"][0]["label"].startswith("Phase 1")


def test_esp_boss_attempt_on_loopback_stops_at_the_first_phase_on_an_empty_workspace(tmp_path, bwrap_ok):
    c = _app(tmp_path, "127.0.0.1", "http://localhost")
    r = c.post("/api/boss/attempt", params={"id": "esp_boss"}).json()
    assert r["won"] is False and r["phase_reached"] == 1 and r["remedial_lesson_id"] == "es6", r
