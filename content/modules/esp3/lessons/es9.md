# Robustesse : survivre aux coupures, aux redémarrages et aux blocages

**Le problème concret :** votre contrôleur de piscine publie sa télémétrie en MQTT (leçon précédente). Dans une vraie maison, trois choses arrivent tôt ou tard : **le courtier MQTT tombe** (la box redémarre, le serveur est mis à jour) ; **la carte redémarre** (coupure de courant, mise à jour) ; **le programme se bloque** (une boucle qui n'en finit pas). Un contrôleur « robuste » doit alors rester **utilisable et sûr** : continuer à publier quand le courtier revient, recevoir encore les commandes, **se souvenir de ses réglages** après un redémarrage, et **ne jamais allumer la pompe par hasard** au démarrage. Cette leçon apprend les outils d'ESP-IDF pour cela : la reconnexion MQTT et le réabonnement, la mémoire **NVS**, le **watchdog de tâche** et la gestion des erreurs.

Cette leçon contient toute la théorie du TP. Lisez-la dans l'ordre : les messages du contrôle vous disent quelle section relire. Elle suppose les leçons précédentes : MQTT et les commandes (TP 8), le Wi-Fi (TP 7), le relais sur la GPIO 5 et la **limite de sécurité de 80 %** (TP 6), la lecture du niveau avec l'ADC (TP 4).

Tout ce qui est écrit ici est le vrai ESP-IDF (version 5.5.3), sauf la section « Ce que le simulateur simplifie », qui liste les écarts du TP. Le TP tourne dans le simulateur, qui sait **couper le courtier** et **redémarrer la carte** à des instants fixés par le scénario.

## Reprendre après une coupure du courtier

Quand le courtier disparaît, le client MQTT d'ESP-IDF **ne s'arrête pas** : il prévient votre gestionnaire (`MQTT_EVENT_DISCONNECTED`), puis **réessaie tout seul** de se connecter, toutes les 10 secondes par défaut (champ `network.reconnect_timeout_ms`). Cela dure tant que vous n'avez pas mis `network.disable_auto_reconnect` à `true`. Vous n'écrivez donc **aucune boucle de reconnexion** : au retour du courtier, un nouvel événement `MQTT_EVENT_CONNECTED` arrive.

Reste ce que le client **ne fait pas pour vous** :

- **Les abonnements.** Par défaut la **session est propre** (`session.disable_clean_session` vaut `false`) : à chaque connexion le courtier **oublie** tout ce qu'il savait de vous, abonnements compris. Après une coupure, votre carte est connectée mais **sourde** aux commandes, et rien ne signale l'erreur. La règle : **s'abonner dans la réaction à `MQTT_EVENT_CONNECTED`, à chaque connexion**, jamais une seule fois au démarrage.

```cpp
case MQTT_EVENT_CONNECTED:
    esp_mqtt_client_subscribe_single(ev->client, TOPIC_COMMANDE, 1);   // à CHAQUE connexion
    break;
```

- **Et si la session n'est pas propre ?** Avec `session.disable_clean_session = true`, la spécification MQTT autorise le courtier à **garder** la session (donc vos abonnements) d'une connexion à l'autre ; l'événement de connexion porte alors le drapeau `session_present` (la documentation d'ESP-IDF cite ce champ sans le détailler : sa signification vient de la spécification MQTT). Mais le courtier peut aussi avoir tout perdu (il a redémarré, il a purgé la session). S'abonner à chaque connexion marche **dans les deux cas** : un nouvel abonnement au même filtre remplace simplement l'ancien. C'est la règle du TP, qui garde la session propre.
- **Les messages publiés pendant la coupure.** `esp_mqtt_client_publish` renvoie **-1** pour un message de **QoS 0** quand le client est déconnecté : il est **perdu**, il n'est pas mis en attente. Les messages de QoS 1 ou 2 sont, eux, mis en file d'attente et envoyés après la reconnexion (ils expirent après le délai `CONFIG_MQTT_OUTBOX_EXPIRED_TIMEOUT_MS`). Une mesure toutes les 10 s se publie en QoS 0 : la suivante arrive dans 10 s, rejouer l'ancienne n'aurait aucun intérêt.
- **L'état local.** Votre programme continue à tourner pendant la coupure : le relais reste piloté par les dernières consignes connues. Une coupure du courtier ne doit **pas** arrêter la régulation.

Le scénario a du TP coupe le courtier **60 secondes**, puis envoie une commande **après** la reconnexion : elle n'arrive que si vous vous êtes réabonné.

## La consigne : un JSON de commande, des bornes de sécurité

Jusqu'ici la limite de remplissage était une constante. Dans ce TP, le **niveau haut** est une **consigne** réglable à distance : au lieu de « s'arrêter à 80 % » une fois pour toutes, la pompe s'arrête au niveau choisi par l'utilisateur dans l'application, par exemple 75 %. La règle de régulation du TP, volontairement simple :

- le relais est **allumé** si le niveau, lu sur le capteur **à cet instant**, est **strictement inférieur** à la consigne ; sinon il est **éteint** (une régulation réelle ajouterait une hystérésis, voir le TP 6 : le niveau du TP est constant, elle n'apporterait rien ici) ;
- tant qu'aucune consigne n'a été reçue ni enregistrée, la consigne vaut **60 %** (`HAUT_DEFAUT`).

**Le format de la commande**, décidé pour ce TP : un message sur `home/devices/pool-ctl/command` dont la charge utile est un JSON avec la clé `high`, un **entier** en pourcent : `{"high": 75}`. Les espaces sont libres (`{"high":75}` est aussi valide) et la valeur peut ne pas être un nombre : on doit y résister. Les commandes de relais du TP 8 n'existent plus ici : ce topic ne porte que la consigne.

**Les bornes de sécurité.** Une commande à distance ne contourne jamais la limite du TP 6. Les règles du TP :

- une consigne **de 10 à 80 % inclus** est **acceptée** : 80 est la limite de sécurité absolue du TP 6, 10 est un plancher (au-dessous, la pompe ne s'arrêterait presque jamais de tourner) ;
- une consigne **hors de ces bornes** (95, ou 5) est **refusée** : la consigne actuelle **ne change pas** et n'est **pas** enregistrée en NVS ; une seule ligne est journalisée, **exactement** : `ESP_LOGW(TAG, "setpoint refused: high=%ld", valeur);` avec le tag `robust`. Pour 95, la ligne est `setpoint refused: high=95` ;
- un message qui **n'est pas une commande** (un texte quelconque, une clé inconnue, une valeur qui n'est pas un nombre comme `{"high": "abc"}`) est **ignoré en silence** : ni changement, ni ligne de refus.

On refuse plutôt qu'on ne « ramène à 80 » : un ordre de 95 % est probablement une erreur de l'utilisateur, il vaut mieux qu'il le sache (la ligne de refus le dit) que de faire autre chose que ce qu'il a demandé.

**Lire l'entier.** `topic` et `data` d'un événement MQTT ne sont **pas** terminés par un NUL (TP 8) : on copie d'abord les `len` octets dans un tampon `msg[64]` terminé par un NUL, on cherche `"high"` avec `strstr`, on saute les espaces et le `:`, puis on lit le nombre avec **`strtol`**.

```cpp
char msg[64];
int n = len < (int)sizeof(msg) - 1 ? len : (int)sizeof(msg) - 1;
memcpy(msg, data, n);
msg[n] = '\0';
const char *p = strstr(msg, "\"high\"");      // NULL : pas une commande
if (p == NULL) return;
p += strlen("\"high\"");
while (*p == ' ' || *p == ':') p++;
char *fin;
long valeur = strtol(p, &fin, 10);            // fin == p : aucun chiffre lu
if (fin == p) return;
```

`strtol(texte, &fin, 10)` lit un entier en base 10 et met dans `fin` l'endroit où la lecture s'est arrêtée : si `fin == p`, il n'y avait pas de nombre (`"abc"` commence par un guillemet : rien n'est lu). Contrairement à `atoi`, il permet donc de **détecter** l'erreur, et une valeur énorme donne un `long` immense que le test de bornes refuse. (`sscanf(p, "%d", &v) == 1` détecte l'erreur aussi.)

Une fois acceptée, la consigne est écrite dans la variable partagée `haut` (un `std::atomic<int>` : elle est écrite par la tâche `mqtt_task` et lue par `app_main`) **et** enregistrée en NVS (section suivante). La **télémétrie** publie la consigne en vigueur : `{"level": 72.5, "relay": false, "high": 75}`. C'est ce qui permet au contrôle (et à l'application) de voir quelle consigne la carte utilise réellement.

## Sauvegarder en NVS : ouvrir, écrire, valider

Une variable en RAM **disparaît** au redémarrage. Pour garder un réglage, on l'écrit dans la **NVS** (*Non-Volatile Storage*), une zone de la mémoire flash organisée en paires **clé / valeur**. Les valeurs sont rangées dans des **espaces de noms** (*namespaces*) ; clés et noms d'espaces font **15 caractères au plus**. Types possibles : entiers de 8 à 64 bits, signés ou non (`nvs_set_u8`, `nvs_set_i32`...), chaînes terminées par un NUL, et blocs d'octets (*blobs*).

Avant tout, la NVS doit être initialisée, une fois : `nvs_flash_init()`. L'idiome officiel (déjà dans `init_nvs`, fourni) : si elle renvoie `ESP_ERR_NVS_NO_FREE_PAGES` ou `ESP_ERR_NVS_NEW_VERSION_FOUND`, on efface la partition (`nvs_flash_erase()`) et on réessaie. Le Wi-Fi en a aussi besoin, c'est pourquoi `app_main` l'appelle **en premier**.

**Écrire** suit toujours les quatre mêmes temps :

```cpp
nvs_handle_t h;
esp_err_t err = nvs_open("pool", NVS_READWRITE, &h);     // 1. ouvrir l'espace de noms
if (err == ESP_OK) {
    err = nvs_set_i32(h, "haut", 75);                    // 2. écrire
    if (err == ESP_OK) err = nvs_commit(h);              // 3. VALIDER
    nvs_close(h);                                        // 4. fermer
}
```

- **`nvs_commit` est obligatoire.** La documentation dit : après avoir écrit des valeurs, `nvs_commit()` **doit** être appelée pour garantir qu'elles sont écrites en mémoire non volatile ; une implémentation peut écrire à d'autres moments, mais ce n'est **pas garanti**. Et `nvs_close` ne le fait pas non plus : « fermer le handle peut ne pas écrire les changements ». **Sur une vraie carte, l'oubli du commit peut passer inaperçu** (l'implémentation actuelle écrit souvent tout de suite), et le bug apparaît un jour, ailleurs. **Le simulateur est plus strict que la carte** : il n'enregistre que ce qui a été validé avec `nvs_commit`, et perd le reste au redémarrage. Prenez donc l'habitude : **toute écriture est suivie de `nvs_commit`**. Le contrôle vérifie un `nvs_commit` dans les 2 secondes de chaque écriture.
- **Une clé est d'un type.** Ce qu'on a écrit avec `nvs_set_i32` se relit avec `nvs_get_i32` ; un autre type renvoie une erreur (`ESP_ERR_NVS_TYPE_MISMATCH`).
- **Ménagez la flash.** La NVS répartit l'usure, mais une flash a un nombre limité d'effacements : on écrit **quand la valeur change** (une commande de l'utilisateur), pas à chaque tour de boucle.
- **Vérifiez les codes de retour**, sans arrêter la carte : si la NVS tombe en panne, on journalise (`ESP_LOGE` avec `esp_err_to_name(err)`) et on continue, la pompe doit rester pilotée (section sur `ESP_ERROR_CHECK`).

**Relire**, avec une **valeur par défaut** pour le premier démarrage, quand rien n'a encore été écrit :

```cpp
nvs_handle_t h;
if (nvs_open("pool", NVS_READONLY, &h) != ESP_OK) return HAUT_DEFAUT;  // espace de noms encore inconnu
int32_t valeur = HAUT_DEFAUT;
esp_err_t err = nvs_get_i32(h, "haut", &valeur);
nvs_close(h);
if (err == ESP_ERR_NVS_NOT_FOUND) return HAUT_DEFAUT;                   // clé jamais écrite
```

- Ouvert en `NVS_READONLY`, un espace de noms qui n'existe pas encore fait échouer `nvs_open` avec `ESP_ERR_NVS_NOT_FOUND` (documenté) : c'est le **premier démarrage**, pas une panne. Un handle `NVS_READONLY` refuse toute écriture.
- `nvs_get_i32` renvoie `ESP_ERR_NVS_NOT_FOUND` si la clé n'existe pas. En cas d'erreur, la valeur de sortie est **laissée inchangée** (documenté).
- **Ne faites pas confiance à ce que vous relisez** : une valeur hors des bornes 10 à 80 % (flash corrompue, ancienne version du programme) est écartée, avec un `ESP_LOGW` et la valeur par défaut : on ne pilote jamais la pompe avec une consigne qui n'a pas le droit d'exister.

## Restaurer au démarrage, avant d'allumer le relais

Quand la carte redémarre, **tout ce qui est en RAM est perdu** : variables, tâches, états des broches (le relais retombe éteint, ce qui est l'état sûr), connexions Wi-Fi et MQTT. Ce qui survit : la **NVS** (ce qui a été validé). Le programme repart de `app_main`. Pour savoir **pourquoi** on a redémarré, `esp_reset_reason()` (en-tête `esp_system.h`) renvoie une valeur comme `ESP_RST_POWERON` (mise sous tension), `ESP_RST_SW` (`esp_restart()`), `ESP_RST_PANIC` ou `ESP_RST_TASK_WDT` (watchdog de tâche) : un bon réflexe est de la journaliser au démarrage.

**L'ordre du démarrage compte**, parce que le relais pilote une pompe :

1. `init_relais()` : broche en sortie, **éteinte**. C'est l'état sûr : tant que le programme ne connaît pas la consigne, il n'allume **rien**.
2. `init_adc()` puis `init_nvs()`.
3. **Relire la consigne** : `haut = charger_consigne();`.
4. **Seulement ensuite**, piloter le relais : `appliquer_consigne()` (lit le niveau, allume si le niveau est sous la consigne relue).
5. Le réseau : `wifi_connecter()`, `demarrer_mqtt()`.
6. Le watchdog, puis la boucle principale.

L'erreur classique est d'allumer le relais « par défaut » au démarrage, ou de piloter le relais **avant** d'avoir relu la consigne : avec la consigne par défaut (60 %), un niveau de 50 % allume la pompe, puis la consigne enregistrée (40 %) l'éteint une fraction de seconde plus tard. Sur une vraie piscine, ce clic de relais peut remplir pendant que le logiciel « corrige » : la pompe ne doit tourner que d'après une consigne **connue**. Le scénario b du TP redémarre la carte avec une consigne de 40 % pour un niveau de 50 % : le relais ne doit **jamais** s'allumer après le redémarrage, pas même brièvement.

Le point 4 se fait **avant** `wifi_connecter()`, qui bloque jusqu'à l'obtention d'une adresse IP : la régulation ne doit pas dépendre du réseau.

## Le watchdog de tâche : surveiller la boucle

Si votre boucle principale se bloque (attente infinie, boucle sans fin), la pompe reste figée dans son dernier état. Le **watchdog de tâche** (*Task Watchdog Timer*, TWDT) est un chien de garde : des tâches s'**abonnent** à lui et doivent l'**alimenter** (*feed*) régulièrement ; si l'une d'elles oublie pendant plus que le délai, le watchdog se déclenche.

Ce que dit la documentation d'ESP-IDF 5.5.3 :

- Le TWDT est **initialisé automatiquement au démarrage** (option `CONFIG_ESP_TASK_WDT_INIT`, activée par défaut). Il surveille déjà les **tâches idle** des cœurs 0 et 1 (la documentation dit que celle de chaque cœur est abonnée au démarrage, options `CONFIG_ESP_TASK_WDT_CHECK_IDLE_TASK_CPU0` et `CONFIG_ESP_TASK_WDT_CHECK_IDLE_TASK_CPU1`, activées par défaut ; une tâche idle est la tâche qui tourne quand rien d'autre ne tourne : si une tâche monopolise le processeur, idle ne passe plus et le watchdog le voit). La documentation de l'API ne donne pas le délai par défaut en secondes : il vient de `CONFIG_ESP_TASK_WDT_TIMEOUT_S` (le simulateur prend 5 s).
- Votre tâche (par exemple `app_main`) n'y est **pas** abonnée par défaut : la documentation ne cite que les tâches idle. Elle doit appeler **`esp_task_wdt_add(NULL)`** (`NULL` = la tâche courante), puis **`esp_task_wdt_reset()`** régulièrement, **plus souvent que le délai**.
- Comme il est déjà initialisé, **`esp_task_wdt_init` renvoie `ESP_ERR_INVALID_STATE`** si on l'appelle. Pour changer les réglages, on utilise **`esp_task_wdt_reconfigure(&cfg)`** avec une structure `esp_task_wdt_config_t` :

```cpp
esp_task_wdt_config_t cfg = {};
cfg.timeout_ms = 15000;        // délai : TWDT TIMEOUT
cfg.idle_core_mask = (1 << 0) | (1 << 1);   // garder la surveillance des tâches idle des cœurs 0 et 1
cfg.trigger_panic = true;      // redémarrer la carte au déclenchement
ESP_ERROR_CHECK(esp_task_wdt_reconfigure(&cfg));
ESP_ERROR_CHECK(esp_task_wdt_add(NULL));       // abonner la tâche courante
// ... puis, dans la boucle :  ESP_ERROR_CHECK(esp_task_wdt_reset());
```

- `timeout_ms` : le délai. `idle_core_mask` : les cœurs dont la tâche idle est surveillée (`1 << i` : la tâche idle du cœur i) ; on remet ici les deux cœurs pour **ne rien perdre** de la surveillance par défaut. `trigger_panic` : « déclencher une panique quand le délai expire ».
- **Quand il se déclenche** : si une tâche abonnée n'a pas appelé `esp_task_wdt_reset` dans le délai. Avec `trigger_panic = false` (le comportement par défaut), la documentation dit que le watchdog **affiche seulement un avertissement et une trace avant de laisser le programme continuer** : rien ne redémarre. Avec `trigger_panic = true` (ou l'option `CONFIG_ESP_TASK_WDT_PANIC`), il provoque une **panique et la carte redémarre** (le motif de redémarrage est `ESP_RST_TASK_WDT`). Pour une pompe, on veut en général que la carte **redémarre** (elle repart dans l'état sûr, relais éteint, puis relit sa consigne) : on met `true`.
- **Le délai doit être plus long que le pire tour de boucle**. Ici : la boucle tourne chaque seconde, mais une publication MQTT peut, d'après la documentation, **bloquer plusieurs secondes** (jusqu'au délai réseau de 10 s) : le TP prend **15 s**. Trop court, le watchdog redémarre une carte saine ; trop long, il met du temps à réagir.
- **Où alimenter ?** Dans la boucle principale, **une fois par tour**, pas dans une sous-fonction appelée de temps en temps : le but est de prouver que **la boucle entière** avance. Surtout, **ne pas s'abonner avant une initialisation longue** : `wifi_connecter()` peut attendre longtemps l'adresse IP, et une tâche abonnée qui n'a pas encore atteint sa boucle déclencherait le watchdog. On s'abonne juste **avant** la boucle.
- Une tâche qui s'arrête doit se désabonner avec `esp_task_wdt_delete` : la documentation précise qu'une tâche désabonnée ne doit plus appeler `esp_task_wdt_reset` ; abonnée mais disparue, elle n'alimenterait plus le watchdog, qui se déclencherait.

Dans le TP, aucun scénario ne bloque votre programme : le contrôle ne peut donc pas tester le redémarrage. Il vérifie deux choses : **le watchdog ne se déclenche jamais** (événement `wdt_reset` dans la trace du simulateur : une tâche abonnée qui n'est pas alimentée à temps le provoque) et, en lisant le texte de `main.cpp`, que le programme appelle bien **`esp_task_wdt_add` et `esp_task_wdt_reset`** (le simulateur ne trace pas l'abonnement : sans cette lecture, un programme sans watchdog passerait). Un appel dans un commentaire ne compte pas. Le choix `trigger_panic = true` est dans l'énoncé mais n'est pas contrôlé.

## Gérer l'erreur au lieu d'abandonner : ESP_ERROR_CHECK

`ESP_ERROR_CHECK(expr)` vérifie que `expr` vaut `ESP_OK` ; sinon il affiche un message d'erreur sur la console puis appelle **`abort()`**. Avec la configuration par défaut d'ESP-IDF, après un `abort()` **la carte redémarre**. La documentation d'ESP-IDF précise que ce n'est « pas la meilleure pratique pour une application » : il sert surtout dans les exemples, par concision. Elle recommande, selon le cas, de **réessayer**, de **propager l'erreur** à l'appelant, ou de la traiter comme irrécupérable.

La règle de ce TP : **`ESP_ERROR_CHECK` pour ce qui ne doit jamais échouer et sans quoi le programme n'a aucun sens** (configurer la broche du relais, initialiser l'ADC au démarrage), **une vraie gestion d'erreur pour tout ce qui peut échouer en fonctionnement normal**. Une coupure du courtier **n'est pas une erreur fatale**, c'est un événement normal. La publication de la télémétrie en est l'exemple :

```cpp
if (esp_mqtt_client_publish(client, TOPIC_TELEMETRIE, json, 0, 0, 0) < 0) {
    ESP_LOGI(TAG, "télémétrie non envoyée (hors connexion)");     // on journalise et on continue
}
```

- `esp_mqtt_client_publish` renvoie un **entier** (l'identifiant du message, 0 en QoS 0 ; -1 en cas d'échec, -2 si la file est pleine), **pas** un `esp_err_t`. Le passer à `ESP_ERROR_CHECK` ferait **abandonner le programme** dès que le courtier est absent : au démarrage (le client n'est pas encore connecté) ou pendant la coupure du scénario a. Et si l'abandon redémarre la carte, le programme repart, publie, échoue, redémarre... **Une panne du réseau ne doit jamais arrêter le contrôle de la pompe.**
- **Journaliser et continuer.** Le message d'un `ESP_LOGI` dit ce qui s'est passé ; la télémétrie **reprend d'elle-même** à la reconnexion, sans rien faire de plus. Un programme qui s'arrête de publier après le premier échec est faux.
- Pour **voir** une erreur sans arrêter le programme, ESP-IDF offre `ESP_ERROR_CHECK_WITHOUT_ABORT(expr)` : même message que `ESP_ERROR_CHECK`, mais **sans** `abort()`. On peut aussi tester le code soi-même et écrire `ESP_LOGE(TAG, "...: %s", esp_err_to_name(err))`.
- Les mêmes principes valent pour la NVS (section précédente) : une écriture qui échoue se journalise, elle n'arrête pas la pompe.

Conséquence pour le contrôle : le **moindre redémarrage non prévu** par le scénario (un `esp_restart`, le watchdog, un `ESP_ERROR_CHECK` qui abandonne et fait redémarrer) fait échouer le TP. Le seul redémarrage attendu est celui du scénario : la coupure de courant.

## Le programme du TP en un coup d'œil

```text
app_main :
  init_relais(), init_adc(), init_nvs()                  (fournis ; le relais est éteint)
  haut = charger_consigne()                              (étapes 2 et 8 : relire la NVS, défaut 60)
  appliquer_consigne()                                   (étapes 6 et 8 : relais d'après la consigne RELUE)
  wifi_connecter(), demarrer_mqtt()                      (fournis)
  configurer_watchdog()                                  (étape 7 : reconfigure + add)
  boucle, une fois par seconde :                         (étape 8)
    esp_task_wdt_reset(), appliquer_consigne()
    tous les 10 tours : publier_telemetrie()             (étape 5 : -1 hors connexion : journaliser, continuer)
    vTaskDelay(1 s)

gestionnaire_mqtt (tâche mqtt_task, ne bloque jamais) :  (étape 4)
  CONNECTED : s'abonner à .../command (QoS 1), À CHAQUE connexion
  DATA      : si le sujet (avec topic_len) est .../command : traiter_commande(data, data_len)

traiter_commande(data, len) :                            (étape 3)
  copier dans msg[64] ; "high" ; strtol ; hors 10..80 : « setpoint refused: high=%ld » ; sinon haut = valeur et sauver_consigne

sauver_consigne(v) : nvs_open, nvs_set_i32, nvs_commit, nvs_close           (étape 1)
charger_consigne() : nvs_open READONLY, nvs_get_i32, défaut si absent       (étape 2)
```

Le contrôle fait tourner le programme **trois fois**, en temps virtuel. Le niveau du réservoir est constant dans chaque exécution :

- **a, niveau 72,5 %** (180 s) : `{"high": 55}` à 30 s ; **courtier coupé de 50 s à 110 s** (60 s ; le client se reconnecte seul, vers 110,6 s) ; `{"high":75}` à 115 s, reçue seulement si vous vous êtes **réabonné** : le relais doit s'allumer (72,5 est sous 75) ; **redémarrage à 120 s** (coupure de courant) : la consigne 75 doit être **relue de la NVS** (et non la valeur par défaut de 60 %) : le relais doit se rallumer dans les 5 s qui suivent ; `{"high": 65}` à 150 s, reçue seulement si vous vous êtes réabonné **après le redémarrage** : le relais doit s'éteindre ;
- **b, niveau 50 %** (100 s) : par défaut (60 %) le relais est allumé ; `{"high": 40}` à 30 s : le relais s'éteint ; **redémarrage à 60 s** : la consigne 40 est relue **avant** de piloter le relais, qui ne s'allume **jamais** (pas même un instant) ;
- **c, niveau 85,3 %** (80 s) : `salut` (10 s) ignoré ; `{"high": 95}` (20 s) et `{"high": 5}` (40 s) refusées avec les lignes `setpoint refused: high=95` et `setpoint refused: high=5` ; `{"high": "abc"}` (50 s) ignorée en silence ; `{"high": 80}` (55 s) et `{"high": 10}` (62 s) acceptées (bornes incluses). Le relais n'est jamais allumé (85 % est au-dessus de toute consigne permise).

Ce que le contrôle vérifie, dans chaque exécution : aucun `wdt_reset` ; **aucun redémarrage** autre que ceux du scénario ; à **chaque connexion** (la reconnexion et celle d'après le redémarrage comprises), un abonnement à `home/devices/pool-ctl/command` (le filtre exact, ou un filtre avec jokers qui le couvre) dans les 5 s ; les écritures NVS suivies de `nvs_commit` dans les 2 s, et aucune valeur refusée écrite ; le **relais** (broche 5, sortie, niveau lu sur le canal 6 de l'ADC) conforme à la consigne en vigueur, à 2 s près après une commande et à 5 s près après un démarrage ; la **télémétrie** sur `home/devices/pool-ctl/telemetry` : un JSON avec **exactement** les clés `level` (à 1 point près), `relay` (état réel de la broche à cet instant) et `high` (la consigne en vigueur), de 8 s à 12 s entre deux messages d'une même connexion, et reprise après chaque coupure ; les lignes de refus ; enfin, la lecture du texte de `main.cpp` pour `esp_task_wdt_add` et `esp_task_wdt_reset`.

## Ce que le simulateur simplifie

- **`nvs_commit` est exigé** : le simulateur n'enregistre que ce qui a été validé et perd le reste au redémarrage. Une vraie carte écrit souvent tout de suite : l'oubli du commit y passe parfois inaperçu. Le simulateur est **plus strict** que la réalité, ce qui est une bonne pratique à garder. Pas d'usure de flash, de pages ni de manque de place : `nvs_flash_init` ne renvoie jamais `ESP_ERR_NVS_NO_FREE_PAGES`.
- **Le redémarrage** est un vrai redémarrage du programme (variables, tâches, broches remises à zéro, la NVS validée est conservée) à l'instant du scénario, sans durée ; les tampons d'affichage non vidés sont perdus. Plus de 50 redémarrages au même instant, ou plus de 300 dans une exécution, arrêtent la simulation (boucle de redémarrages).
- **Le watchdog** : les tâches idle ne sont pas simulées (une tâche qui ne rend jamais la main arrête la simulation avec un message dédié) ; le délai par défaut du simulateur est de 5 s ; sans `trigger_panic`, il avertit et se répète à chaque délai écoulé (la documentation dit seulement qu'il affiche un avertissement et laisse le programme continuer).
- **Le courtier** : un seul, sans keep-alive, sans testament ni message retenu (TP 8) ; la reconnexion est tentée toutes les 10 s après une erreur ou une déconnexion ; après une coupure, une tentative de connexion échoue (0,1 s) puis la suivante a lieu 10 s plus tard.
- **`ESP_ERROR_CHECK`** : un échec arrête la simulation (le contrôle le signale) ; sur une vraie carte l'`abort()` fait en plus redémarrer la carte par défaut.
- **Pas de minuteur logiciel FreeRTOS** ni de cJSON : le JSON se produit avec `snprintf` et se lit avec `strstr` et `strtol`. Les tâches comptent dans une limite (le Wi-Fi, la boucle d'événements et le client MQTT en prennent trois) : le TP n'en crée aucune.
- Le temps est virtuel et n'avance que pendant les attentes ; l'abonnement au watchdog n'est pas tracé (d'où la lecture du texte).

## Pièges

!!Après une coupure du courtier, la session propre a tout oublié : abonnez-vous dans la réaction à MQTT_EVENT_CONNECTED, à chaque connexion, sinon la carte devient sourde sans aucune erreur!!

!!Toute écriture en NVS se termine par nvs_commit : nvs_close ne valide rien, et le simulateur, plus strict que la carte, perd l'écriture au redémarrage!!

!!Au démarrage, relisez la consigne enregistrée avant de piloter le relais : un relais allumé par défaut puis corrigé un instant plus tard peut remplir la piscine!!

!!Un message reçu n'est jamais une consigne de confiance : bornes 10 à 80 % (la limite de sécurité du TP 6), refus journalisé, texte quelconque ignoré, valeur relue de la NVS revérifiée!!

!!Un watchdog abonné doit être alimenté à chaque tour de la boucle, avec un délai plus long que le pire tour, et jamais avant une initialisation qui bloque!!

!!Ne mettez pas ESP_ERROR_CHECK autour d'une publication : une coupure du courtier n'est pas fatale, esp_mqtt_client_publish renvoie -1 hors connexion, on journalise et on continue!!

## À retenir

- Le client MQTT **se reconnecte tout seul** (toutes les 10 s par défaut) ; la session est **propre** par défaut : **réabonnez-vous à chaque `MQTT_EVENT_CONNECTED`**. En QoS 0, un message publié hors connexion est refusé (-1) et perdu.
- **NVS** : `nvs_flash_init`, puis `nvs_open` (espace de noms de 15 caractères au plus), `nvs_set_i32` / `nvs_get_i32`, **`nvs_commit`**, `nvs_close`. `ESP_ERR_NVS_NOT_FOUND` : prendre la **valeur par défaut**. Ouvert en lecture seule, un espace inconnu donne `ESP_ERR_NVS_NOT_FOUND` aussi.
- Un redémarrage perd la RAM et garde la NVS validée : **relire la consigne, puis seulement piloter le relais**. `esp_reset_reason()` dit pourquoi on a redémarré.
- Une consigne reçue est **bornée** (10 à 80 %), **refusée avec une ligne de journal** hors bornes, **enregistrée** quand elle est acceptée ; un texte quelconque est ignoré. `strtol` lit l'entier et détecte l'erreur.
- **Watchdog de tâche** : déjà initialisé au démarrage ; `esp_task_wdt_reconfigure` pour régler (`esp_task_wdt_init` donne `ESP_ERR_INVALID_STATE`), `esp_task_wdt_add(NULL)` pour s'abonner, `esp_task_wdt_reset()` à chaque tour ; sans `trigger_panic` il avertit seulement, avec il redémarre la carte.
- **`ESP_ERROR_CHECK`** abandonne le programme (`abort()`, puis redémarrage par défaut) : réservé à ce qui ne doit jamais échouer. Pour une panne attendue (courtier absent), **tester le résultat, journaliser, continuer** ; `ESP_ERROR_CHECK_WITHOUT_ABORT` affiche sans arrêter.
