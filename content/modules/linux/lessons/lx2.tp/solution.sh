#!/usr/bin/env bash
# Solution de référence du TP lx2.
set -euo pipefail
cat > top_ips.sh <<'EOF'
#!/usr/bin/env bash
awk '{print $1}' "$1" | sort | uniq -c | sort -rn | head -3
EOF
cat > errors_5xx.sh <<'EOF'
#!/usr/bin/env bash
awk '$9 >= 500 {n++} END {print n+0}' "$1"
EOF
