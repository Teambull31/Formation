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
