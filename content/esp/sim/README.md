# Simulateur ESP-IDF

Faux ESP-IDF compilé une fois (`build.py`, mis en cache selon le contenu des sources) et lié au programme de l'apprenant.
Un scénario JSON décrit le monde extérieur (capteurs, coupures) ; le programme écrit une trace d'événements que les
contrôles de `content/esp/checks/` analysent. `signatures.json` liste les signatures reprises de la doc ESP-IDF v5.5.3.

## Clé de scénario `series` (I2C)

Sous `"i2c"`, chaque appareil est indexé par son adresse (`"0x44"`) et accepte `bytes`, `series` et `nack`
(`bytes` ou `series` est obligatoire).

`series` est un tableau de pas `{"t_ms": entier >= 0, "bytes": [octets]}` : à partir de l'instant `t_ms` (horloge
simulée), les lectures renvoient ces octets à la place de `bytes`. Un lecteur reçoit le dernier pas dont `t_ms` est
passé, sinon `bytes`, complétés par des zéros. Les pas sont triés par `t_ms` (à égalité, le dernier écrit l'emporte),
donc l'ordre du tableau n'a pas d'importance. Avec `series` seul, l'appareil répond des zéros avant le premier pas.
Un pas mal formé fait échouer le chargement du scénario avec un message en français.

Exemple réel, `content/esp/checks/es5-tp.py` : un capteur de température dont la valeur change au fil du temps,
avec deux fenêtres où il ne répond pas (les lectures finissent en `ESP_ERR_TIMEOUT`).

```python
SCENARIO = {"i2c": {"0x44": {
    "series": [{"t_ms": s * 1000, "bytes": [raw_of(c) >> 8, raw_of(c) & 0xFF]} for s, c in TEMPS_C.items()],
    "nack": [GLITCH, NACK]}}}   # GLITCH et NACK : {"from_ms": ..., "to_ms": ...}
```

Les tests de référence sont `test_i2c_series_changes_bytes_over_time` et les cas invalides dans `backend/tests/test_esp_sim.py`.

## Export

Les dossiers de travail du boss ESP ne sont pas exportés (portfolio) : le contrôle de fuite `leak_reason` ne les couvre pas.
Les modules esp1 à esp4 n'ont pas non plus `"portfolio": true` en v1 (voir `docs/BACKLOG.md`).
