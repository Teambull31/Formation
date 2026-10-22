# Prépare l12/ comme après le TP 12 (kit, digest.py, quotidien.py de référence) si l'apprenant n'a rien. cwd = racine.
M="$LESSON_DIR/../../modules/auto1"
mkdir -p l12 && cd l12 || exit 1
[ -d kit ] || cp -r "$M/kit" kit
[ -f digest.py ] || cp "$M/lessons/_starters/digest.py" digest.py
[ -f quotidien.py ] || LESSON_DIR="$M/lessons/l12.tp" bash "$M/lessons/l12.tp/solution.sh"
cd ..
