#!/usr/bin/env bash
# Solution de référence du TP an5.
# Le coffre group_vars/db/vault.yml de cette solution est chiffré avec le mot de passe « formation ».
set -euo pipefail
rm group_vars/db.yml
cat > ansible.cfg <<'EOF'
[defaults]
inventory = inventory.ini
EOF
mkdir -p group_vars/db
cat > group_vars/db/vars.yml <<'EOF'
db_name: app
db_user: app
db_password: "{{ vault_db_password }}"
EOF
mkdir -p group_vars/db
cat > group_vars/db/vault.yml <<'EOF'
$ANSIBLE_VAULT;1.1;AES256
35636563646664356535633137343937393366366266646438366662656565663238376161386238
6532646362636462346537636561636238636430623533390a373636353136643364363661626563
35623838383633646466636161353766323363626164393463363233353435393664363037376564
3863373831353138640a653233333830353862393433393266303133326662616531613731313662
30623430336136326664313038623462353631666435646563363561383163646235363931396662
66316663643436356331353338336161363030613965313730613931333633386639343235356434
326331303137316265356530323133336563
EOF
cat > .gitignore <<'EOF'
.vault_pass
*.retry
EOF
cat > db.yml <<'EOF'
- name: Base de données
  hosts: db
  tasks:
    - name: Installer PostgreSQL
      ansible.builtin.apt:
        name: postgresql
        state: present
      become: true
    - name: Créer l'utilisateur de la base
      community.postgresql.postgresql_user:
        name: "{{ db_user }}"
        password: "{{ db_password }}"
      become: true
      become_user: postgres
      no_log: true
EOF
