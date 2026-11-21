"""Les contrôles des TP DevOps avancés (ci4-6, k4-7, tf4-6, an1-6) refusent chaque variante fautive de la solution."""
import shutil
import subprocess
import sys
from pathlib import Path

import pytest

MODULES = Path(__file__).resolve().parents[2] / "content" / "modules"
CHECKERS = {"ci": "cicd/lessons/_cicd_check.py", "k": "k8s/lessons/_k8s_check.py",
            "tf": "terraform/lessons/_hcl_check.py", "an": "ansible/lessons/_ansible_check.py"}


def _lesson_dir(tp: str) -> Path:
    return MODULES / CHECKERS[tp.rstrip("0123456789")].rsplit("/", 1)[0]


def _solved(tmp_path: Path, tp: str) -> Path:
    tp_dir = _lesson_dir(tp) / f"{tp}.tp"
    ws = tmp_path / tp
    shutil.copytree(tp_dir / "seed", ws)
    subprocess.run(["bash", str(tp_dir / "solution.sh")], cwd=ws, check=True, capture_output=True, timeout=30,
                   env={"PATH": "/usr/bin:/bin", "LESSON_DIR": str(tp_dir)})
    return ws


def _check(ws: Path, tp: str) -> tuple[int, str]:
    checker = MODULES / CHECKERS[tp.rstrip("0123456789")]
    r = subprocess.run([sys.executable, "-I", "-B", str(checker), tp], cwd=ws, capture_output=True, text=True, timeout=20)
    return r.returncode, r.stdout


def test_yaml_reader_copies_are_identical():
    ref = (MODULES / "cicd" / "lessons" / "_yaml.py").read_bytes()
    for m in ("terraform", "ansible"):
        assert (MODULES / m / "lessons" / "_yaml.py").read_bytes() == ref


MUT = [
    # (tp, fichier, ancien, nouveau, extrait attendu du message)
    ("ci4", ".github/actions/setup/action.yml", "      shell: bash\n", "", "shell: bash"),
    ("ci4", ".github/actions/setup/action.yml", "using: composite", "using: node20", "composite"),
    ("ci4", ".github/workflows/reusable-test.yml", "  workflow_call:", "  push:\n  workflow_call:", "que workflow_call"),
    ("ci4", ".github/workflows/reusable-test.yml", "        required: true\n", "", "required: true"),
    ("ci4", ".github/workflows/reusable-test.yml", "      - uses: actions/checkout@v4\n      - uses: ./.github/actions/setup",
     "      - uses: ./.github/actions/setup", "checkout"),
    ("ci4", ".github/workflows/ci.yml", "    uses: ./.github/workflows/reusable-test.yml\n",
     "    uses: ./.github/workflows/reusable-test.yml\n    runs-on: ubuntu-latest\n", "ni runs-on"),
    ("ci4", ".github/workflows/ci.yml", "[\"3.11\", \"3.12\"]", "[\"3.12\"]", "deux versions"),
    ("ci5", ".github/workflows/deploy.yml", "  workflow_dispatch:\n", "  workflow_dispatch:\n  pull_request:\n", "pull request"),
    ("ci5", ".github/workflows/deploy.yml", "branches: [main]", "branches: [main, dev]", "branches"),
    ("ci5", ".github/workflows/deploy.yml", "echo \"version=1.0.${GITHUB_RUN_NUMBER}\" >> \"$GITHUB_OUTPUT\"",
     "echo \"::set-output name=version::1\"", "set-output"),
    ("ci5", ".github/workflows/deploy.yml", "needs: [build, deploy-staging]", "needs: deploy-staging", "build doit figurer"),
    ("ci5", ".github/workflows/deploy.yml", "cancel-in-progress: false", "cancel-in-progress: true", "annuler"),
    ("ci5", ".github/workflows/deploy.yml", "    if: github.ref == 'refs/heads/main'\n", "", "refs/heads/main"),
    ("ci5", ".github/workflows/deploy.yml", "    environment: staging\n", "", "staging"),
    ("ci6", ".github/workflows/release.yml", "tags: [\"v*\"]", "branches: [main]", "tags"),
    ("ci6", ".github/workflows/release.yml", "permissions:\n  contents: read\n", "permissions: write-all\n", "lecture seule"),
    ("ci6", ".github/workflows/release.yml", "          role-to-assume: arn:aws:iam::123456789012:role/release\n",
     "          aws-access-key-id: ${{ secrets.AWS_KEY }}\n", "statique"),
    ("ci6", ".github/workflows/release.yml", "@e3dd6a429d7300a6a4c196c26e071d42e0343502", "@v4", "SHA"),
    ("ci6", ".github/workflows/release.yml", "          retention-days: 7\n", "", "retention-days"),
    ("ci6", ".github/workflows/release.yml", "      id-token: write\n", "", "id-token"),
    ("ci6", ".github/workflows/release.yml", "          name: dist\n          path: dist/\n    ",
     "          name: autre\n          path: dist/\n    ", "même name"),
    ("k4", "db.yaml", "kind: StatefulSet", "kind: Deployment", "StatefulSet"),
    ("k4", "db.yaml", "  clusterIP: None\n", "", "headless"),
    ("k4", "db.yaml", "            - name: data\n              mountPath", "            - name: autre\n              mountPath", "même name"),
    ("k4", "db.yaml", "  concurrencyPolicy: Forbid\n", "", "Forbid"),
    ("k4", "db.yaml", "restartPolicy: OnFailure", "restartPolicy: Always", "restartPolicy"),
    ("k4", "db.yaml", "\"0 3 * * *\"", "\"chaque nuit\"", "cron"),
    ("k4", "db.yaml", "postgres:16.4\n          ports", "postgres:latest\n          ports", "latest"),
    ("k5", "web.yaml", "      maxUnavailable: 0\n", "      maxUnavailable: 1\n", "maxUnavailable"),
    ("k5", "web.yaml", "spec:\n  strategy:", "spec:\n  replicas: 3\n  strategy:", "spec.replicas"),
    ("k5", "web.yaml", "  ingressClassName: nginx\n", "", "ingressClassName"),
    ("k5", "web.yaml", "      secretName: web-tls\n", "", "TLS"),
    ("k5", "web.yaml", "              cpu: 100m\n              memory: 128Mi\n            limits",
     "              memory: 128Mi\n            limits", "requests.cpu"),
    ("k5", "web.yaml", "  minAvailable: 1\n  selector:\n    matchLabels:\n      app: web",
     "  minAvailable: 1\n  selector:\n    matchLabels:\n      app: autre", "PodDisruptionBudget"),
    ("k5", "web.yaml", "metadata:\n  name: web\nspec:\n  selector:\n    app: web\n  ports",
     "metadata:\n  name: web\nspec:\n  type: LoadBalancer\n  selector:\n    app: web\n  ports", "ClusterIP"),
    ("k6", "diagnostic.yaml", "cache: memoire", "cache: application", "cache"),
    ("k6", "manifests.yaml", "api:1.27.1", "api:1.27.O", "api"),
    ("k6", "manifests.yaml", "                  key: url\n", "                  key: password\n", "worker"),
    ("k6", "manifests.yaml", "memory: 2Gi\n            limits", "memory: 64Gi\n            limits", "batch"),
    ("k6", "manifests.yaml", "              memory: 256Mi", "              memory: 32Mi", "cache"),
    ("k6", "manifests.yaml", "  selector:\n    app: front\n  ports", "  selector:\n    app: frontend\n  ports", "front"),
    ("k7", "overlays/prod/kustomization.yaml", "newTag: \"1.5.0\"", "newTag: latest", "latest"),
    ("k7", "overlays/prod/kustomization.yaml", "namespace: prod\n", "", "namespace"),
    ("k7", "overlays/prod/kustomization.yaml", "count: 3", "count: 1", "count"),
    ("k7", "base/kustomization.yaml", "  - service.yaml\n", "", "service.yaml"),
    ("k7", "rbac.yaml", "verbs: [\"get\", \"list\", \"watch\", \"update\", \"patch\"]", "verbs: [\"*\"]", "\"*\""),
    ("k7", "rbac.yaml", "resources: [\"deployments\"]", "resources: [\"deployments\", \"secrets\"]", "secrets"),
    ("k7", "rbac.yaml", "roleRef:\n  kind: Role\n  name: deployer", "roleRef:\n  kind: ClusterRole\n  name: cluster-admin", "cluster-admin"),
    ("tf4", "main.tf", "  for_each = var.environments\n", "  count = 3\n", "count"),
    ("tf4", "main.tf", "${each.key}.conf", "conf", "each.key"),
    ("tf4", "variables.tf", "map(object({", "list(object({", "map(object"),
    ("tf4", "main.tf", "${local.out_dir}", "${local.autre}", "local.autre"),
    ("tf4", "outputs.tf", "{ for env, f in local_file.config : env => f.filename }", "local_file.config", "for"),
    ("tf5", "main.tf", "    use_lockfile = true\n", "", "verrou"),
    ("tf5", "main.tf", "    encrypt      = true\n", "    access_key   = \"X\"\n", "access_key"),
    ("tf5", "main.tf", "  environment = var.environment\n", "", "obligatoire environment"),
    ("tf5", "main.tf", "  app_name    = \"web\"\n", "  app_name    = \"web\"\n  replicas    = 3\n", "replicas"),
    ("tf5", "main.tf", "?ref=v1.2.0", "", "?ref="),
    ("tf5", "outputs.tf", "module.web.config_path", "module.web.path", "module.web.path"),
    ("tf5", "main.tf", "web/prod.tfstate", "terraform.tfstate", "key"),
    ("tf6", "variables.tf", ", \"prod\"]", "]", "prod"),
    ("tf6", "main.tf", "moved {\n  from = local_file.hello\n  to   = local_file.greeting\n}\n", "", "moved"),
    ("tf6", "main.tf", "    prevent_destroy = true\n", "    prevent_destroy = false\n", "prevent_destroy"),
    ("tf6", ".github/workflows/terraform.yml", "    if: github.ref == 'refs/heads/main' && github.event_name == 'push'\n", "", "refs/heads/main"),
    ("tf6", ".github/workflows/terraform.yml", "      - run: terraform validate\n", "", "validate"),
    ("tf6", ".github/workflows/terraform.yml", "    environment: production\n", "", "environment"),
    ("tf6", ".github/workflows/terraform.yml", "setup-terraform@b9cd54a3c349d3f38e8881555d616ced269862dd\n      - run: terraform fmt",
     "setup-terraform@v3\n      - run: terraform fmt", "SHA"),
    ("an1", "inventory.ini", "web2 ansible_host=10.0.1.12", "web2 ansible_host=10.0.1.12 ansible_password=x", "ansible_password"),
    ("an1", "inventory.ini", "[prod:children]\nweb\ndb", "[prod:children]\nweb", "prod:children"),
    ("an1", "site.yml", "ansible.builtin.apt:", "apt:", "nom complet"),
    ("an1", "site.yml", "        enabled: true\n", "", "enabled"),
    ("an1", "site.yml", "  become: true\n", "", "become"),
    ("an2", "site.yml", "      notify: Recharger nginx", "      notify: recharger nginx", "notify"),
    ("an2", "site.yml", "      changed_when: false\n", "", "changed_when"),
    ("an2", "site.yml", "        mode: \"0644\"", "        mode: 0644", "guillemets"),
    ("an2", "group_vars/web.yml", "nginx_port: 8080", "autre: 1", "nginx_port"),
    ("an3", "site.yml", "        validate: nginx -t -c %s\n", "", "validate"),
    ("an3", "site.yml", "      when: ansible_os_family == \"Debian\"", "      when: \"{{ ansible_os_family == 'Debian' }}\"", "accolades"),
    ("an3", "site.yml", "      loop: \"{{ admins }}\"", "      with_items: \"{{ admins }}\"", "with_items"),
    ("an3", "templates/nginx.conf.j2", "{% endfor %}", "", "endfor"),
    ("an3", "templates/nginx.conf.j2", "# Géré par Ansible", "#", "Géré par Ansible"),
    ("an4", "site.yml", "  roles:\n    - role: nginx\n", "  roles:\n    - role: nginx\n  tasks:\n    - name: x\n      ansible.builtin.ping:\n", "vivent dans le rôle"),
    ("an4", "roles/nginx/defaults/main.yml", "nginx_port: 80\n", "", "nginx_port"),
    ("an4", "requirements.yml", "    version: \"9.4.0\"\n", "", "version"),
    ("an4", "roles/nginx/handlers/main.yml", "Recharger nginx", "Relancer nginx", "notify"),
    ("an5", "group_vars/db/vars.yml", "\"{{ vault_db_password }}\"", "\"en-clair\"", "vault_db_password"),
    ("an5", "db.yml", "      no_log: true\n", "", "no_log"),
    ("an5", "db.yml", "  hosts: db\n", "  hosts: db\n  become: true\n", "become"),
    ("an5", "ansible.cfg", "inventory = inventory.ini\n", "inventory = inventory.ini\nhost_key_checking = False\n", "host_key_checking"),
    ("an5", ".gitignore", ".vault_pass\n", "", ".vault_pass"),
    ("an6", "deploy.yml", "  serial: 1\n", "", "serial"),
    ("an6", "deploy.yml", "  max_fail_percentage: 0\n", "  max_fail_percentage: 50\n", "max_fail_percentage"),
    ("an6", ".github/workflows/ansible.yml", "ansible-lint==24.9.2", "ansible-lint", "épinglée"),
    ("an6", ".github/workflows/ansible.yml", "      - run: ansible-playbook -i inventory.ini deploy.yml --syntax-check\n", "", "syntax-check"),
]


@pytest.mark.parametrize("tp,path,old,new,expected", MUT, ids=[f"{m[0]}-{i}" for i, m in enumerate(MUT)])
def test_faulty_variant_refused(tmp_path, tp, path, old, new, expected):
    ws = _solved(tmp_path, tp)
    assert _check(ws, tp)[0] == 0
    f = ws / path
    text = f.read_text(encoding="utf-8")
    assert old in text, old
    f.write_text(text.replace(old, new, 1), encoding="utf-8")
    code, out = _check(ws, tp)
    assert code == 1 and expected in out, out


def test_vault_tampered_refused(tmp_path):
    ws = _solved(tmp_path, "an5")
    v = ws / "group_vars" / "db" / "vault.yml"
    v.write_text('vault_db_password: "en clair"\n', encoding="utf-8")
    code, out = _check(ws, "an5")
    assert code == 1 and "pas chiffré" in out
