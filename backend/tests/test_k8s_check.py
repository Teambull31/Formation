"""The Kubernetes checker must refuse each unsafe or incomplete variant of the reference manifests."""
import re
import subprocess
import sys
from pathlib import Path

import pytest

MODULES = Path(__file__).resolve().parents[2] / "content" / "modules"
LESSONS = MODULES / "k8s" / "lessons"
CHECKER = LESSONS / "_k8s_check.py"


def test_yaml_reader_copies_are_identical():
    assert (LESSONS / "_yaml.py").read_bytes() == (MODULES / "cicd" / "lessons" / "_yaml.py").read_bytes()


def _solution(tp: str) -> dict[str, str]:
    text = (LESSONS / f"{tp}.tp" / "solution.sh").read_text(encoding="utf-8")
    return {m.group(1): m.group(2) + "\n" for m in re.finditer(r"cat > (\S+) <<'EOF'\n(.*?)\nEOF", text, re.S)}


def run(tmp_path, tp, files):
    for name, text in files.items():
        (tmp_path / name).write_text(text, encoding="utf-8")
    r = subprocess.run([sys.executable, "-I", "-B", str(CHECKER), tp], cwd=tmp_path, capture_output=True, text=True, timeout=20)
    return r.returncode, r.stdout


@pytest.mark.parametrize("tp", ["k1", "k2", "k3"])
def test_reference_solution_passes(tmp_path, tp):
    code, out = run(tmp_path, tp, _solution(tp))
    assert code == 0, out


MUT = [
    ("k1", "deployment.yaml", "replicas: 2", "replicas: 1", "au moins 2"),
    ("k1", "deployment.yaml", "      app: web\n  template", "      app: other\n  template", "ne correspond pas"),
    ("k1", "deployment.yaml", ":1.4.2", ":latest", "latest"),
    ("k1", "deployment.yaml", ":1.4.2", "", "pas de tag"),
    ("k1", "deployment.yaml", "              memory: 256Mi\n", "", "limits.memory"),
    ("k1", "deployment.yaml", "            requests:\n              cpu: 100m\n              memory: 128Mi\n", "", "requests.cpu"),
    ("k1", "deployment.yaml", "containerPort: 8000", "containerPort: 80", "port"),
    ("k1", "deployment.yaml", "apiVersion: apps/v1", "apiVersion: v1", "apps/v1"),
    ("k1", "deployment.yaml", "  replicas: 2\n  selector:\n    matchLabels:", "  replicas: 2\n  selector:\n  matchLabels:", "matchLabels"),
    ("k2", "app.yaml", "                  key: APP_MODE\n", "                  key: AUTRE\n", "APP_MODE"),
    ("k2", "app.yaml", "            - name: DB_PASSWORD\n              valueFrom:\n                secretKeyRef:\n                  name: web-db\n                  key: password\n",
     "            - name: DB_PASSWORD\n              value: hunter2\n", "valeur en clair"),
    ("k2", "app.yaml", "          readinessProbe:\n            httpGet:\n              path: /healthz\n              port: 8000\n", "", "readinessProbe"),
    ("k2", "app.yaml", "            initialDelaySeconds: 10\n", "", "initialDelaySeconds"),
    ("k2", "app.yaml", "            initialDelaySeconds: 10\n", "            initialDelaySeconds: 1\n", "initialDelaySeconds"),
    ("k2", "app.yaml", "    app: web\n  ports:", "    app: autre\n  ports:", "sélecteur du Service"),
    ("k2", "app.yaml", "      targetPort: 8000", "      targetPort: 9000", "targetPort"),
    ("k2", "app.yaml", "  selector:\n    app: web\n  ports:", "  type: LoadBalancer\n  selector:\n    app: web\n  ports:", "ClusterIP"),
    ("k2", "app.yaml", "kind: ConfigMap", "kind: Secret\nstringData:\n  A: b", "ConfigMap"),
    ("k3", "deployment.yaml", "      automountServiceAccountToken: false\n", "", "automountServiceAccountToken"),
    ("k3", "deployment.yaml", "        runAsNonRoot: true", "        runAsNonRoot: false", "runAsNonRoot"),
    ("k3", "deployment.yaml", "            allowPrivilegeEscalation: false\n", "", "allowPrivilegeEscalation"),
    ("k3", "deployment.yaml", "readOnlyRootFilesystem: true", "readOnlyRootFilesystem: false", "readOnlyRootFilesystem"),
    ("k3", "deployment.yaml", "drop: [\"ALL\"]", "drop: [\"NET_RAW\"]", "drop"),
    ("k3", "deployment.yaml", "            readOnlyRootFilesystem: true\n", "            readOnlyRootFilesystem: true\n            privileged: true\n", "privileged"),
    ("k3", "deployment.yaml", "      automountServiceAccountToken: false\n", "      automountServiceAccountToken: false\n      hostNetwork: true\n", "hostNetwork"),
    ("k3", "deployment.yaml", "      automountServiceAccountToken: false\n",
     "      automountServiceAccountToken: false\n      volumes:\n        - name: h\n          hostPath:\n            path: /\n", "hostPath"),
    ("k3", "networkpolicy.yaml", "  podSelector: {}\n  policyTypes: [\"Ingress\"]\n---", "  podSelector: {}\n  policyTypes: [\"Ingress\"]\n  ingress:\n    - {}\n---", "tout refuser"),
    ("k3", "networkpolicy.yaml", "              app: gateway", "              app: ", "from"),
    ("k3", "networkpolicy.yaml", "        - port: 8000", "        - port: 22", "port"),
    ("k3", "networkpolicy.yaml", "    - from:\n        - podSelector:\n            matchLabels:\n              app: gateway\n      ports:", "    - ports:", "from"),
]


@pytest.mark.parametrize("tp,name,old,new,expected", MUT, ids=[f"{m[0]}-{i}" for i, m in enumerate(MUT)])
def test_unsafe_variant_refused(tmp_path, tp, name, old, new, expected):
    files = _solution(tp)
    assert old in files[name], f"mutation does not apply: {old!r}"
    files[name] = files[name].replace(old, new, 1)
    code, out = run(tmp_path, tp, files)
    assert code == 1 and expected in out, out
