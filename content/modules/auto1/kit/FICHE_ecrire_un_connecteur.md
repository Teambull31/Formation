# Écrire un connecteur

Un connecteur transforme une boîte mail (API, IMAP, fichier) en liste de `Mail`. Le reste de l'automatisation ne connaît que ce contrat.

## Le contrat `MailSource`

```python
class MailSource(Protocol):
    def fetch(self, since: datetime | None = None, limit: int = 50) -> list[Mail]: ...
```

`Mail` est un `dataclass` figé, avec cinq champs : `id`, `sender`, `subject`, `received` (ISO 8601 en UTC, ex. `2026-03-02T08:15:00Z`), `body` (texte brut).

Les règles ne se négocient pas :

1. **Lecture seule.** Aucun envoi, aucune suppression, aucun marquage « lu ». Scopes minimaux : `Mail.Read`, `gmail.readonly`.
2. **Borné.** `limit` plafonne le résultat ; `limit <= 0` rend une liste vide ; les pages sont comptées pour qu'un serveur hostile ne boucle pas. Le corps est tronqué.
3. !!Ne jamais journaliser un corps de mail ni un jeton.!! Les messages de `ConnectorError` ne contiennent ni l'un ni l'autre : on journalise des comptes, jamais du contenu.
4. **Un seul hôte.** Les requêtes HTTP passent par `get_json`, qui refuse toute URL hors de `base_url` (`same_origin`) et ne suit pas les redirections.
5. **Jeton en 0600**, dans `~/.config/formation-auto1/`, écrit par `write_private`. !!Jamais de mot de passe ni de jeton en clair dans le code ou les arguments.!!

## L'exemple IMAP, pas à pas

`ImapSource` tient en une page. !!Copiez sa structure, pas ses raccourcis : lecture seule et mot de passe hors du code.!!

1. Constructeur : `ImapSource(host, user, password_env, folder="INBOX", port=993, connection_factory=None)`. On passe le **nom** de la variable (`password_env`), pas le mot de passe.
2. `fetch` lit la variable d'environnement et lève `ConnectorError` si elle est vide.
3. La connexion vient de `connection_factory` (par défaut TLS avec vérification du certificat et délai de 30 s). C'est ce qui rend le test possible : on injecte un faux serveur.
4. Le dossier est ouvert avec `readonly=True` : rien n'est marqué comme lu.
5. Chaque message est converti par `message_to_mail`, puis la sélection applique `since` et `limit`.
6. Les erreurs réseau deviennent un `ConnectorError` au texte neutre : le texte du serveur pourrait répéter un identifiant. Le `finally` ferme toujours la connexion.

## Squelette d'un nouveau connecteur

```python
from datetime import datetime
from mail_source import Mail


class MaSource:
    def __init__(self, host, token_path=None, auth=None):
        self.host, self.token_path, self.auth = host, token_path, auth

    def fetch(self, since: datetime | None = None, limit: int = 50) -> list[Mail]:
        if limit <= 0:
            return []
        mails = []
        # 1. obtenir un jeton (self.auth() en test), 2. GET borné, 3. une Mail par message
        mails.append(Mail(id="1", sender="a@example.test", subject="(sans objet)",
                          received="2026-03-02T08:15:00Z", body="texte"))
        # trier du plus récent au plus ancien, filtrer sur since, couper à limit
        return mails[:limit]
```

Tout champ peut manquer ou avoir le mauvais type : prévoyez une valeur de repli, ne levez pas d'exception pour un seul mail.

## Tester contre un simulateur

Ne testez jamais contre une vraie boîte. Le kit fournit `mock_graph` et `mock_gmail`, de faux serveurs locaux qui répondent comme les vraies API et notent chaque requête :

```python
with mock_graph.serve(port=0, pages=2) as srv:
    src = OutlookGraphSource("x", base_url=f"http://127.0.0.1:{srv.port}/v1.0", auth=lambda: "t")
    assert len(src.fetch(limit=5)) == 5
    assert all(m == "GET" for m, _, _ in srv.requests)
```

Pour votre connecteur, vérifiez au minimum : `limit` respecté, `since` filtre, aucune requête autre que GET, champ manquant sans exception, aucun jeton dans les messages d'erreur. Pour IMAP, passez un faux objet via `connection_factory`.
