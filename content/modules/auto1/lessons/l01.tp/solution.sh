cat > tri.sh <<'SCRIPT'
#!/usr/bin/env bash
# Range les fichiers d'un dossier dans des sous-dossiers par extension.
set -euo pipefail

if [ $# -ne 1 ]; then
  echo "Usage : $0 <dossier>" >&2
  exit 2
fi
dossier=$1
[ -d "$dossier" ] || { echo "Erreur : $dossier n'est pas un dossier" >&2; exit 1; }

for f in "$dossier"/*; do
  [ -f "$f" ] || continue
  nom=${f##*/}
  ext=sans_extension
  case $nom in
    *.*) ext=${nom##*.}; ext=${ext,,}; [ -n "$ext" ] || ext=sans_extension ;;
  esac
  mkdir -p "$dossier/$ext"
  mv -n -- "$f" "$dossier/$ext/$nom"
done
SCRIPT
chmod +x tri.sh
