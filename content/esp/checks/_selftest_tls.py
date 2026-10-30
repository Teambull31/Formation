"""TP d'essai du certificat généré à l'exécution (préfixe _ : hors des TP livrés) : un client mqtts:// doit se connecter.

Le certificat du « broker » est fabriqué par le pilote à chaque exécution (esp_check.GENERATE_CERT) et n'est jamais stocké ici.
"""
from esp_trace import Trace, need

SCENARIO = {"tls": {"server_cert": "@generate", "server_cn": "broker.local"}}
MAX_MS = 2000


def verify(trace: Trace, source: str) -> None:
    hs = trace.events("tls_handshake")
    need(hs and hs[-1]["ok"], "la poignée de main TLS doit réussir (relire : la section TLS)")
    need(any(e["event"] == "connected" for e in trace.events("mqtt")), "le client MQTT doit se connecter (relire : la section TLS)")
