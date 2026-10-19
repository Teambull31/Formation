# Appli de formation gamifiée "zéro à héros" : design

Date : 2026-10-18. Statut : brouillon à valider.

## Intention et pourquoi

L'utilisateur a un TDAH et se forme seul. Ce qui a marché pour lui : une formation en ligne avec vidéo de cours (regardée en x2), page de cours imprimable, puis QCM. Ce qui le fait décrocher : trop de théorie sans application. Il veut une appli qui le garde accroché chaque jour, le fait pratiquer pour de vrai, et le mène de zéro à un niveau vendable.

Objectif à long terme : devenir intermédiaire puis expert DevOps (et SecOps si possible) pour se mettre à son compte. Outils visés : Docker, Kubernetes, Terraform, Ansible, plus CI/CD, monitoring, sécurité. Objectif à court terme : un premier module d'automatisation de tâches et de création d'agents IA pour l'entreprise, car l'utilisateur veut gagner du temps et réduire sa charge mentale au travail, pour libérer du temps de formation.

L'appli doit être générique : d'autres domaines s'ajoutent ensuite (Python, C, C++, ESP32…) avec le même format.

## Buts

- Séance quotidienne de 30 min (minimum) à 60 min (idéal), avec une quête réalisable, jamais une liste infinie.
- Chaque leçon combine : micro-leçon (texte bien écrit avec points clés en gras ou rouge, version audio ; vidéo dans une version ultérieure), fiche de révision imprimable, QCM, TP pratique dans un vrai terminal.
- Boucle de jeu de type gacha / level-up / Souls-like (voir plus bas), où la progression de jeu reflète des compétences réelles.
- Quand l'utilisateur se trompe (QCM ou TP) : explication du pourquoi, correction, mini-leçon ciblée, rappel plus tard.
- Parcours guidé par un objectif (ex. "expert DevOps") avec, chaque semaine, le sujet logique et plusieurs formats au choix pour l'apprendre. Possibilité d'imposer un sujet à tout moment.
- Un environnement d'exécution réel et gratuit sur le PC de l'utilisateur pour chaque domaine.
- Premier domaine livré : automatisation et agents IA (voir plus bas). Le DevOps vient ensuite.
- Fonction "Veille du jour" : synthèse courte et locale de sujets IA / DevOps, à lire à la place du scroll.

## Non-buts

- Pas de multi-utilisateur, pas de comptes, pas de cloud, pas d'hébergement public.
- Pas d'argent réel dans le gacha, aucun achat intégré.
- Pas de vraies vidéos de formateurs : vidéos générées uniquement.
- Pas de mini-jeu où l'on déplace un personnage en codant, dans la première version (idée pour plus tard).
- Pas d'accès aux mails professionnels de l'utilisateur par l'appli elle-même (voir confidentialité).

## Anti-buts (échecs même si "ça marche")

- Une séance de 30 min qui demande de réfléchir à quoi faire, ou qui déborde sans prévenir.
- Du hasard qui bloque la progression pédagogique (le gacha ne cache jamais de contenu de cours).
- Des corrections qui disent seulement "faux" sans expliquer.
- Des TP artificiels : l'utilisateur doit pouvoir réutiliser ce qu'il construit.
- Des récompenses ou une série qui punissent une pause (TDAH) : la série ne casse pas quand l'utilisateur impose un sujet ou prend un jour de repos annoncé.

## Contraintes

- Tout tourne en local sur le PC personnel de l'utilisateur (Linux, Fedora). L'appli n'est utilisée que là. L'entraînement ne se fait jamais sur le PC du travail.
- Accès depuis le téléphone, sur le réseau local, pour QCM, fiches et vidéos. Les TP au terminal restent sur le PC.
- Durée de séance : 30 min minimum, 60 min idéal, généralement à midi.
- Langue de l'interface et des contenus : français ; termes techniques en anglais.
- Gratuit à l'usage : pas de cloud payant pour les TP, pas de clé API payante obligatoire.

## IA et génération de contenu

- L'utilisateur a un abonnement Claude Code (pas une clé API) et Ollama avec Qwen3 14B sur son PC.
- **Génération des modules, deux modes au choix de l'utilisateur** (décision du 2026-10-19) : (1) par défaut, Qwen3 14B en local rédige le module (cours, fiches, QCM, énoncés de TP, scripts de vérification), puis l'abonnement Claude Code le relit et le corrige ; (2) option « Claude seul » : l'abonnement Claude Code rédige tout, sans Qwen. Le premier module (automatisation et agents) est entièrement produit par Claude, quel que soit le réglage. Seul du contenu de cours passe par Claude, jamais de données personnelles ou professionnelles.
- L'appli appelle Claude Code en ligne de commande sur le PC de l'utilisateur. Ce mode d'usage de l'abonnement est à confirmer auprès des conditions d'Anthropic avant construction. Si ce n'est pas autorisé, l'utilisateur s'en charge lui-même (décision du 2026-10-19) : chaque dimanche ou lundi, il lance Claude Code à part pour relire ou générer les cours de la semaine. L'appli doit donc rendre ce rituel simple : écran « Préparation de la semaine » qui produit le brief à donner à Claude Code (sujet, format choisi, niveau, erreurs récurrentes), et qui importe puis valide les fichiers produits (format, QCM complets, scripts de TP présents).
- Ollama + Qwen3 14B : tout ce qui se passe en direct pendant la séance (indices, explications d'erreurs, adversaire IA des combats, synthèses de veille). Qualité plus faible sur les sujets pointus : les corrections critiques s'appuient sur le contenu pré-généré, pas sur le modèle seul.

## Confidentialité

Les mails du travail de l'utilisateur sont sensibles et ne peuvent aller qu'à un outil local. Règles :
- Aucun mail réel n'est jamais envoyé à un service externe, y compris Claude Code.
- Les TP du module 1 utilisent des mails fictifs.
- L'agent mail construit pendant le module est un outil que l'utilisateur déploie ensuite lui-même à son poste de travail. Cela peut exiger l'accord du service informatique : l'appli le rappelle mais n'a pas à le trancher.

## Expérience d'une séance

Écrans validés en maquette : https://claude.ai/artifact/Bhd5SDeND78sKpvAvJhhMF (exemples de contenu uniquement).

- **Quête du jour** : rang, XP, série ; trois étapes : micro-leçon (3-5 min), QCM (≈5 questions), mini-TP (≈15 min) ; quête bonus de 30 min en plus ; choix du format de la semaine (vidéo + fiche + QCM, TP guidé, "répare l'infra cassée", projet fil rouge) ; champ "impose ton sujet".
- **Leçon** : cours écrit avec points clés en gras ou rouge et lecteur audio (voix de synthèse locale, vitesse réglable dont x2) ; la maquette montre une vidéo, prévue dans une version ultérieure ; fiche de révision, QCM avec correction, TP dans un terminal intégré avec indices progressifs (coût en XP).
- **Équipe** : personnage, compétences réelles en niveaux, équipement débloqué par les compétences validées, invocation (gacha).
- **Boss de palier** : défi pratique difficile, avec des "patterns" à apprendre.

## Boucle de jeu

Préférences exprimées : tirage surprise, montée en puissance de l'équipe, et battre un mode difficile grâce à cette montée en puissance (esprit Souls-like).

- XP et niveaux liés aux compétences réelles (par outil), gagnés par leçons, QCM, TP.
- Jetons gagnés par les quêtes ; l'invocation donne personnages et skins (cosmétique / collection). Pas de contenu pédagogique derrière le hasard.
- Équipement : outils et compétences débloqués par la validation réelle.
- Combats contre une IA : défis pratiques chronométrés (réparer un incident, finir un déploiement), adversaire piloté par Qwen3 en local. Le concepteur propose ce format ; le détail est laissé au constructeur.
- Rangs (Bronze à Expert), chacun fermé par un boss : un projet de portfolio réel (dépôt + README). Échec sans punition lourde ; l'appli nomme le pattern qui a fait échouer et propose la mini-leçon qui le contre.
- Prérequis recommandés avant un boss, mais l'utilisateur peut le tenter plus tôt.

## Gestion des erreurs et rappel

- Après une erreur : explication du pourquoi, indice ou correction, mini-leçon ciblée (texte court ou vidéo).
- L'appli mémorise les notions ratées et les repropose en QCM ou défi plus tard jusqu'à maîtrise (répétition espacée simple).

## Parcours et semaines

- L'utilisateur choisit un objectif ; l'appli en déduit la suite logique des semaines.
- Chaque semaine : un sujet et plusieurs formats d'apprentissage au choix.
- Sujet imposé : l'utilisateur saisit un sujet urgent ; l'appli monte une formation courte et ciblée, met le parcours principal en pause sans casser la série, puis le reprend.

## Premier module : automatisation et agents IA pour l'entreprise

- But : gagner du temps et réduire la charge mentale de l'utilisateur au travail.
- Fil rouge : de vraies tâches de l'utilisateur deviennent les TP, avec des données fictives dans l'appli.
- Progression : scripts et tâches planifiées, appels d'API, workflows, puis agents IA qui décident et agissent.
- Cas déjà exprimés : synthèse quotidienne des mails professionnels par un agent 100 % local (Outlook / Microsoft 365 confirmé ; connecteur Gmail aussi prévu) ; veille quotidienne perso (IA, DevOps) ; d'autres tâches répétitives, à détailler plus tard par l'utilisateur.
- Environnement des TP : Python, Ollama local, API de test. Pas de cloud.

## Modules suivants (hors première livraison)

DevOps : Docker, Kubernetes (mini-cluster jetable via kind ou k3d), Terraform (providers Docker / Kubernetes, sans cloud payant), Ansible (cibles : conteneurs faisant office de serveurs), puis CI/CD, monitoring, sécurité. Plus tard : Python, C, C++, ESP32 (matériel réel en USB).

## Choix de construction (décisions du concepteur, pas validées par l'utilisateur)

- Appli web locale, accessible depuis le téléphone sur le réseau local.
- Backend Python (FastAPI) ; frontend React ; terminal dans le navigateur (xterm.js) branché sur la machine ; SQLite pour progression, XP, erreurs.
- Contenu des modules en fichiers Markdown et JSON : un domaine s'ajoute sans toucher au code.
- Première version sans vidéo : cours écrits avec les informations importantes en gras ou en rouge, plus une version audio (voix de synthèse ou format podcast, générée en local) que l'utilisateur écoute, y compris en accéléré. Décision de l'utilisateur. La vidéo (diapos animées plus voix) vient dans une version suivante.
- Style visuel : voir la maquette (ardoise sombre, or pour les récompenses, vert terminal pour la progression), à titre indicatif.

## Décisions du concepteur après relecture (à vérifier par l'utilisateur)

- **Génération du contenu** : voir la section IA. Cela remplace ma décision précédente (génération uniquement hors de l'appli), changée par l'utilisateur le 2026-10-19.
- **Module 1 et mails** : les TP utilisent une source de mails fictive (JSON ou mbox) derrière une interface unique « source de mails ». Le module fournit deux connecteurs prêts à brancher, Outlook / Microsoft 365 et Gmail, et montre comment en écrire un autre. Le vrai plug and play dépend des droits côté entreprise : pour Outlook professionnel, le consentement administrateur et l'accès à l'API Microsoft Graph peuvent être bloqués par le service informatique. À défaut, le module montre pas à pas comment adapter. Décision du 2026-10-19 : les essais réels se font avec le compte Outlook personnel de l'utilisateur, en local uniquement (le contenu des mails ne quitte pas le PC et ne va jamais à Claude). Le module contient une fiche « du perso au pro » qui liste ce qui change pour un compte d'entreprise (enregistrement de l'application dans l'annuaire de l'entreprise, consentement administrateur, droits d'accès aux mails, règles d'accès conditionnel, accord du service informatique). La connexion au compte professionnel est faite par l'utilisateur à son travail, jamais depuis l'appli d'entraînement.
- **Validation des TP** : par vérifications scriptées (état du terminal ou des fichiers), un script de contrôle par TP. Le LLM local ne sert qu'aux indices et explications, jamais à juger la réussite.
- **Terminal** : accessible uniquement depuis le PC (localhost). Le téléphone sur le réseau local ne voit que QCM, fiches, vidéos et veille. Module 1 : shell de l'hôte. Modules DevOps : TP dans des conteneurs jetables.
- **Contenu de la première livraison** : le module 1 a son propre boss de rang Bronze uniquement ; les autres rangs viennent avec les modules suivants. Nombre de semaines du module 1 : à fixer dans le plan.
- **Jours de repos** : annoncés, illimités, sans pénalité.

## Laissé au constructeur

Découpage des versions et ordre de livraison, schéma de données, format exact des modules et des TP, mécanique précise du gacha et des combats, choix du moteur de voix de synthèse, sécurité du terminal intégré, sauvegarde et export de la progression, algorithme de répétition espacée.

## Questions ouvertes (signalées par le concepteur)

- Autorisation d'usage de l'abonnement Claude Code pour la génération de contenu depuis l'appli (voir plus haut).
- Machine perso : Ryzen 5 3600X, 32 Go de RAM, Radeon RX 7900 GRE (16 Go de mémoire vidéo). Qwen3 14B quantifié tient en mémoire vidéo avec de la marge, et la RAM reste libre pour Docker et kind. Le fonctionnement d'Ollama avec cette carte AMD sous Linux (ROCm) est à vérifier par le constructeur, mais l'utilisateur dit l'avoir déjà installé et testé.
- Les mails du travail sont dans Outlook (confirmé). Reste à savoir si le service informatique autorise un accès par API (Graph ou IMAP) pour l'agent.
- Liste des tâches répétitives réelles au travail (à fournir plus tard par l'utilisateur).
