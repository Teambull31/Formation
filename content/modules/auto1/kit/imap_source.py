"""IMAP example: "write your own connector". Read-only select, password from the environment."""
import email
import imaplib
import os
from datetime import datetime

from mail_source import ConnectorError, Mail, _select, message_to_mail


class ImapSource:
    def __init__(self, host, user, password_env, folder="INBOX", port=993, connection_factory=imaplib.IMAP4_SSL):
        self.host, self.user, self.password_env = host, user, password_env
        self.folder, self.port, self.connection_factory = folder, port, connection_factory

    def fetch(self, since: datetime | None = None, limit: int = 50) -> list[Mail]:
        password = os.environ.get(self.password_env)  # never a literal password in code or args
        if not password:
            raise ConnectorError(f"variable d'environnement {self.password_env} absente ou vide")
        try:
            conn = self.connection_factory(self.host, self.port)
            conn.login(self.user, password)
            conn.select(self.folder, readonly=True)  # readonly: nothing gets flagged as read or deleted
            ids = conn.search(None, "ALL")[1][0].split()[-limit:]
            mails = []
            for n in ids:
                raw = conn.fetch(n, "(RFC822)")[1][0][1]
                mails.append(message_to_mail(email.message_from_bytes(raw), f"imap-{n.decode()}"))
            conn.logout()
        except (imaplib.IMAP4.error, OSError):
            raise ConnectorError("connexion IMAP échouée") from None  # server text may echo credentials
        return _select(mails, since, limit)
