#!/usr/bin/env bash
# Solution de référence du TP lx3.
set -euo pipefail
cat > sshd_config <<'EOF'
# Configuration SSH durcie
Port 22
PermitRootLogin no
PasswordAuthentication no
PubkeyAuthentication yes
MaxAuthTries 3
X11Forwarding no
AllowUsers deploy
EOF
cat > firewall.nft <<'EOF'
table inet filter {
  chain input {
    type filter hook input priority 0; policy drop;
    ct state established,related accept
    iif "lo" accept
    tcp dport { 22, 443 } accept
  }
}
EOF
