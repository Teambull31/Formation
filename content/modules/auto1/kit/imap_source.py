"""IMAP example: "write your own connector". Read-only select, password from the environment."""
import email
import imaplib
import os
import ssl
from datetime import datetime

from mail_source import ConnectorError, Mail, _select, message_to_mail


class ImapSource:
    def __init__(self, host, user, password_env, folder="INBOX", port=993, connection_factory=None):
        self.host, self.user, self.password_env = host, user, password_env
        self.folder, self.port, self.connection_factory = folder, port, connection_factory or self._tls

    @staticmethod
    def _tls(host, port):
        # default context = certificate and hostname verification; timeout: no hang on a dead server
        return imaplib.IMAP4_SSL(host, port, ssl_context=ssl.create_default_context(), timeout=30)

    def fetch(self, since: datetime | None = None, limit: int = 50) -> list[Mail]:
        password = os.environ.get(self.password_env)  # never a literal password in code or args
        if not password:
            raise ConnectorError(f"variable d'environnement {self.password_env} absente ou vide")
        if limit <= 0:
            return []
        conn = None
        try:
            conn = self.connection_factory(self.host, self.port)
            conn.login(self.user, password)
            conn.select(self.folder, readonly=True)  # readonly: nothing gets flagged as read or deleted
            status, data = conn.search(None, "ALL")
            if status != "OK" or not data or data[0] is None:
                raise ConnectorError("recherche IMAP refusée")
            mails = []
            for n in data[0].split()[-limit:]:
                status, parts = conn.fetch(n, "(RFC822)")
                if status != "OK" or not parts or not isinstance(parts[0], tuple):
                    raise ConnectorError("lecture IMAP refusée")
                mails.append(message_to_mail(email.message_from_bytes(parts[0][1]), f"imap-{n.decode()}"))
        except (imaplib.IMAP4.error, OSError):
            raise ConnectorError("connexion IMAP échouée") from None  # server text may echo credentials
        finally:
            if conn is not None:
                try:
                    conn.logout()
                except Exception:  # already closed: nothing more to do
                    pass
        return _select(mails, since, limit)
