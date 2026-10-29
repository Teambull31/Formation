# Se connecter au Wi-Fi : NVS, événements et reconnexion avec attente croissante

**Le problème concret :** votre objet connecté doit se brancher tout seul sur la box de la maison. La box peut être éteinte, le signal faible, le réseau absent pendant une minute. Un programme fragile abandonne au premier échec. Un programme **trop** têtu rappelle la box en boucle serrée, dix fois par seconde, et ne laisse plus la place à rien d'autre. Il faut un juste milieu : **réessayer en attendant de plus en plus longtemps, et savoir abandonner proprement.**

Cette leçon contient toute la théorie du TP. Lisez-la dans l'ordre : les messages du contrôle vous disent quelle section relire. Elle suppose les leçons précédentes : les tâches FreeRTOS et `vTaskDelay` (TP 3), les journaux `ESP_LOGx`, et l'idée d'**état** d'un programme (TP 6).

Tout ce qui est écrit ici est le vrai ESP-IDF : le code est celui de l'exemple officiel `examples/wifi/getting_started/station` (version 5.5.3), que vous pourrez recopier dans un vrai projet. Le TP tourne dans le simulateur, qui joue le rôle de la puce Wi-Fi et de la box.

## La vue d'ensemble : les étapes d'une connexion

Une carte ESP32 qui rejoint un réseau se comporte comme une **station** (le mot officiel est *station*, abrégé STA : un appareil qui se connecte à un point d'accès, ici votre box). Voici toutes les étapes, dans l'ordre. Le TP les suit une par une.

1. **Initialiser la NVS** (le petit espace de stockage de la carte).
2. **Initialiser la pile réseau** : `esp_netif_init()`.
3. **Créer la boucle d'événements par défaut** : `esp_event_loop_create_default()`.
4. **Créer l'interface réseau de la station** : `esp_netif_create_default_wifi_sta()`.
5. **Initialiser le pilote Wi-Fi** : `esp_wifi_init(&cfg)`.
6. **Enregistrer les gestionnaires d'événements** (avant de démarrer le Wi-Fi).
7. **Régler le mode et le réseau** : `esp_wifi_set_mode`, `esp_wifi_set_config`.
8. **Démarrer** : `esp_wifi_start()`.
9. **Réagir aux événements** : connexion, échec, adresse IP obtenue.

Chaque fonction renvoie un `esp_err_t` (`ESP_OK` si tout va bien). On les entoure de `ESP_ERROR_CHECK(...)` : si l'appel échoue, le programme s'arrête avec un message qui nomme l'erreur, plutôt que de continuer avec un Wi-Fi à moitié prêt.

## La NVS d'abord : le motif d'initialisation

La **NVS** (*non-volatile storage*) est un petit espace de stockage qui garde ses données quand la carte est éteinte. Le pilote Wi-Fi s'en sert : la documentation précise que, quand le Wi-Fi est configuré pour cela (c'est le cas par défaut, avec `WIFI_INIT_CONFIG_DEFAULT()`), **toute configuration réglée avec les fonctions Wi-Fi est enregistrée en mémoire flash**, et que le pilote repart avec cette configuration au démarrage suivant. Les exemples officiels initialisent donc la NVS **avant** tout le reste.

Le motif est toujours le même, on le recopie tel quel :

```cpp
esp_err_t ret = nvs_flash_init();
if (ret == ESP_ERR_NVS_NO_FREE_PAGES || ret == ESP_ERR_NVS_NEW_VERSION_FOUND) {
    ESP_ERROR_CHECK(nvs_flash_erase());
    ret = nvs_flash_init();
}
ESP_ERROR_CHECK(ret);
```

Pourquoi ce « si » ? Deux cas peuvent faire échouer la première initialisation, et dans les deux on ne peut qu'**effacer** la NVS puis recommencer :

- `ESP_ERR_NVS_NO_FREE_PAGES` : la NVS n'a plus de page libre (la documentation cite le cas d'une partition tronquée) ;
- `ESP_ERR_NVS_NEW_VERSION_FOUND` : la NVS contient des données dans un format plus récent que celui que ce programme sait lire (par exemple après avoir flashé une version plus ancienne du programme).

Tout autre code d'erreur est un vrai problème : `ESP_ERROR_CHECK(ret)` l'attrape. **Effacer ne se fait donc que dans ces deux cas**, jamais « au cas où » : un effacement systématique détruirait à chaque démarrage ce que la NVS doit garder.

Le contrôle du TP exige que votre `main.cpp` contienne ce motif complet : les deux noms d'erreur et l'appel à `nvs_flash_erase`. Le simulateur applique aussi la règle : tant que `nvs_flash_init()` n'a pas réussi, `esp_wifi_init` renvoie `ESP_ERR_NVS_NOT_INITIALIZED`.

!!Sans NVS initialisée, le Wi-Fi ne démarre pas : appelez nvs_flash_init (avec son motif d'effacement) avant tout autre appel Wi-Fi!!

## La pile réseau : esp_netif et la boucle d'événements par défaut

Deux briques doivent exister avant le pilote Wi-Fi :

- **`esp_netif_init()`** initialise la pile TCP/IP. La documentation demande de l'appeler **une seule fois**, au démarrage de l'application.
- **`esp_event_loop_create_default()`** crée la **boucle d'événements par défaut** : c'est par elle que le système distribue les événements (Wi-Fi, adresse IP). Elle renvoie `ESP_ERR_INVALID_STATE` si elle existe déjà.

Puis **`esp_netif_create_default_wifi_sta()`** crée l'interface réseau de la station et la branche sur le Wi-Fi. La documentation précise que la boucle d'événements par défaut doit avoir été créée **avant**, et que cette fonction **s'arrête avec un `abort`** en cas d'erreur (elle n'a pas de code de retour d'erreur : elle renvoie un pointeur sur l'interface). Sans cette interface, la station peut se connecter à la box, mais personne ne demande d'adresse IP : l'événement « adresse obtenue » n'arrive jamais.

Ordre à respecter : `esp_netif_init`, puis `esp_event_loop_create_default`, puis `esp_netif_create_default_wifi_sta`, puis `esp_wifi_init`.

## Initialiser et démarrer le Wi-Fi en mode station

```cpp
wifi_init_config_t cfg = WIFI_INIT_CONFIG_DEFAULT();
ESP_ERROR_CHECK(esp_wifi_init(&cfg));
```

`esp_wifi_init` doit être appelée avant toute autre fonction Wi-Fi, et la documentation demande de **toujours** utiliser la macro `WIFI_INIT_CONFIG_DEFAULT()` pour remplir la configuration (elle fixe des dizaines de réglages du pilote que vous n'avez pas à connaître).

Ensuite, on choisit le mode station et on indique le réseau :

```cpp
wifi_config_t conf = {};
strncpy((char *)conf.sta.ssid, CONFIG_ESP_WIFI_SSID, sizeof(conf.sta.ssid) - 1);
strncpy((char *)conf.sta.password, CONFIG_ESP_WIFI_PASSWORD, sizeof(conf.sta.password) - 1);
ESP_ERROR_CHECK(esp_wifi_set_mode(WIFI_MODE_STA));
ESP_ERROR_CHECK(esp_wifi_set_config(WIFI_IF_STA, &conf));
ESP_ERROR_CHECK(esp_wifi_start());
```

`wifi_config_t conf = {};` met tout à zéro : les champs `ssid` et `password` sont des **tableaux d'octets** de 32 et 64 cases (pas des `const char *`), on y **copie** le texte avec `strncpy`, en laissant toujours une case libre pour le zéro final. `esp_wifi_start()` démarre la station et fait arriver le premier événement, `WIFI_EVENT_STA_START`.

## Le mot de passe ne s'écrit jamais dans le code

Un mot de passe écrit dans un fichier source finit dans le dépôt Git, dans une capture d'écran, dans un message d'aide envoyé à un collègue. L'exemple officiel ne l'écrit pas dans le code : il lit **`CONFIG_ESP_WIFI_SSID`** et **`CONFIG_ESP_WIFI_PASSWORD`**, deux valeurs de la configuration du projet (le menu `idf.py menuconfig`, alimenté par le fichier `Kconfig.projbuild` du projet). Le compilateur les transforme en macros qui valent des chaînes de caractères, disponibles dans `sdkconfig.h`.

Dans ce TP, le simulateur fournit ces deux macros dans `sdkconfig.h` avec des **valeurs d'exemple** (`reseau-exemple` et `exemple-motdepasse`) : ce n'est pas un vrai réseau. Votre programme les utilise comme dans la section précédente, et ne contient **aucun** mot de passe.

Le contrôle fait respecter cette règle par une **analyse statique** (une lecture du texte de `main.cpp` avant même de l'exécuter). Elle refuse :

- toute instruction qui parle d'un mot de passe (un nom contenant `pass`, `pwd`, `mdp`, `secret` ou `psk`) **et** contient un texte entre guillemets (par exemple `strcpy(conf.sta.password, "abcdefgh")`), ainsi que toute ligne `#define` dans le même cas ;
- le mot de passe d'exemple lui-même, écrit n'importe où dans le code (hors commentaires) ;
- un programme qui n'utilise pas `CONFIG_ESP_WIFI_PASSWORD`.

Elle ne peut pas deviner un secret caché autrement : c'est une garde contre l'accident, pas une preuve. Sur une vraie carte, prenez l'habitude de ne jamais écrire un secret en dur.

!!Un mot de passe écrit en dur dans le code est refusé par le contrôle, et dans un vrai projet il finit tôt ou tard dans le dépôt : lisez-le toujours dans la configuration du projet!!

## Les événements Wi-Fi : qui appelle quoi, et dans quelle tâche

Le pilote Wi-Fi ne vous « rappelle » pas à la fin de chaque opération : il **poste des événements** dans la boucle d'événements par défaut. Un événement est identifié par deux nombres : une **famille** (`WIFI_EVENT` pour le Wi-Fi, `IP_EVENT` pour le réseau) et un **identifiant** (`WIFI_EVENT_STA_START`, `WIFI_EVENT_STA_CONNECTED`, `WIFI_EVENT_STA_DISCONNECTED`, `IP_EVENT_STA_GOT_IP`...).

Vous enregistrez une fonction, un **gestionnaire**, pour ceux qui vous intéressent :

```cpp
static void gestionnaire(void *arg, esp_event_base_t base, int32_t id, void *data) { /* ... */ }

esp_event_handler_instance_t inst_wifi, inst_ip;
ESP_ERROR_CHECK(esp_event_handler_instance_register(WIFI_EVENT, ESP_EVENT_ANY_ID, &gestionnaire, NULL, &inst_wifi));
ESP_ERROR_CHECK(esp_event_handler_instance_register(IP_EVENT, IP_EVENT_STA_GOT_IP, &gestionnaire, NULL, &inst_ip));
```

La première ligne dit « tous les événements `WIFI_EVENT` », la seconde « seulement `IP_EVENT_STA_GOT_IP` ». Les deux appels utilisent le **même** gestionnaire, qui distingue les cas avec `base` et `id`. L'argument `NULL` est une donnée que vous retrouverez dans `arg` ; `inst_wifi` et `inst_ip` servent à désenregistrer plus tard (on n'en a pas besoin ici). **Enregistrez les gestionnaires avant `esp_wifi_start()`** : sinon le tout premier événement, `WIFI_EVENT_STA_START`, arrive quand personne n'écoute, et il est perdu.

Qui exécute le gestionnaire ? **Pas votre tâche** : la boucle d'événements par défaut a sa propre tâche, nommée `sys_evt`. Les événements y sont mis en **file d'attente** (32 places par défaut) et le gestionnaire les traite **un par un, dans l'ordre**. La documentation décrit cette boucle comme un moyen de « sérialiser et différer » l'exécution du code dans un autre contexte. Deux conséquences :

1. **Un gestionnaire ne doit jamais bloquer** (pas de `vTaskDelay` long, pas d'attente d'une file) : pendant qu'il dort, la tâche `sys_evt` ne traite plus aucun événement du système, ni les vôtres. Si la file de 32 places se remplit, de nouveaux événements sont perdus.
2. Un gestionnaire qui doit **attendre** ou **décider lentement** ne le fait pas lui-même : il **note** ce qui s'est passé et **réveille une autre tâche**, par exemple avec un **groupe d'événements**.

Le contrôle ne peut pas voir ce que fait votre gestionnaire à l'intérieur, et la règle n°1 n'est donc pas vérifiée par lui. Elle reste vraie sur une vraie carte : respectez-la.

Les événements utiles pour ce TP :

- **`WIFI_EVENT_STA_START`** : la station est démarrée. La documentation recommande d'appeler `esp_wifi_connect()` à ce moment. **Une seule tentative** de connexion est lancée par appel, et `esp_wifi_connect` rend la main tout de suite : le résultat arrive plus tard sous forme d'événement.
- **`WIFI_EVENT_STA_CONNECTED`** : la box a accepté la station. Mais elle n'a pas encore d'adresse IP.
- **`IP_EVENT_STA_GOT_IP`** : l'adresse IP est obtenue. La documentation est nette : c'est le moment où « tout est prêt » pour le réseau, et il ne faut **pas** commencer de travail réseau avant. Les données de l'événement (`void *data`) sont un `ip_event_got_ip_t` qui contient l'adresse.
- **`WIFI_EVENT_STA_DISCONNECTED`** : une tentative a échoué, ou la connexion est perdue. Il porte un code de raison (`wifi_event_sta_disconnected_t`, champ `reason`). Dans le simulateur : 201 (`WIFI_REASON_NO_AP_FOUND`, la box n'est pas là) ou 205 (`WIFI_REASON_CONNECTION_FAIL`, la connexion est refusée). La documentation indique que le code habituel de ce gestionnaire est de rappeler `esp_wifi_connect()` pour se reconnecter.

## La machine à états de la connexion

Comme la régulation de la piscine, la connexion est une **machine à états** : à chaque instant, le programme est dans un état précis, et chaque événement le fait passer à un autre.

```text
              STA_START                 STA_CONNECTED             GOT_IP
 DEMARRAGE ------------> TENTATIVE ---------------------> LIEN ------------> CONNECTE
                            |   ^                                              
          STA_DISCONNECTED  |   | attente écoulée, esp_wifi_connect()
                            v   |
                          ATTENTE ---- 10e échec ----> ABANDON
```

- **TENTATIVE** : `esp_wifi_connect()` a été appelée, on attend le résultat.
- **ATTENTE** : la tentative a échoué ; on attend avant de recommencer.
- **CONNECTE** : l'adresse est obtenue, c'est gagné.
- **ABANDON** : trop d'échecs, on s'arrête, **une seule** ligne d'erreur.

Vous n'avez pas besoin d'une variable « état » : le **compteur d'échecs de suite** (`echecs`) suffit. Il augmente à chaque `STA_DISCONNECTED`, il repart à zéro à la connexion, et sa valeur décide : attendre combien de temps, ou abandonner.

## Reconnecter sans marteler : l'attente croissante

La tentation : dans le gestionnaire de `STA_DISCONNECTED`, rappeler tout de suite `esp_wifi_connect()`. Si la box est absente, vous obtenez une boucle serrée : une tentative, un échec, une tentative, un échec, sans pause. Elle inonde le journal, fait travailler la radio pour rien et use la batterie. Si la box redémarre, des dizaines d'objets qui rappellent en même temps l'écrasent.

La règle du TP est une attente **croissante**, doublée à chaque échec, avec un **plafond** :

| Échecs de suite | Attente avant la tentative suivante |
|---|---|
| 1 | 1 s |
| 2 | 2 s |
| 3 | 4 s |
| 4 | 8 s |
| 5 et plus | 8 s (plafond) |

Pourquoi doubler ? Un réseau qui ne répond pas dès la première seconde a peu de chances de répondre à la seconde suivante : on laisse de plus en plus de temps. Pourquoi un plafond ? Sans lui, l'attente atteindrait 16 s, 32 s, 64 s, et un réseau qui revient après une minute serait retrouvé très tard. Avec le plafond de 8 s, on le retrouve au plus 8 s après son retour.

Le calcul tient en une petite fonction, qui ne dépend que du nombre d'échecs `n` (au moins 1) :

```cpp
static int attente_ms(int n) {
    int ms = 1000;
    for (int i = 1; i < n && ms < 8000; i++) {
        ms *= 2;
    }
    return ms;
}
```

`attente_ms(1)` vaut 1000, `attente_ms(3)` vaut 4000, `attente_ms(4)` et tout ce qui suit valent 8000.

**Où attendre ?** Pas dans le gestionnaire (règle n°1 de la section précédente). Le schéma de l'exemple officiel et de ce TP : le gestionnaire de `STA_DISCONNECTED` ne fait que **lever un drapeau** dans un **groupe d'événements**, et c'est une tâche (ici `app_main` elle-même) qui attend ce drapeau, puis `vTaskDelay`, puis rappelle `esp_wifi_connect()`.

Un **groupe d'événements** (`freertos/event_groups.h`) est un petit mot de bits partagé entre tâches. Chaque bit est un drapeau :

```cpp
static const EventBits_t BIT_CONNECTE = 1 << 0;
static const EventBits_t BIT_PERDU = 1 << 1;
static EventGroupHandle_t groupe;                 // groupe = xEventGroupCreate(); (une fois, avant le Wi-Fi)

xEventGroupSetBits(groupe, BIT_PERDU);            // lever un drapeau : peut s'appeler depuis un gestionnaire
EventBits_t bits = xEventGroupWaitBits(groupe, BIT_CONNECTE | BIT_PERDU, pdTRUE, pdFALSE, portMAX_DELAY);
```

`xEventGroupWaitBits(groupe, bits_attendus, effacer_en_sortie, attendre_tous, delai)` bloque la tâche jusqu'à ce que la condition soit vraie :

- `bits_attendus` : les bits qui nous intéressent ;
- `effacer_en_sortie` à `pdTRUE` : les bits attendus sont remis à zéro au retour (le drapeau est « consommé ») ;
- `attendre_tous` à `pdFALSE` : **un seul** des bits suffit (avec `pdTRUE`, il les faudrait tous) ;
- `delai` : `portMAX_DELAY` attend sans limite.

La valeur renvoyée contient les bits tels qu'ils étaient au moment où la condition est devenue vraie : on teste `bits & BIT_PERDU` pour savoir lequel est arrivé. Pendant l'attente, la tâche ne consomme rien : dans le simulateur comme sur la carte, le temps passe pour les autres tâches.

## Savoir abandonner : le nombre maximal d'essais

Un programme qui réessaie **sans fin** un réseau qui n'existe pas ne se règle jamais et ne le dit jamais. Le TP fixe un maximum de **10 tentatives de connexion au total, la première comprise**. Donc :

- les attentes sont celles du tableau, une par échec, **entre** deux tentatives : 1, 2, 4, 8, 8, 8, 8, 8, 8 secondes (9 attentes pour 10 tentatives) ;
- après le **10e échec**, on **n'attend pas** : on abandonne, avec **une seule** ligne `ESP_LOGE(TAG, ...)` (tag `wifi`) qui dit pourquoi ;
- après l'abandon, plus **aucun** appel à `esp_wifi_connect()`.

« Abandonner proprement » veut dire : un message d'erreur, plus de tentative, et un programme qui ne plante pas et ne redémarre pas la carte (`esp_restart()` est refusé par le contrôle : un redémarrage relancerait les dix tentatives, sans fin).

Les échecs **intermédiaires** ne sont pas des erreurs du programme : journalisez-les avec `ESP_LOGW` ou `ESP_LOGI`. Le contrôle exige **zéro** `ESP_LOGE` de tag `wifi` quand la connexion réussit, et **exactement un** quand on abandonne : une ligne d'erreur, c'est ce qu'un humain va chercher dans le journal.

!!Après le dixième échec, n'attendez pas et ne rappelez pas esp_wifi_connect : écrivez UN ESP_LOGE de tag wifi puis arrêtez de réessayer!!

## Journaliser l'adresse obtenue

Quand `IP_EVENT_STA_GOT_IP` arrive, l'adresse est dans les données de l'événement :

```cpp
ip_event_got_ip_t *ev = (ip_event_got_ip_t *)data;
ESP_LOGI(TAG, "adresse IP : " IPSTR, IP2STR(&ev->ip_info.ip));
```

`IPSTR` et `IP2STR` sont deux macros de ESP-IDF : `IPSTR` est le modèle `%d.%d.%d.%d`, `IP2STR(&adresse)` fournit les quatre nombres. Le contrôle attend **exactement** ce format : un `ESP_LOGI` de tag `wifi` dont le message est `adresse IP : 192.168.1.42` (l'adresse que le simulateur donne), écrit **une seule fois**, au moment où l'adresse est obtenue (pas avant). Il refuse aussi une adresse écrite en dur dans le code : on lit celle de l'événement.

## Un exemple pas à pas : un portail de garage

Ce n'est pas le TP, c'est un cas voisin. Un portail connecté doit rejoindre le réseau du garage, mais cette fois avec **3 tentatives maximum**, une attente qui commence à 2 s et double, plafonnée à 4 s.

- Démarrage : `STA_START` arrive, on appelle `esp_wifi_connect()` : tentative n° 1.
- Elle échoue (`STA_DISCONNECTED`) : `echecs` vaut 1, 1 est inférieur à 3, on attend 2 s (`attente_ms(1)`), puis tentative n° 2.
- Elle échoue : `echecs` vaut 2, on attend 4 s (le doublement donnerait 4, le plafond est 4), tentative n° 3.
- Elle échoue : `echecs` vaut 3, c'est le maximum : **pas d'attente**, une ligne `ESP_LOGE`, et c'est fini.
- Si la tentative n° 2 avait réussi, `STA_CONNECTED` puis `GOT_IP` arriveraient : on journalise l'adresse, `echecs` repart à zéro.

```cpp
echecs++;                                         // une tentative de plus a échoué
if (echecs >= MAX_TENTATIVES) {
    ESP_LOGE(TAG, "abandon : %d tentatives sans succès", MAX_TENTATIVES);
    return;                                       // plus aucun esp_wifi_connect()
}
vTaskDelay(pdMS_TO_TICKS(attente_ms(echecs)));    // d'abord attendre...
esp_wifi_connect();                               // ...puis réessayer
```

## Ce que le simulateur simplifie

- La **box** est un simple modèle : le scénario dit à partir de quand elle existe, quand elle est absente, et combien de tentatives elle refuse. Aucune radio, aucun signal, aucune analyse de réseaux (scan), aucun mot de passe vérifié : tout mot de passe de 8 caractères ou plus est accepté.
- Une tentative **échouée** dure 1 seconde, une tentative **réussie** donne `STA_CONNECTED` après 0,3 s puis `GOT_IP` 0,2 s plus tard. Sur une vraie carte, ces durées varient.
- **L'adresse** est toujours `192.168.1.42`.
- **La NVS** : le simulateur exige `nvs_flash_init()` avant `esp_wifi_init`, comme le font les exemples officiels. Sur une vraie carte, le comportement exact dépend de la configuration du projet : le motif d'initialisation reste le bon réflexe.
- Le simulateur ne renvoie jamais `ESP_ERR_NVS_NO_FREE_PAGES` ni `ESP_ERR_NVS_NEW_VERSION_FOUND` : le « si » du motif ne se déclenche pas, mais il doit être écrit, et le contrôle vérifie sa présence.
- Les valeurs `CONFIG_ESP_WIFI_SSID` et `CONFIG_ESP_WIFI_PASSWORD` sont fournies par le simulateur ; dans un vrai projet elles viennent de `menuconfig`.
- Le temps est virtuel et n'avance que pendant les attentes (`vTaskDelay`, `xEventGroupWaitBits`).

## Le programme du TP en un coup d'œil

```text
app_main :
  1. init_nvs()                                        (motif canonique)
  2. demarrer_wifi() :
       groupe = xEventGroupCreate()
       esp_netif_init, esp_event_loop_create_default, esp_netif_create_default_wifi_sta
       esp_wifi_init(WIFI_INIT_CONFIG_DEFAULT())
       enregistrer le gestionnaire : WIFI_EVENT (tous), IP_EVENT (GOT_IP)
       esp_wifi_set_mode(STA), esp_wifi_set_config (SSID et mot de passe de CONFIG_...), esp_wifi_start()
  3. boucle : xEventGroupWaitBits(BIT_CONNECTE | BIT_PERDU)
       BIT_CONNECTE : echecs = 0
       BIT_PERDU    : echecs++ ; si echecs >= 10 : ESP_LOGE puis return
                      sinon : vTaskDelay(attente_ms(echecs)) puis esp_wifi_connect()

gestionnaire (tâche sys_evt, ne bloque jamais) :
  STA_START        -> esp_wifi_connect()
  STA_DISCONNECTED -> xEventGroupSetBits(groupe, BIT_PERDU)
  GOT_IP           -> ESP_LOGI « adresse IP : ... » puis xEventGroupSetBits(groupe, BIT_CONNECTE)
```

Le contrôle fait tourner le programme **deux fois**, en temps virtuel :

- **a, trois échecs puis succès** : la box refuse les 3 premières tentatives. Il faut 4 tentatives, avec des attentes de **1 s, 2 s et 4 s**, puis l'adresse journalisée ;
- **b, réseau absent** : la box n'existe pas. Il faut **exactement 10 tentatives**, avec des attentes de **1, 2, 4, 8, 8, 8, 8, 8, 8 s**, puis une seule ligne `ESP_LOGE`, et plus aucune tentative pendant les 55 secondes restantes (la simulation dure 120 s).

Chaque attente est mesurée **entre la fin d'un échec et le début de la tentative suivante**, avec une tolérance : elle doit valoir la durée demandée, **au plus 50 ms de moins** et **au plus 500 ms de plus**. Une attente de 10 ms (`vTaskDelay(1)`) ou de 100 s ne passe pas.

## Pièges

!!Initialisez la NVS en premier : sans nvs_flash_init réussi, esp_wifi_init échoue (ESP_ERR_NVS_NOT_INITIALIZED dans le simulateur) et le programme s'arrête!!

!!Un gestionnaire d'événements s'exécute dans la tâche sys_evt : n'y faites ni vTaskDelay ni attente bloquante, levez un bit de groupe d'événements et laissez une autre tâche attendre!!

!!Réessayer sans attendre, c'est marteler la box : l'attente doit doubler à chaque échec (1 s, 2 s, 4 s, 8 s) et ne jamais dépasser 8 s!!

!!Enregistrez les gestionnaires avant esp_wifi_start, sinon WIFI_EVENT_STA_START est perdu et rien ne se connecte jamais!!

!!Une attente en millisecondes se convertit avec pdMS_TO_TICKS : vTaskDelay(attente) tout seul compte des ticks de 10 ms et attend dix fois trop longtemps!!

## À retenir

- Les étapes : **NVS**, `esp_netif_init`, boucle d'événements par défaut, interface station, `esp_wifi_init`, gestionnaires, mode et configuration, `esp_wifi_start`.
- Le motif NVS : `nvs_flash_init`, et **seulement** si `ESP_ERR_NVS_NO_FREE_PAGES` ou `ESP_ERR_NVS_NEW_VERSION_FOUND` : `nvs_flash_erase` puis `nvs_flash_init` de nouveau.
- Le **mot de passe** ne s'écrit jamais dans le code : `CONFIG_ESP_WIFI_PASSWORD` (menuconfig).
- Un **gestionnaire** tourne dans la tâche **`sys_evt`** : il ne bloque jamais, il note et réveille (groupe d'événements).
- `esp_wifi_connect()` lance **une** tentative ; le résultat arrive par `STA_CONNECTED` puis `GOT_IP`, ou par `STA_DISCONNECTED`.
- **Attente croissante** : 1 s, 2 s, 4 s, 8 s, puis 8 s. **Maximum 10 tentatives** au total, attentes entre elles, abandon après le 10e échec avec **un** `ESP_LOGE`.
- L'adresse se journalise une fois, au format `adresse IP : ` suivi de `IPSTR` : on la lit dans l'événement, on ne l'écrit pas dans le code.
