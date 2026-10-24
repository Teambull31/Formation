# Parcours domotique « de zéro à héros » (ESP32, ESP-IDF, simulé)

Date : 2026-10-25. Statut : brouillon à valider.

## Intention

Formation est une app de formation gamifiée (leçons courtes, QCM, TP vérifiés automatiquement, boss). On y ajoute un parcours de domotique qui part de zéro et mène à un contrôleur ESP32 prêt à être livré chez un client.

Le porteur du projet apprend en construisant des choses utiles à de vraies personnes (exemple fondateur : remplir automatiquement la piscine de son père pour qu'elle reste au bon niveau). Son objectif à terme est d'installer et de vendre une domotique qu'il a programmée lui-même. Le parcours doit donc aussi bien servir à des débutants curieux qu'à lui-même, et valoir sur un CV : on y apprend ESP-IDF, le framework officiel d'Espressif, pas une version simplifiée.

Le matériel n'est pas nécessaire. Tout est simulé dans l'app. Le vrai matériel viendra plus tard, sans que le cours change.

## Objectifs

1. Un apprenant sans connaissance de l'embarqué arrive, en 4 modules de 3 leçons, à écrire en C++ moderne (C++17) un contrôleur ESP32 qui lit des capteurs, commande un relais, parle MQTT sur TLS et se met à jour par OTA.
2. Le code écrit par l'apprenant est du vrai code ESP-IDF : il doit pouvoir être copié dans un vrai projet ESP-IDF sans modification. Le simulateur imite l'API réelle (mêmes noms, mêmes signatures, mêmes codes d'erreur `esp_err_t`).
3. **Clarté et guidage avant tout.** Chaque leçon contient toute la théorie nécessaire pour résoudre ses TP, sans rien supposer connu en dehors des leçons précédentes. La leçon sert aussi de fiche de révision : on peut la relire seule pour refaire le TP. Chaque TP est découpé en étapes numérotées, les indices sont gradués, et les messages d'erreur du contrôle disent en français ce qui ne va pas et quelle section de la leçon relire.
4. Des projets concrets plutôt que des exercices abstraits : LED, bouton, capteur de niveau d'eau, relais de pompe, régulation de piscine, boss final.
5. Les TP s'exécutent pour de vrai : le code de l'apprenant est compilé avec `g++` contre un faux ESP-IDF, puis lancé dans un scénario scripté (capteurs qui évoluent, pannes). Le contrôle vérifie ce que le programme a fait (broches, journaux, messages MQTT, états après panne), pas seulement son texte.
6. Le parcours s'intègre à l'app existante comme les autres modules (modules, QCM, TP, boss, portfolio, révision espacée), sans nouvel écran spécifique sauf si le format actuel ne suffit pas pour afficher la sortie de simulation.

## Hors périmètre

- Aucun flashage et aucun vrai matériel dans cette version.
- Ni Arduino, ni MicroPython (ajoutables plus tard sur demande).
- Ni Zigbee, ni Matter, ni Home Assistant.
- Le projet existant `Teambull31/Domotique` (dashboard ESP32, MQTT, FastAPI, React) n'est pas modifié ici. C'est un second projet, traité plus tard. On réutilise seulement son format de messages MQTT comme fil conducteur : `home/devices/<device_id>/telemetry`, `.../status` (last will `online`/`offline`), `.../command`.
- Pas de nouvel écran de visualisation 3D ni de schéma électronique animé.

## Anti-objectifs (ce qui serait un échec même si tout « marche »)

- Un simulateur dont l'API diverge du vrai ESP-IDF : l'apprenant écrirait du code qui compile dans l'app mais pas sur un vrai ESP32.
- Une leçon qui ne donne pas assez de théorie pour résoudre son TP, ou un TP qui exige de deviner.
- Un contrôle qu'on peut tromper en écrivant en dur le résultat attendu. Chaque contrôle est donc testé avec des variantes fautives de la solution (même méthode que les modules existants : suites de mutations).
- Un simulateur non déterministe (résultats qui changent d'une exécution à l'autre).
- Un contrôle qui exécute du code d'apprenant sans limites (temps, mémoire, fichiers).
- Un parcours trop simplifié, façon Arduino, qui cache la gestion d'erreurs, les tâches et le temps réel.

## Contraintes

- Contenu en français, avec les accents. Termes techniques et identifiants de code en anglais.
- Même format de contenu que les modules existants (voir `content/modules/docker`) : `module.json`, leçons `.md` avec paires de surlignage `!!...!!`, QCM `.qcm.json`, TP avec `tp.json`, `check.sh`, `solution.sh`, dossier `seed/`. Boss dans `content/boss/` sur le modèle de `docker_boss`.
- Chaque module est livré avec ses tests : validation de structure, solution qui passe, suite de variantes fautives qui échouent. La suite de tests du backend (625 tests) reste verte.
- Les TP actuels sont des analyses statiques, sans exécution. Ici, le code d'apprenant est compilé et exécuté : c'est une nouvelle classe de risque, à traiter explicitement (voir « Exécution et sécurité »).
- `g++` est présent sur la machine de développement et sur le VPS de production.
- Le contrôle d'export portfolio filtre les secrets : les TP de TLS manipulent des certificats et des identifiants factices, il faut s'assurer que le filtre ne bloque pas à tort, et que de faux secrets ne soient jamais présentés comme réels.

## Le parcours (décidé avec le porteur du projet)

Chaque module a 3 leçons, chacune avec un QCM et un TP.

**Module 1 : bases de l'ESP.** `app_main` et `ESP_LOGI`. Piloter une LED en GPIO. Lire un bouton avec anti-rebond. Tâches FreeRTOS et `vTaskDelay`, sans jamais bloquer.

**Module 2 : capteurs et contrôle.** Lire un capteur (ADC, I2C). Commander un relais. Écrire une régulation avec hystérésis, jusqu'à la piscine qui se remplit seule sans déborder.

**Module 3 : connecté et fiable.** Wi-Fi puis MQTT (client `esp_mqtt`, boucle d'événements) avec les topics de l'ancien projet. Reconnexion, watchdog, sauvegarde en NVS, gestion des erreurs `esp_err_t`.

**Module 4 : livrable chez un client.** TLS : MQTT sur TLS avec vérification du certificat serveur, aucun secret dans le code, gestion d'un échec de handshake. OTA : `esp_https_ota`, table de partitions à deux slots, contrôle de version et de signature, retour automatique à l'ancienne version si la nouvelle plante.

**Boss final** (en fin de module 4) : un contrôleur de piscine complet, évalué avec des pannes simulées : capteur bloqué, MQTT coupé, image OTA corrompue, coupure de courant pendant l'OTA, certificat invalide. Dans tous les cas, le relais doit retomber en état sûr (pas de débordement).

## Exécution et sécurité

Le TP compile le code de l'apprenant avec `g++ -std=c++17` contre un faux ESP-IDF, puis exécute le programme contre un scénario scripté. Le programme n'a ni réseau, ni accès hors de son dossier de travail ; il est limité en temps et en mémoire.

C'est une décision à laquelle le porteur du projet doit être attentif : sur le VPS, l'exécution distante (`FORMATION_REMOTE_EXEC=1`) est déjà activée pour permettre de faire les TP depuis un téléphone sur Tailscale. Compiler et lancer du C++ arbitraire est plus puissant qu'analyser du texte. Le garde-fou existant (route réservée aux pairs autorisés, mot de passe) s'applique, et on y ajoute des limites de ressources. **Décision du porteur du projet : les TP C++ restent bloqués en exécution distante dans la première version.** Ils ne tournent qu'en local, jusqu'à ce que les tests du sandbox prouvent qu'il tient. L'ouverture à distance se fait ensuite, dans un changement séparé. Le niveau d'isolation (voir « Décisions prises par le concepteur ») doit être justifié et testé : un programme qui boucle à l'infini, alloue toute la mémoire, lit un fichier hors de son dossier ou tente une connexion réseau ne doit pas passer.

## Le simulateur (faux ESP-IDF)

- Sous-ensemble de l'API réelle, juste ce que les leçons utilisent : `esp_log`, `driver/gpio`, ADC, I2C, FreeRTOS (`xTaskCreate`, `vTaskDelay`, files, sémaphores), `nvs_flash`, Wi-Fi et événements, `esp_mqtt_client`, `esp_http_client`/`esp_https_ota`, `esp_ota_ops`, `esp_task_wdt`.
- Les signatures et les codes de retour suivent ESP-IDF v5.x. Le constructeur doit vérifier chaque signature dans la documentation officielle, pas de mémoire.
- **Temps virtuel et déterminisme.** `vTaskDelay` n'attend pas pour de vrai : le simulateur avance une horloge virtuelle quand toutes les tâches sont bloquées. Un TP de 10 minutes simulées s'exécute en quelques millisecondes et donne toujours le même résultat.
- **Scénario scripté** : qui change quoi et quand (valeur d'un capteur à la seconde N, coupure du broker, image OTA invalide, etc.).
- **Trace** : le simulateur enregistre ce que fait le programme (écritures GPIO horodatées, journaux, messages MQTT publiés, partition active). Le contrôle fait ses vérifications sur cette trace.
- Les contrôles complètent la trace par quelques vérifications statiques ciblées quand le comportement ne se voit pas à l'exécution, par exemple « la vérification du certificat n'est pas désactivée » ou « pas de mot de passe écrit en dur ».

## Clarté pédagogique (exigence centrale)

Chaque leçon respecte ce gabarit :

1. Le problème concret du TP en une phrase (« la pompe doit s'arrêter quand le bassin est plein »).
2. Les notions, expliquées dans l'ordre où le TP en a besoin, avec petits exemples de code annotés.
3. Une mini-référence des fonctions ESP-IDF employées : nom, signature, ce qu'elle renvoie, erreurs possibles.
4. Les pièges classiques, mis en évidence avec `!!...!!`.
5. « À retenir » en fin de leçon, servant de fiche de révision.

Chaque TP : énoncé en étapes numérotées avec case de validation implicite par le contrôle ; 3 indices du plus vague au plus précis ; fichier de départ qui cache l'infrastructure au début et la révèle progressivement ; messages d'erreur du contrôle qui nomment la cause (« le relais est resté fermé après la seconde 40 ») et renvoient à la section de la leçon.

## Faits vérifiés dans le projet et sur le VPS

- **Fonctionnement d'un TP.** `backend/app/tp.py` lance la commande `check` du `tp.json` avec la variable `LESSON_DIR` et une limite `timeout_s` propre à chaque TP. Chaque module garde un contrôleur partagé à côté de ses leçons (`_docker_check.py` pour Docker) que les `check.sh` appellent. Le simulateur suit le même principe : une seule copie partagée (dossier `sim/` ou équivalent sous `content/`), jamais dupliquée dans chaque TP. Le temps de compilation compte dans `timeout_s` ; une compilation en cache (en-têtes précompilés) est probablement nécessaire.
- **Outils d'isolation.** `bwrap` (bubblewrap), `unshare` et `docker` sont installés sur le VPS ; `bwrap` l'est aussi en local. Les espaces de noms utilisateur sont activés (`user.max_user_namespaces` élevé). Le VPS a 4 cœurs, ~7,7 Go de RAM et `g++` 15.
- **ESP-IDF.** Aucune chaîne de compilation ESP-IDF (`idf.py`) ni QEMU Xtensa n'est installé, ni en local ni sur le VPS. La fidélité de l'API ne peut donc être prouvée que par relecture de la documentation officielle, pas par une vraie compilation.
- **Filtre d'export portfolio.** `leak_reason` (dans `backend/app/portfolio.py`) rejette adresses e-mail réelles et secrets en clair, et accepte les valeurs factices reconnues comme « placeholder » ainsi que les adresses `@example.test`. Il est dans le périmètre : on peut l'adapter, avec ses propres tests, si les TP TLS en ont besoin.

## Décisions prises par le concepteur (à relire)

Ces points sont des choix du concepteur, pas des décisions du porteur du projet :

- **Ordonnancement du simulateur.** Vrais threads, mais un seul s'exécute à la fois (passage de témoin), avec horloge virtuelle qui avance quand toutes les tâches attendent. Cela garantit le déterminisme tout en gardant du C++ ordinaire. Une boucle sans `vTaskDelay` est interrompue par une limite de temps réel par tranche d'exécution et signalée par un message clair (« votre tâche ne rend jamais la main : ajoutez un `vTaskDelay` »). Le fichier de l'apprenant définit `extern "C" void app_main()` ; le harnais fournit `main`.
- **Sandbox.** `bwrap` sans réseau, système de fichiers en lecture seule sauf le dossier de travail, limites `ulimit` (processeur, mémoire, taille de fichier, nombre de processus) et délai. Le compilateur tourne dans le même cadre, avec une liste blanche d'en-têtes (`-nostdinc` plus chemins explicites) et une limite de temps de compilation.
- **Version d'ESP-IDF visée.** La dernière version stable 5.x connue du constructeur au moment de la construction, avec les API actuelles (ADC oneshot, nouveau pilote I2C maître), pas les pilotes dépréciés. Chaque signature est vérifiée dans la documentation officielle (outil de documentation Context7 ou site d'Espressif).
- **En-têtes du faux ESP-IDF.** Écrits à la main, réduits au sous-ensemble utilisé. Un tableau de signatures vérifiées avec leur source accompagne le code, et un test compare les signatures du simulateur à ce tableau.
- **Affichage de la simulation.** Texte seul d'abord : chronologie lisible dans la sortie du contrôle. L'interface n'est modifiée que si ce n'est pas lisible.
- **Livraison par étapes.** Un seul plan, en tranches : (1) simulateur, sandbox et module 1 ; (2) module 2 ; (3) module 3 ; (4) module 4 et boss. Chaque tranche est testée, revue et déployable seule. Le module 1 peut sortir seul si la suite prend du retard.
- **Certificats de test (TLS).** Générés à l'exécution dans le dossier de travail du TP, jamais écrits en clair dans le contenu, afin de ne pas déclencher le filtre portfolio ni présenter de faux secrets comme réels.

## À la charge du constructeur

- Noms des modules et des leçons (identifiants), organisation interne du code du simulateur, choix entre un harnais en C++ pur ou piloté par Python.
- Mise en page exacte des messages d'erreur et des indices.
- Contenu précis des QCM et des scénarios, dans le respect du parcours ci-dessus.
- Niveau d'isolation de l'exécution (voir plus haut), avec justification et tests.
- Utilisation des revues ECC (relecture de code, sécurité) pendant la construction, en particulier sur le sandbox d'exécution et sur le contrôle d'export portfolio.
