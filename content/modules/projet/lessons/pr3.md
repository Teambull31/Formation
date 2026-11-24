# Projet fil rouge : déployer sur Kubernetes

L'image existe, testée et publiée. L'étape 3 la fait tourner sur un cluster, avec les réglages qu'un collègue attendrait en revue : **réplicas, sondes, ressources et sécurité**.

## Les trois fichiers

- `k8s/deployment.yaml` : 2 réplicas de l'image `ghcr.io/...:<sha>`, port 8000.
- `k8s/service.yaml` : un Service stable devant les pods.
- `k8s/kustomization.yaml` : la liste des ressources, pour `kubectl apply -k k8s/`.

## Ce qu'une revue vérifie

| Réglage | Pourquoi |
|---|---|
| `replicas: 2` | un pod tombe avec son nœud |
| `readinessProbe` sur `/healthz` | pas de trafic vers un pod pas prêt |
| `livenessProbe` | redémarrer un conteneur bloqué |
| requests et limits | placement prévisible, pas de voisin affamé |
| `runAsNonRoot`, `allowPrivilegeEscalation: false` | un conteneur compromis reste limité |

L'image est **la même** que celle publiée par la CI : c'est le SHA qui relie le commit au pod.

!!Un Deployment qui pointe vers latest peut faire tourner deux versions différentes après un simple redémarrage de nœud!!

## Le Deployment commenté

Ce fichier assemble les leçons k1 (structure), k2 (sondes) et k3 (sécurité). Les commentaires renvoient à la règle de placement.

```yaml
# Fichier : k8s/deployment.yaml
apiVersion: apps/v1
kind: Deployment
metadata:
  name: commandes
spec:                                        # ── DEPLOYMENT ──
  replicas: 2
  selector:
    matchLabels:
      app: commandes                         # ① doit égaler ② et le sélecteur du Service
  template:
    metadata:
      labels:
        app: commandes                       # ②
    spec:                                    # ── POD ──
      automountServiceAccountToken: false    # l'API n'a rien à faire du jeton
      securityContext:
        runAsNonRoot: true                   # vaut pour tous les conteneurs
        runAsUser: 10001                     # le même uid que USER 10001 du Dockerfile
      containers:
        - name: api                          # ── CONTENEUR ──
          image: ghcr.io/moncompte/commandes:3f2a9c1   # le SHA publié par la CI
          ports:
            - containerPort: 8000
          readinessProbe:                    # propriétés du conteneur : alignées sur image
            httpGet:
              path: /healthz
              port: 8000
          livenessProbe:
            httpGet:
              path: /healthz
              port: 8000
            initialDelaySeconds: 10          # aligné sur httpGet : réglage de la sonde
          resources:
            requests:
              cpu: 50m
              memory: 64Mi
            limits:
              cpu: 250m
              memory: 128Mi
          securityContext:                   # celui DU CONTENEUR
            allowPrivilegeEscalation: false
            readOnlyRootFilesystem: true
            capabilities:
              drop: ["ALL"]
```

```yaml
# Fichier : k8s/service.yaml
apiVersion: v1
kind: Service
metadata:
  name: commandes                # le nom utilisé par port-forward svc/commandes
spec:
  selector:
    app: commandes               # ③ = ① = ② : sinon aucun endpoint
  ports:
    - port: 80
      targetPort: 8000           # = containerPort
```

```yaml
# Fichier : k8s/kustomization.yaml
apiVersion: kustomize.config.k8s.io/v1beta1
kind: Kustomization
resources:                       # chemins relatifs au dossier k8s/
  - deployment.yaml
  - service.yaml
```

Remplacez `moncompte` et `3f2a9c1` par votre compte GitHub et le SHA réel : `git rev-parse HEAD` le donne, et l'onglet **Packages** liste les étiquettes publiées.

## Pas à pas : l'étape 3

1. Créez le dossier `k8s/` à la racine du dépôt.
2. Écrivez `deployment.yaml` en suivant les trois niveaux : Deployment, pod, conteneur. Vérifiez que l'uid du `securityContext` est celui du Dockerfile.
3. Écrivez `service.yaml` avec le même sélecteur que les étiquettes du pod.
4. Écrivez `kustomization.yaml` qui liste les deux fichiers.
5. Validez sans cluster : `kubeconform -strict k8s/deployment.yaml k8s/service.yaml`, puis `kubectl kustomize k8s/`.
6. Avec kind : appliquez, attendez le rollout, et appelez `/healthz` par `port-forward` (commandes ci-dessous).

## Le tester avec kind

```bash
kind create cluster --name formation
kubectl apply -k k8s/
kubectl rollout status deploy/commandes
kubectl port-forward svc/commandes 8080:80 &
curl -s http://127.0.0.1:8080/healthz
```

Un dépôt privé sur ghcr.io demande un `imagePullSecret` ; un dépôt public, rien.

!!Un livenessProbe trop agressif sur une application lente à démarrer la tue en boucle : donnez-lui un initialDelaySeconds!!

## Mettre à jour

Nouvelle version = nouveau SHA. On change l'image (à la main, avec `kustomize edit set image`, ou par Argo CD), et le rolling update remplace les pods un par un.

!!kubectl edit en production sans reporter le changement dans Git, c'est une dérive que le prochain apply effacera!!

## Labo réel

```bash
kubectl kustomize k8s/
kubectl get pods -l app=commandes -o wide
kubectl describe deploy/commandes
```

**À retenir :** l'image du SHA publié ; 2 réplicas, readiness et liveness ; requests et limits ; non-root ; sélecteur du Service identique aux étiquettes ; `kubectl apply -k` et `rollout status`.
