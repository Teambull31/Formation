#!/usr/bin/env bash
# Solution de référence du TP 11 : maison_source.py (EmlDirSource sur un dossier de .eml) branché sur digest.py.
cat > maison_source.py <<'PY'
# maison_source.py : source de mails « maison » = un dossier de fichiers .eml (lecture seule).
#   python3 maison_source.py --path DOSSIER [--out digest.json]
import argparse
import email
import json
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
import digest  # point de départ fourni ; ajoute aussi kit/ au chemin d'import
from mail_source import _select, message_to_mail

MAX_EML = 5_000_000  # octets lus au plus par fichier


class EmlDirSource:
    """Respecte le contrat MailSource : fetch(since, limit) -> list[Mail], plus récents d'abord."""

    def __init__(self, path):
        self.path = Path(path)

    def fetch(self, since=None, limit=50):
        if limit <= 0 or not self.path.is_dir():
            return []
        mails = []
        for f in sorted(self.path.glob("*.eml")):  # pas de sous-dossiers, pas d'autres extensions
            if not f.is_file():
                continue
            try:
                with open(f, "rb") as fh:
                    raw = fh.read(MAX_EML)
            except OSError:
                continue  # un fichier illisible ne bloque pas les autres
            mails.append(message_to_mail(email.message_from_bytes(raw), f.stem))
        return _select(mails, since, limit)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--path", required=True)
    ap.add_argument("--out", default="digest.json")
    args = ap.parse_args()
    mails = EmlDirSource(args.path).fetch(limit=10_000)
    with open(args.out, "w", encoding="utf-8") as f:
        json.dump([digest.digest_entry(m) for m in mails], f, ensure_ascii=False, indent=2)
    print(f"{len(mails)} mails traités.")  # un nombre, jamais de contenu


if __name__ == "__main__":
    main()
PY
