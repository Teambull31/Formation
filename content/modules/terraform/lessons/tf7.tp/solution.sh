#!/usr/bin/env bash
# Solution de référence du TP tf7.
set -euo pipefail
cat > diagnostic.yaml <<'DIAG'
provider: version
tfvars: validation
logs: renommage
servers: index
config: derive
DIAG
sed -i 's/"~> 9.0"/"~> 2.5"/' main.tf
sed -i 's/environment = "production"/environment = "prod"/' prod.tfvars
python3 - <<'PY'
import re
s = open("main.tf", encoding="utf-8").read()
s = s.replace('''  count    = length(var.servers)
  filename = "${local.out_dir}/${var.servers[count.index]}.conf"''', '''  for_each = toset(var.servers)
  filename = "${local.out_dir}/${each.key}.conf"''')
s += '''
moved {
  from = local_file.logs
  to   = local_file.journaux
}

moved {
  from = local_file.server[0]
  to   = local_file.server["web-1"]
}

moved {
  from = local_file.server[2]
  to   = local_file.server["web-3"]
}
'''
open("main.tf", "w", encoding="utf-8").write(s)
PY
