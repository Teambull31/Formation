# MQTT : publier, s'abonner, annoncer son statut et obéir sans danger

**Le problème concret :** votre contrôleur de piscine est sur le Wi-Fi (leçon précédente). Il doit maintenant **parler** : envoyer le niveau d'eau toutes les 10 secondes à l'application de la maison, dire s'il est en ligne ou non, et **recevoir des ordres** (« allume le relais »). Il faut le faire sans que la maison ait besoin de connaître l'adresse de la carte, sans que la carte ait besoin de connaître l'application, et sans qu'un ordre malheureux fasse déborder la piscine. Le protocole standard de la domotique pour cela s'appelle **MQTT**.

Cette leçon contient toute la théorie du TP. Lisez-la dans l'ordre : les messages du contrôle vous disent quelle section relire. Elle suppose les leçons précédentes : le Wi-Fi et les gestionnaires d'événements (TP 7), le relais sur la GPIO 5 et la **limite de sécurité de 80 %** (TP 6), la lecture du niveau avec l'ADC et son étalonnage (TP 4).

Tout ce qui est écrit ici est le vrai ESP-IDF (version 5.5.3) : le client `esp-mqtt`, les mêmes fonctions, les mêmes événements, les mêmes champs de configuration. L'exemple officiel `examples/protocols/mqtt/tcp` en montre le squelette ; ce qu'il fait exactement est décrit dans la section sur la configuration. Le TP, lui, tourne dans le simulateur, qui joue le rôle du **courtier** (le serveur MQTT) ; ce qu'il simplifie est listé à part, dans « Ce que le simulateur simplifie ».

**Honnêteté sur le Wi-Fi.** MQTT a besoin d'un réseau, donc du Wi-Fi. Le TP ne vous fait pas refaire le TP 7 : **main.cpp** contient déjà une fonction `wifi_connecter()`, une version **minimale** du TP 7 (même initialisation, mais sans l'attente croissante entre les essais : la box de ce TP répond toujours). Elle bloque jusqu'à ce que l'adresse IP soit obtenue. Dans un vrai projet, vous reprendriez votre version complète.

## La vue d'ensemble : un courtier, des sujets, des messages

MQTT repose sur trois idées.

1. **Un courtier** (*broker*) : un serveur central, dans la maison ou sur Internet. Personne ne parle directement à personne : tous les appareils parlent au courtier.
2. **Des sujets** (*topics*) : des noms qui ressemblent à des chemins, avec des `/` : `home/devices/pool-ctl/telemetry`. Les majuscules comptent. Un sujet n'a pas besoin d'être créé : il existe dès qu'on y publie.
3. **Publier et s'abonner** : un client **publie** un message (une charge utile, *payload*, d'octets quelconques) sur un sujet ; le courtier le transmet à tous les clients **abonnés** à ce sujet.

Un client peut s'abonner à un **filtre** qui contient des jokers : `+` remplace **un** niveau (`home/devices/+/status`), `#` remplace **tout le reste** (`home/devices/#`). Les jokers n'existent que dans les abonnements : on publie toujours sur un sujet précis.

Les trois sujets du TP :

| Sujet | Qui publie | Contenu |
|---|---|---|
| `home/devices/pool-ctl/telemetry` | la carte | le JSON `{"level": 72.5, "relay": false}`, toutes les 10 s |
| `home/devices/pool-ctl/status` | la carte | le texte `online` (ou `offline`, publié par le courtier si la carte disparaît) |
| `home/devices/pool-ctl/command` | l'application | une commande : `{"relay": true}` ou `{"relay": false}` |

La carte est donc à la fois **éditrice** (télémétrie, statut) et **abonnée** (commandes).

## Le client ESP-IDF : configuration et démarrage

Le composant `esp-mqtt` fournit un **client** : un objet (`esp_mqtt_client_handle_t`) qui gère la connexion au courtier, les paquets, les reconnexions. Quatre étapes, toujours les mêmes :

1. **Remplir** un `esp_mqtt_client_config_t` (mettre à zéro avec `= {}`, puis renseigner les champs utiles).
2. **Créer** le client : `esp_mqtt_client_init(&cfg)`.
3. **Enregistrer** votre gestionnaire d'événements : `esp_mqtt_client_register_event(client, (esp_mqtt_event_id_t)ESP_EVENT_ANY_ID, gestionnaire, NULL)`.
4. **Démarrer** : `esp_mqtt_client_start(client)`. Le client crée sa **propre tâche**, `mqtt_task`, et se connecte tout seul.

Les champs de configuration du TP (les noms sont ceux de la vraie structure) :

```cpp
esp_mqtt_client_config_t cfg = {};
cfg.broker.address.uri = "mqtt://192.168.1.10:1883";  // où est le courtier
cfg.credentials.client_id = "pool-ctl";                // l'identité de la carte
cfg.session.last_will.topic = "home/devices/pool-ctl/status";  // le testament (voir plus bas)
cfg.session.last_will.msg = "offline";
cfg.session.last_will.qos = 1;
cfg.session.last_will.retain = true;
```

- **L'URI** a la forme `schéma://hôte:port`. Le schéma `mqtt://` veut dire MQTT sur TCP, sans chiffrement, port 1883 par défaut ; `mqtts://` est la version chiffrée (port 8883 par défaut), que le simulateur n'a pas. Le courtier du TP est simulé : l'adresse `192.168.1.10` est une valeur d'exemple.
- **L'identifiant du client** (`client_id`) : le courtier n'accepte qu'**un** client par identifiant. Si deux appareils prennent le même, le courtier coupe l'ancien. Par défaut ESP-IDF en fabrique un, `ESP32_` suivi des trois derniers octets de l'adresse MAC ; le TP en fixe un lisible.
- **Les reconnexions sont automatiques** : si la connexion tombe, le client réessaie tout seul toutes les 10 secondes (champ `network.reconnect_timeout_ms`, 10 s par défaut) tant que vous n'avez pas mis `network.disable_auto_reconnect` à `true`. Vous n'avez pas à écrire de boucle de reconnexion.
- **La session est propre par défaut** (`session.disable_clean_session` vaut `false`) : à chaque connexion, le courtier **oublie** tout ce qu'il savait de ce client, abonnements compris. C'est la raison du réflexe décrit dans « S'abonner, et se réabonner après une coupure ».

**L'exemple officiel `mqtt/tcp`**, tel qu'il est écrit : `app_main` initialise la NVS (`nvs_flash_init` dans un `ESP_ERROR_CHECK`), `esp_netif_init`, la boucle d'événements par défaut, puis appelle `example_connect()` (une fonction d'aide des exemples qui connecte le Wi-Fi **ou** l'Ethernet, selon la configuration) avant `mqtt_app_start()`. Celle-ci ne renseigne qu'**une** chose, `.broker.address.uri = CONFIG_BROKER_URL`, crée le client, enregistre **un** gestionnaire pour tous les événements et démarre. Il n'y a dans cet exemple ni testament, ni statut, ni JSON : ce sont les ajouts de ce TP. Le gestionnaire de l'exemple, lui, publie et s'abonne dans la réaction à `MQTT_EVENT_CONNECTED` : c'est le bon emplacement, nous le reprenons.

Deux appels sont **interdits dans un gestionnaire** d'événements MQTT : `esp_mqtt_client_stop` et `esp_mqtt_client_destroy` (la documentation le dit : on ne peut pas arrêter le client depuis sa propre tâche).

## Les événements MQTT : qui les appelle, dans quelle tâche

Le client prévient votre programme par des **événements**, comme le Wi-Fi au TP 7. Le gestionnaire a la même signature :

```cpp
static void gestionnaire_mqtt(void *arg, esp_event_base_t base, int32_t id, void *data) {
    esp_mqtt_event_handle_t ev = (esp_mqtt_event_handle_t)data;   // la description de l'événement
    switch ((esp_mqtt_event_id_t)id) {
    case MQTT_EVENT_CONNECTED:  /* connecté au courtier */ break;
    case MQTT_EVENT_DATA:       /* un message est arrivé */ break;
    default: break;
    }
}
```

| Événement | Quand | Ce qu'il y a dedans |
|---|---|---|
| `MQTT_EVENT_BEFORE_CONNECT` | juste avant chaque tentative de connexion | rien d'utile |
| `MQTT_EVENT_CONNECTED` | connecté au courtier : on peut publier et s'abonner | `session_present` |
| `MQTT_EVENT_DISCONNECTED` | la connexion est perdue | rien d'utile |
| `MQTT_EVENT_ERROR` | une erreur, par exemple une tentative de connexion qui échoue (réseau, courtier absent...) | `ev->error_handle->error_type` |
| `MQTT_EVENT_SUBSCRIBED` | le courtier a accepté un abonnement | `msg_id` |
| `MQTT_EVENT_PUBLISHED` | un message de QoS 1 ou 2 a été acquitté (jamais pour le QoS 0) | `msg_id` |
| `MQTT_EVENT_DATA` | un message arrive sur un sujet auquel vous êtes abonné | `topic`, `topic_len`, `data`, `data_len`... |

**Dans quelle tâche ?** Le gestionnaire est appelé depuis la tâche **`mqtt_task`** du client (le code du composant poste l'événement dans une boucle d'événements **sans tâche propre** et la fait tourner dans sa propre tâche). Conséquences :

- Ce n'est **pas** `app_main` ni `sys_evt` : votre gestionnaire MQTT et votre boucle de télémétrie sont dans **deux tâches différentes** qui partagent des variables (ici l'état du relais). Un booléen partagé se déclare `std::atomic<bool>` : c'est ce que fait `main.cpp`.
- Comme au TP 7, le gestionnaire **ne doit jamais bloquer** : tant qu'il travaille, la tâche `mqtt_task` ne lit plus le réseau. Pas de `vTaskDelay` de plusieurs secondes là-dedans.
- On peut publier et s'abonner depuis le gestionnaire : l'exemple officiel le fait, et la documentation le permet pour l'abonnement.

## Publier : la fonction, le QoS et le drapeau retain

```cpp
int id = esp_mqtt_client_publish(client, "home/devices/pool-ctl/telemetry", json, 0, 0, 0);
//                                client,  sujet,                           charge, len, qos, retain
```

- `len` : la longueur de la charge utile. **0 veut dire « calcule avec strlen »** : pratique pour un texte, à éviter pour des octets quelconques.
- La fonction renvoie l'**identifiant du message** (toujours 0 en QoS 0), **-1** en cas d'échec, **-2** si la file d'attente sortante est pleine. **Vérifiez le résultat.** En particulier, un message de **QoS 0 publié pendant que le client est déconnecté est refusé (-1)** : il n'est pas mis en file d'attente, il est perdu.
- La documentation prévient que l'appel **peut bloquer plusieurs secondes** (délai réseau de 10 s, ou fragmentation d'un gros message). Raison de plus pour ne pas publier à toute vitesse.

**Le QoS** (*Quality of Service*) dit quelle garantie de livraison on demande :

| QoS | Garantie | Coût | Simulateur |
|---|---|---|---|
| 0 | **au plus une fois** : envoyé, sans accusé de réception ; peut se perdre | le plus léger | géré |
| 1 | **au moins une fois** : le courtier accuse réception ; peut arriver en double | un aller-retour | géré (l'échange est réduit à un événement `MQTT_EVENT_PUBLISHED`) |
| 2 | **exactement une fois** : quatre messages d'échange | le plus lourd | accepté, traité comme le QoS 1 |

Règle pratique : une **mesure périodique** se publie en **QoS 0** (la suivante arrive dans 10 s, la rejouer en retard n'aurait aucun intérêt) ; un **état** ou un **ordre** qui ne doit pas se perdre se publie en QoS 1. Un message de QoS 1 ou 2 publié pendant une coupure est mis en file d'attente et envoyé après la reconnexion.

Le drapeau **`retain`** (retenu) demande au courtier de **garder le dernier message** de ce sujet et de le **renvoyer immédiatement à tout nouvel abonné**. Sans lui, un client qui s'abonne à `.../status` ne sait rien tant que la carte n'a pas republié. Avec lui, il reçoit l'état courant dès son abonnement. On ne retient pas une mesure (un abonné tardif recevrait une valeur vieille de plusieurs minutes comme si elle était actuelle), on retient un **état**.

## S'abonner, et se réabonner après une coupure

```cpp
int id = esp_mqtt_client_subscribe_single(client, "home/devices/pool-ctl/command", 1);
//                                         client,  filtre,                          QoS maximal
```

En C, `esp_mqtt_client_subscribe` est une macro qui choisit avec `_Generic` entre l'abonnement à un sujet et l'abonnement à plusieurs (c'est ce que fait l'exemple officiel, écrit en C). En C++, l'en-tête la définit simplement comme un alias de `esp_mqtt_client_subscribe_single`. Le TP appelle directement `esp_mqtt_client_subscribe_single`.

- **Le client doit être connecté** : la documentation le dit, et la fonction renvoie -1 sinon. On s'abonne donc **dans la réaction à `MQTT_EVENT_CONNECTED`**, jamais juste après `esp_mqtt_client_start` (la connexion n'est pas encore faite : l'abonnement serait perdu sans bruit).
- **À chaque connexion, pas une seule fois.** La session est propre : quand la connexion tombe puis revient, le courtier a **tout oublié**. Un programme qui s'abonne une seule fois fonctionne jusqu'à la première coupure du courtier, puis devient sourd aux commandes **sans aucune erreur**. Le scénario c du TP provoque exactement cette coupure.
- Le **QoS de l'abonnement** est un maximum : le message est livré avec le plus petit des deux QoS (celui de la publication et celui de l'abonnement).

## Le statut et le testament

Comment l'application sait-elle que la carte est **en ligne** ? Un message `online` sur `.../status`, publié à chaque connexion. Mais si la carte perd le courant, elle ne peut plus rien dire : `online` resterait affiché pour toujours. Le **testament** (*last will*) résout cela : la carte donne au courtier, **au moment de se connecter**, un message à publier **à sa place** si elle disparaît sans se déconnecter proprement (courant coupé, Wi-Fi perdu : la documentation parle de déconnexion « ungraceful »). Le courtier détecte la disparition grâce au délai de *keep-alive* (réglage `session.keepalive`).

Les champs : `topic`, `msg`, `qos`, `retain` (et `msg_len`, nécessaire seulement si `msg` n'est pas un texte terminé par un NUL ; avec un texte entre guillemets, laissez 0).

**Pourquoi `online` retenu ET testament `offline` retenu ?** Regardons les quatre combinaisons du point de vue d'une application qui s'abonne à `.../status` **plus tard**, la carte étant en ligne ou ayant disparu :

| `online` | testament | Abonné tardif, carte en ligne | Abonné tardif, carte disparue |
|---|---|---|---|
| retenu | retenu | `online` | `offline` : **correct dans les deux cas** |
| non retenu | retenu | rien : l'état est inconnu | `offline` |
| retenu | non retenu | `online` | `online` **à tort, pour toujours** |
| non retenu | non retenu | rien | rien |

Les deux sont donc retenus : le sujet `.../status` contient toujours **le dernier état connu**, qu'il vienne de la carte (`online`) ou du courtier (`offline`). À chaque (re)connexion, la carte republie `online`, ce qui remplace un `offline` laissé par le testament.

Le testament est une promesse faite au courtier **à la connexion** : il se règle donc dans la configuration, **avant** `esp_mqtt_client_init`.

## Construire un JSON valide sans bibliothèque

Le format de la télémétrie est du **JSON** : `{"level": 72.5, "relay": false}`. Un JSON est valide ou non, il n'y a pas de « presque » : l'application qui le lit le rejette entièrement. Les règles dont vous avez besoin :

- un objet s'écrit entre `{` et `}`, les paires `"clé": valeur` séparées par des virgules, **sans virgule finale** ;
- les **clés** sont entre **guillemets doubles** : `{level: 72.5}` est invalide ;
- `true` et `false` s'écrivent **en minuscules et sans guillemets** : `"false"` est un texte, pas un booléen ;
- un nombre s'écrit avec un **point** décimal ; `nan` et `inf` ne sont pas des nombres JSON ;
- les espaces entre les éléments sont **libres** : `{"relay":true}` et `{"relay": true}` disent la même chose.

Pour **construire** un si petit JSON, inutile d'une bibliothèque : un `snprintf` suffit.

```cpp
char json[64];
snprintf(json, sizeof(json), "{\"level\": %.1f, \"relay\": %s}", niveau, relais ? "true" : "false");
```

- Les guillemets du JSON s'écrivent `\"` dans une chaîne C.
- `%.1f` écrit le niveau avec **une** décimale (72.5). Dans l'environnement par défaut d'ESP-IDF, le séparateur est bien le point.
- `relais ? "true" : "false"` fabrique le mot : jamais de `%d` pour un booléen, qui écrirait 0 ou 1 (invalide ici : le contrôle exige `true` ou `false`).
- `snprintf` n'écrit jamais plus que la taille donnée. Prévoyez un tampon assez grand : ce message fait 30 caractères, 64 octets suffisent.

**cJSON.** ESP-IDF 5.5.3 contient le composant `json` (la bibliothèque cJSON, en-tête `cJSON.h`, à déclarer dans les dépendances du composant), qui construit et analyse des JSON de toute taille. Le **simulateur ne la fournit pas** : le TP utilise `snprintf` pour écrire et une recherche de texte pour lire. Sur une vraie carte et pour des messages plus riches, préférez cJSON.

**Les valeurs doivent être vraies.** Le niveau est **lu sur le capteur à chaque message** (la fonction `lire_niveau()` du TP applique l'étalonnage du TP 4 : brut 620 = 0 %, 3723 = 100 %), et `relay` est l'état **réel** du relais à cet instant. Une valeur écrite en dur passerait un seul scénario : le contrôle en fait tourner trois.

## Recevoir une commande : topic et data ne sont pas des chaînes C

Un message reçu arrive dans `MQTT_EVENT_DATA`. L'événement (`esp_mqtt_event_handle_t ev`) contient :

| Champ | Sens |
|---|---|
| `ev->topic`, `ev->topic_len` | le sujet du message, et sa longueur |
| `ev->data`, `ev->data_len` | la charge utile, et sa longueur |
| `ev->total_data_len`, `ev->current_data_offset` | taille totale du message, et position de ce morceau dans le message (messages fragmentés) |
| `ev->retain`, `ev->qos` | les drapeaux du message reçu |

**Piège central : `topic` et `data` ne se terminent PAS par un NUL.** Ce sont des **morceaux** du tampon de réception : le sujet, puis tout de suite la charge utile, sans caractère de fin. L'exemple officiel le sait : il affiche avec `printf("TOPIC=%.*s\r\n", event->topic_len, event->topic)` et `printf("DATA=%.*s\r\n", event->data_len, event->data)`, c'est-à-dire en donnant la **longueur** à afficher. Le simulateur reproduit ce comportement.

- `strcmp(ev->topic, "home/devices/pool-ctl/command")` **échoue en pratique** : `strcmp` ne s'arrête qu'au NUL, et lit donc la charge utile à la suite du sujet. Le sujet reçu ne ressemble pas à celui que vous attendez, et la commande n'est pas exécutée.
- `printf("%s", ev->data)` ou `ESP_LOGI(TAG, "%s", ev->data)` affiche aussi ce qui traîne derrière le message (un `~` de plus dans le simulateur, des octets quelconques sur une vraie carte). Écrivez `"%.*s", ev->data_len, ev->data`.
- Les règles : **comparer le sujet** avec `topic_len` : `ev->topic_len == (int)strlen(attendu) && strncmp(ev->topic, attendu, ev->topic_len) == 0` ; **copier la charge utile** dans un tampon à vous, à la taille `data_len`, puis y mettre un NUL.

```cpp
char msg[64];
int n = len < (int)sizeof(msg) - 1 ? len : (int)sizeof(msg) - 1;   // jamais plus que le tampon
memcpy(msg, data, n);
msg[n] = '\0';                                                      // maintenant c'est une chaîne C
```

**Messages fragmentés.** Quand un message est plus gros que le tampon interne du client, la documentation indique que **plusieurs** événements `MQTT_EVENT_DATA` sont postés, avec `current_data_offset` et `total_data_len` pour recoller les morceaux, et que **seul le premier** porte le sujet. Un message de la taille d'une commande (une trentaine d'octets) tient en un seul événement : le TP ne fragmente jamais (le simulateur non plus) et vous n'avez pas à recoller quoi que ce soit. Gardez en tête qu'un gestionnaire qui compare le sujet de chaque événement ignorera naturellement les morceaux suivants d'un gros message, dont le sujet est vide.

**Lire la commande.** Le JSON est reçu en texte : chercher `"relay"` (avec ses guillemets), avancer après, sauter les espaces et le `:`, puis regarder si on lit `true` ou `false`. Comme les espaces sont libres, le contrôle envoie `{"relay": true}` **et** `{"relay":false}` : une recherche de la chaîne exacte `"relay": true` échouerait sur la seconde. **Tout ce qui n'est pas une commande** (un texte quelconque, une clé inconnue, une valeur ni `true` ni `false`) est **ignoré** : le relais ne change pas, rien ne plante.

```cpp
const char *p = strstr(msg, "\"relay\"");   // NULL : ce n'est pas une commande
p += strlen("\"relay\"");
while (*p == ' ' || *p == ':') p++;          // saute espaces et deux-points
bool voulu = (strncmp(p, "true", 4) == 0);   // et "false" ? voir le TP
```

## Exécuter la commande sans dépasser la limite de sécurité

Au TP 6, la pompe s'arrêtait **au-dessus de 80 %** : c'est la **limite de sécurité** de la piscine. Une commande à distance ne doit **jamais** contourner cette règle : si le niveau dépasse 80 %, allumer le relais ferait déborder la piscine, qui que soit celui qui le demande.

La règle du TP, sans ambiguïté :

- une commande `{"relay": true}` est **refusée** si le niveau, **lu sur le capteur à cet instant** (pas la dernière valeur de la télémétrie, qui date de 10 s), est **strictement supérieur à 80 %** ; le relais **ne change pas** ;
- une commande `{"relay": false}` est **toujours acceptée** : éteindre est toujours sûr ;
- une commande refusée se **journalise** avec **exactement** : `ESP_LOGW(TAG, "command refused: level=%d%%", (int)niveau);` avec le tag `mqtt`. Pour un niveau de 85,3 %, la ligne est `command refused: level=85%`. (Le `%%` est la façon d'écrire un `%` dans un format `printf`.) Une seule ligne par commande refusée ;
- si la **lecture du capteur échoue**, `lire_niveau()` renvoie 100 : sans mesure, on suppose le pire, et on refuse (c'est l'état sûr du TP 6).

Dans les exécutions du contrôle, le niveau est **constant** : il ne peut donc pas distinguer une lecture faite à l'instant de la commande d'une valeur gardée en mémoire. Sur une vraie piscine, seule la lecture fraîche est sûre : faites-la quand même.

Pourquoi un journal de refus ? Parce qu'un ordre ignoré en silence est un mystère : l'utilisateur appuie sur « allumer » et rien ne se passe. Le journal dit pourquoi.

## La télémétrie toutes les 10 secondes

La boucle de `app_main` publie, puis attend 10 secondes avec `vTaskDelay(pdMS_TO_TICKS(PERIODE_MS))`. Quelques points :

- **Le premier message** est publié avant que le client soit connecté (la connexion prend un instant) : `esp_mqtt_client_publish` renvoie -1, le message est perdu, c'est normal pour une mesure en QoS 0. Le programme le note (un `ESP_LOGI`) et continue ; la mesure suivante arrive 10 s plus tard.
- Pendant une coupure du courtier, les messages de QoS 0 sont refusés de la même façon : la télémétrie **reprend** d'elle-même après la reconnexion, sans rien faire de plus. Un programme qui s'arrête de publier après la première erreur est faux.
- La période est de **10 secondes** : une période de 1 s inonde le courtier, de 1 min rend la télémétrie inutile. Le contrôle accepte de **9 s à 11 s** entre deux messages.

Le simulateur ne fournit ni minuteur logiciel FreeRTOS ni `vTaskDelayUntil` (qui existe sur la vraie carte) : on écrit la boucle périodique avec `vTaskDelay` dans `app_main` ou dans une tâche créée avec `xTaskCreate`.

## Un exemple pas à pas : une serre avec un ventilateur

Une carte de serre publie `greenhouse/temp` et reçoit `greenhouse/fan` avec `{"on": true}`. Elle refuse d'éteindre le ventilateur au-dessus de 35 °C. Déroulé, avec un courtier qui tombe :

1. `esp_mqtt_client_start` : le client crée `mqtt_task` et tente de se connecter (`BEFORE_CONNECT`).
2. `CONNECTED` : le gestionnaire publie `online` (retenu) et s'abonne à `greenhouse/fan`.
3. Chaque 10 s : `snprintf` du JSON, `esp_mqtt_client_publish` en QoS 0.
4. Un message arrive sur `greenhouse/fan` : `DATA`. Le gestionnaire compare le sujet **avec sa longueur**, copie la charge utile dans `msg[64]`, cherche `"on"`. Si la température dépasse 35 °C et que la commande est « éteindre » : **refus** journalisé. Sinon : on exécute.
5. Le courtier tombe : `DISCONNECTED`. Les publications QoS 0 renvoient -1, elles sont perdues.
6. 10 s plus tard le client retente (`BEFORE_CONNECT`) ; le courtier est de retour : `CONNECTED` **de nouveau**. Le gestionnaire republie `online` et **se réabonne** : sans cela, plus aucune commande n'arriverait.

## Ce que le simulateur simplifie

- Il y a **un seul courtier**, sans authentification ni TLS (`mqtts://` n'est pas géré), et **pas de keep-alive** : le courtier ne détecte pas qu'une carte a disparu.
- **Le testament n'est jamais envoyé** : le simulateur ne fait pas disparaître la carte. Il **note** dans sa trace le testament que vous avez configuré (sujet, message, QoS, `retain`), et le contrôle le lit.
- **Le courtier ne garde aucun message retenu** : un message publié avec `retain` est simplement noté dans la trace (le contrôle lit le drapeau). Aucun abonné tardif ne reçoit le dernier message.
- **Pas de messages fragmentés** : `MQTT_EVENT_DATA` arrive toujours en un seul morceau (`data_len` égal à `total_data_len`, `current_data_offset` à 0). Le simulateur reproduit en revanche l'absence de NUL après `topic` et `data`.
- **Un `%s` sur `data` ne fait pas échouer le TP** : dans le simulateur, un `~` puis un NUL suivent la charge utile, ce qui permet à une recherche de texte de réussir par chance. Le contrôle ne peut pas le détecter, mais sur une vraie carte c'est une lecture hors des limites : copiez toujours `data_len` octets.
- Les échanges QoS 1 et 2 sont **réduits** à un événement `MQTT_EVENT_PUBLISHED`.
- Le client se connecte 0,1 s après `esp_mqtt_client_start` (ou erreur si le courtier est absent) ; après une coupure ou une erreur, la tentative suivante vient 10 s plus tard.
- **Le Wi-Fi** : une fois `esp_wifi_init` appelé, la connexion MQTT attend l'adresse IP.
- **Les tâches** : le Wi-Fi, la boucle d'événements et le client MQTT créent leurs propres tâches, qui comptent dans la limite de tâches du simulateur (4 tâches à vous au plus). Le TP n'en crée aucune.
- Le temps est virtuel et n'avance que pendant les attentes.
- La bibliothèque cJSON n'est pas fournie.
- Le simulateur exige `nvs_commit` pour qu'une écriture NVS persiste (plus strict que la vraie carte) ; ce TP n'écrit rien dans la NVS.

## Le programme du TP en un coup d'œil

```text
app_main :
  init_relais(), init_adc()                     (fournis)
  wifi_connecter()                              (fourni : Wi-Fi minimal du TP 7, bloque jusqu'à l'IP)
  demarrer_mqtt()                               (étape 5)
  boucle : publier_telemetrie(), puis vTaskDelay(10 s)   (étapes 2 et 6)

gestionnaire_mqtt (tâche mqtt_task, ne bloque jamais) :   (étape 4)
  CONNECTED : publier "online" (QoS 1, retenu) sur .../status, s'abonner à .../command
  DATA      : si le sujet (avec topic_len) est .../command : traiter_commande(data, data_len)

traiter_commande(data, len) :                   (étape 3)
  copier data dans msg[64] avec un NUL ; chercher "relay" puis true ou false ; sinon ignorer
  "true" et niveau > 80 : ESP_LOGW "command refused: level=%d%%" et ne rien changer
  sinon regler_relais(voulu)

construire_json(...) :                          (étape 1)
  snprintf "{\"level\": %.1f, \"relay\": %s}"
```

Le contrôle fait tourner le programme **trois fois**, en temps virtuel. Le niveau du réservoir est constant dans chaque exécution (il ne monte ni ne baisse, que le relais soit allumé ou non) :

- **a, niveau 72,5 %** (120 s) : une commande `{"relay": true}` à 30 s doit allumer le relais (dans la seconde) ; un message `salut` à 50 s n'est pas une commande : le relais ne bouge pas ; `{"relay":false}` à 70 s (sans espace) doit l'éteindre. La télémétrie est publiée toutes les 10 s, de 9 s à 11 s entre deux messages ;
- **b, niveau 85,3 %** (60 s) : `{"relay": true}` à 30 s doit être refusée : le relais n'est jamais allumé et la ligne `command refused: level=85%` (ESP_LOGW, tag `mqtt`) apparaît une fois, dans la seconde qui suit la commande ;
- **c, niveau 72,5 %, coupure du courtier** (140 s) : `{"relay": true}` à 25 s ; le courtier est coupé de 50 s à 75 s, le client se reconnecte tout seul ; `{"relay": false}` à 95 s n'est reçue que si vous vous êtes **réabonné** à la reconnexion.

Ce que le contrôle vérifie, dans chaque exécution : la **télémétrie** sur exactement `home/devices/pool-ctl/telemetry` ; chaque message est un **JSON valide** avec **exactement** les clés `level` (un nombre, à 1 point près du niveau lu sur le capteur) et `relay` (`true` ou `false` sans guillemets, égal à l'état réel de la broche 5 à cet instant) ; à **chaque connexion** (la reconnexion de c comprise), dans les 5 s qui suivent : le texte exact `online` publié sur `home/devices/pool-ctl/status` **avec le drapeau retain**, et un abonnement à `home/devices/pool-ctl/command` (le filtre exact, ou un filtre avec jokers qui le couvre) ; le **testament** de chaque connexion : sujet `home/devices/pool-ctl/status`, message `offline`, drapeau retain ; la broche 5 configurée en sortie et au moins une lecture du canal 6 de l'ADC ; aucun redémarrage de la carte ; la reconnexion automatique du client (n'appelez pas `esp_mqtt_client_stop` et ne la désactivez pas) ; après la reconnexion de c, la télémétrie reprend, avec au plus 11 s entre deux messages ; le relais ne change **que** sur les commandes valides.

## Pièges

!!Les champs topic et data d'un événement MQTT_EVENT_DATA ne sont pas terminés par un NUL : comparez avec topic_len et strncmp, copiez data_len octets dans un tampon à vous, et n'utilisez jamais strcmp ni %s sur eux!!

!!La session est propre : le courtier oublie vos abonnements à chaque connexion, abonnez-vous dans la réaction à MQTT_EVENT_CONNECTED, pas une fois pour toutes!!

!!Une commande ne contourne jamais la limite de sécurité : le niveau se lit au moment de la commande, au-dessus de 80 % on refuse d'allumer, on journalise le refus, et éteindre reste toujours permis!!

!!Le statut online et le testament offline doivent tous les deux porter le drapeau retain, sinon un abonné qui arrive après la panne ne voit pas l'état réel!!

!!Un JSON écrit à la main se vérifie : clés entre guillemets doubles, true et false sans guillemets, pas de virgule finale, un nombre fini!!

!!Ne bloquez pas le gestionnaire MQTT et n'appelez jamais esp_mqtt_client_stop ni esp_mqtt_client_destroy depuis lui!!

## À retenir

- **MQTT** : un **courtier**, des **sujets** (avec `/`, jokers `+` et `#` seulement pour s'abonner), **publier** et **s'abonner**.
- Le client ESP-IDF : `esp_mqtt_client_config_t`, `esp_mqtt_client_init`, `esp_mqtt_client_register_event`, `esp_mqtt_client_start`. Reconnexion **automatique** toutes les 10 s par défaut ; session **propre** par défaut.
- Le gestionnaire s'exécute dans la tâche **`mqtt_task`** et ne bloque jamais.
- `esp_mqtt_client_publish(client, sujet, charge, len, qos, retain)` : **-1** si refusé (QoS 0 hors connexion). **QoS 0** au plus une fois, **QoS 1** au moins une fois, **QoS 2** exactement une fois. **retain** : le courtier garde le dernier message et le donne aux nouveaux abonnés.
- **S'abonner** (`esp_mqtt_client_subscribe_single`) dans `MQTT_EVENT_CONNECTED`, **à chaque connexion**.
- **Statut et testament** : `online` retenu à la connexion, testament `offline` retenu : le sujet contient toujours le dernier état connu.
- Un **JSON** se construit avec `snprintf` pour un petit message (cJSON existe dans ESP-IDF 5.5.3, pas dans le simulateur) : clés entre guillemets, `true`/`false` en minuscules.
- `topic` et `data` : **pas de NUL**. Toujours `topic_len` et `data_len`.
- Une commande ne dépasse **jamais** la limite de sécurité (80 %) : refus journalisé `command refused: level=85%`.
