#!/usr/bin/env bash
# Solution de référence du TP k2.
set -euo pipefail
cat > app.yaml <<'EOF'
apiVersion: v1
kind: ConfigMap
metadata:
  name: web-config
data:
  APP_MODE: production
---
apiVersion: apps/v1
kind: Deployment
metadata:
  name: web
spec:
  replicas: 2
  selector:
    matchLabels:
      app: web
  template:
    metadata:
      labels:
        app: web
    spec:
      containers:
        - name: web
          image: ghcr.io/example/web:1.4.2
          ports:
            - containerPort: 8000
          resources:
            requests:
              cpu: 100m
              memory: 128Mi
            limits:
              cpu: 500m
              memory: 256Mi
          env:
            - name: APP_MODE
              valueFrom:
                configMapKeyRef:
                  name: web-config
                  key: APP_MODE
            - name: DB_PASSWORD
              valueFrom:
                secretKeyRef:
                  name: web-db
                  key: password
          readinessProbe:
            httpGet:
              path: /healthz
              port: 8000
          livenessProbe:
            httpGet:
              path: /healthz
              port: 8000
            initialDelaySeconds: 10
---
apiVersion: v1
kind: Service
metadata:
  name: web
spec:
  selector:
    app: web
  ports:
    - port: 80
      targetPort: 8000
EOF
