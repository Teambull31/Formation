# Fiche de révision : Kubernetes

## Les objets essentiels

- **Pod** : un ou plusieurs conteneurs qui partagent réseau et volumes. Jetable.
- **Deployment** : garde N pods identiques en vie, gère les mises à jour progressives.
- **StatefulSet** : pods à identité stable (`db-0`) avec un disque chacun.
- **DaemonSet** : un pod par nœud (agent de logs, supervision).
- **Job / CronJob** : tâche qui doit réussir une fois / selon un horaire.
- **Service** : adresse stable devant des pods choisis par **étiquettes**.
- **Ingress** : routeur HTTP(S) par domaine et chemin, devant les Services.
- **ConfigMap / Secret** : configuration et valeurs sensibles injectées dans les pods.
- **PVC** : demande de stockage durable ; la StorageClass crée le volume.
- **Namespace** : cloison logique (droits, quotas, noms).

## kubectl au quotidien

```bash
kubectl get pods -o wide -n shop
kubectl describe pod <pod>            # Events en bas
kubectl logs <pod> --previous         # journal avant le crash
kubectl logs -f deploy/web -c web     # suivre un conteneur
kubectl exec -it <pod> -- sh
kubectl port-forward svc/web 8080:80
kubectl apply -f fichier.yaml         # ou -k dossier/ (Kustomize)
kubectl diff -f fichier.yaml          # ce qui changerait
kubectl rollout status|history|undo deployment/web
kubectl get events --sort-by=.lastTimestamp
kubectl auth can-i <verbe> <ressource> --as=<sujet>
kubectl explain deployment.spec.strategy
```

## Deployment de production : la liste

- `replicas` ≥ 2 (ou un HPA, et alors **pas** de `replicas`).
- `selector.matchLabels` identique aux étiquettes du modèle de pod.
- Image avec tag précis ou digest, jamais `latest`.
- `resources.requests` et `limits` pour `cpu` et `memory`.
- `readinessProbe` (reçoit du trafic ?) et `livenessProbe` (redémarrer ?) avec `initialDelaySeconds`.
- `strategy.rollingUpdate` : `maxUnavailable: 0`, `maxSurge: 1`.
- Config par ConfigMap, mots de passe par `secretKeyRef`.
- !!Aucun Secret avec ses valeurs dans le dépôt : créé hors Git (Sealed Secrets, External Secrets, Vault)!!

## Durcissement

- Pod : `securityContext.runAsNonRoot: true`, `automountServiceAccountToken: false`.
- Conteneur : `allowPrivilegeEscalation: false`, `readOnlyRootFilesystem: true`, `capabilities.drop: ["ALL"]`.
- Interdits : `privileged: true`, `hostNetwork`, `hostPID`, `hostPath`.
- NetworkPolicy « tout refuser » (`podSelector: {}`, `policyTypes: [Ingress]`), puis autorisations précises (émetteur + port).

## Exposer et encaisser la charge

- Service `ClusterIP` (interne, défaut), `NodePort`, `LoadBalancer` (payant), headless `clusterIP: None`.
- `port` = port du Service, `targetPort` = port du conteneur.
- Ingress : `ingressClassName`, `host`, `pathType: Prefix`, `tls.secretName` (cert-manager).
- HPA `autoscaling/v2` : CPU en % de `requests.cpu`, besoin de metrics-server.
- PodDisruptionBudget `policy/v1` : `minAvailable` ou `maxUnavailable`, sélecteur sur les pods.
- Répartition : `topologySpreadConstraints` ou `podAntiAffinity`.

## Stockage et tâches

- `emptyDir` meurt avec le pod ; PVC `ReadWriteOnce` pour une base.
- StatefulSet : `serviceName` vers un Service headless, `volumeClaimTemplates` du même nom que le `volumeMounts`.
- Supprimer un StatefulSet garde les PVC.
- CronJob : cron à 5 champs, `concurrencyPolicy: Forbid`, `backoffLimit`, `activeDeadlineSeconds`, `restartPolicy: OnFailure`.

## Dépannage : symptôme, cause

- `ImagePullBackOff` : tag inexistant, registre, `imagePullSecrets`.
- `CrashLoopBackOff` : l'application plante, lire `logs --previous` (variable, config, dépendance).
- `Pending` : planification, lire les Events (mémoire/CPU, taint, affinité, PVC non lié).
- `OOMKilled`, code `137` : `limits.memory` dépassée.
- Code `143` : SIGTERM, arrêt normal. Code `1` : erreur applicative.
- Endpoints `<none>` : sélecteur du Service faux, ou pods pas prêts.
- `CreateContainerConfigError` : ConfigMap ou Secret référencé absent.
- !!Corriger dans le dépôt, pas avec kubectl edit : sinon le prochain déploiement écrase la correction!!

## Livrer par environnement

- Kustomize : `base/` + `overlays/<env>/` avec `namespace`, `images.newTag`, `replicas`, `patches`.
- `kubectl kustomize overlays/prod` pour relire avant d'appliquer.
- Helm : `helm upgrade --install <nom> <chart> --version X -f values.yaml -n <ns>`, `helm rollback`.
- GitOps (Argo CD, Flux) : le cluster suit Git ; retour arrière = `git revert`.

## RBAC

- Role (namespace) / ClusterRole (cluster) ; RoleBinding / ClusterRoleBinding.
- Sujets : User, Group, ServiceAccount (`system:serviceaccount:<ns>:<nom>`).
- Pas de `*`, pas de `secrets` sans raison, pas de `cluster-admin` pour une CI.
- !!Le droit de créer des pods permet de lire tous les Secrets du namespace en les montant!!

## Questions d'entretien

- Différence readiness / liveness / startup probe ?
- Que se passe-t-il pendant un `kubectl apply` d'une nouvelle image ?
- Deployment ou StatefulSet pour PostgreSQL, et pourquoi ?
- Un Service ne répond pas : votre méthode ?
- Comment donner à une CI le droit de déployer sans lui donner le cluster ?
