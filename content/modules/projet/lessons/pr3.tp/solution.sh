#!/usr/bin/env bash
# Solution de référence, étape 3 du projet : les manifestes Kubernetes.
set -euo pipefail
LESSON_DIR="$LESSON_DIR/../pr2.tp" bash "$LESSON_DIR/../pr2.tp/solution.sh"
mkdir -p k8s
cat > k8s/deployment.yaml <<'K'
apiVersion: apps/v1
kind: Deployment
metadata:
  name: commandes
spec:
  replicas: 2
  selector:
    matchLabels:
      app: commandes
  template:
    metadata:
      labels:
        app: commandes
    spec:
      automountServiceAccountToken: false
      securityContext:
        runAsNonRoot: true
        runAsUser: 10001
      containers:
        - name: api
          image: ghcr.io/moncompte/commandes:3f2a9c1
          ports:
            - containerPort: 8000
          readinessProbe:
            httpGet:
              path: /healthz
              port: 8000
          livenessProbe:
            httpGet:
              path: /healthz
              port: 8000
            initialDelaySeconds: 10
          resources:
            requests:
              cpu: 50m
              memory: 64Mi
            limits:
              cpu: 250m
              memory: 128Mi
          securityContext:
            allowPrivilegeEscalation: false
            readOnlyRootFilesystem: true
            capabilities:
              drop: ["ALL"]
K
cat > k8s/service.yaml <<'K'
apiVersion: v1
kind: Service
metadata:
  name: commandes
spec:
  selector:
    app: commandes
  ports:
    - port: 80
      targetPort: 8000
K
cat > k8s/kustomization.yaml <<'K'
apiVersion: kustomize.config.k8s.io/v1beta1
kind: Kustomization
resources:
  - deployment.yaml
  - service.yaml
K
