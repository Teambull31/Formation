#!/usr/bin/env bash
# Labo réel du module Docker : hadolint sur le Dockerfile, docker compose config sur le compose (cwd = dossier du TP).
# Rien n'est construit ni lancé ici : faites docker build / docker compose up vous-même. Code 3 : aucun outil.
set -u
ran=0
if [ -f Dockerfile ] && command -v hadolint >/dev/null; then
  echo "\$ hadolint Dockerfile"; hadolint Dockerfile || exit 1; ran=1
fi
for f in docker-compose.yml compose.yaml compose.yml; do
  [ -f "$f" ] || continue
  if command -v docker >/dev/null && docker compose version >/dev/null 2>&1; then
    echo "\$ docker compose -f $f config --quiet"
    # variables du .env absentes : valeurs factices, seule la structure est vérifiée
    DATABASE_URL=x POSTGRES_PASSWORD=x docker compose -f "$f" config --quiet || exit 1; ran=1
  fi
done
if [ "$ran" = 0 ]; then
  echo "OUTIL ABSENT : ni hadolint ni docker compose."
  echo "Installez hadolint (https://github.com/hadolint/hadolint/releases) ou Docker avec le plugin compose."
  exit 3
fi
echo "OK : les outils Docker ne signalent rien. Essayez maintenant : docker compose build && docker compose up -d"
