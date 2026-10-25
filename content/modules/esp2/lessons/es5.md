# Relais et capteur I2C : survivre à une panne

**Le problème concret :** un petit ventilateur doit se mettre en marche quand il fait trop chaud. Un capteur de température, relié par le bus **I2C**, donne la température ; un **relais** (un interrupteur commandé par l'ESP32) allume le ventilateur au-dessus de **28,0 °C**. Mais un fil peut se débrancher, un capteur peut ne plus répondre pendant quelques secondes : le programme doit alors **continuer à tourner**, garder le ventilateur dans son état, et le dire dans le journal **une seule fois**.

Cette leçon contient toute la théorie du TP. Lisez-la dans l'ordre : les messages du contrôle vous disent quelle section relire. Elle suppose les leçons précédentes (broches, `vTaskDelay`, journaux avec `ESP_LOGI`) et la leçon sur l'ADC.

## Le bus I2C : adresse, ACK et NACK

Un **bus** est un ensemble de fils partagés par plusieurs composants. Le bus **I2C** (on lit « i-deux-c ») n'utilise que **deux fils** :

- **SDA** : les données (*Serial DAta*) ;
- **SCL** : l'horloge (*Serial CLock*), qui rythme les échanges.

Un composant, le **maître** (ici l'ESP32), mène la conversation. Les autres, les **périphériques** (ici le capteur), ne parlent que quand on les interroge. Comme tous les périphériques écoutent les mêmes fils, chacun a une **adresse**, un petit nombre sur **7 bits** (de 0 à 127). Notre capteur est à l'adresse **0x44** (le préfixe `0x` signifie « écrit en hexadécimal » : 0x44 vaut 68). Le maître commence chaque échange en envoyant l'adresse visée.

Le périphérique qui reconnaît son adresse répond par un signal d'accusé de réception : l'**ACK** (*acknowledge*). S'il ne répond pas, c'est un **NACK** (*not acknowledge*) : personne n'a confirmé. Le maître sait alors que l'échange a échoué.

**Pourquoi un capteur peut-il cesser de répondre ?** Parmi les causes générales (cela dépend du montage, pas d'ESP-IDF) : un fil débranché ou mal serré, une alimentation qui chute, un composant occupé à se redémarrer, un autre composant qui bloque le bus. La panne est souvent **passagère** : le capteur répond de nouveau quelques secondes plus tard. Un bon programme ne doit donc pas s'effondrer à la première lecture ratée.

Deux précisions données par la documentation d'ESP-IDF :

- l'adresse que l'on passe au pilote est l'adresse sur 7 bits **sans** le bit lecture/écriture : pour notre capteur, `0x44` tel quel, sans la décaler ;
- sur une vraie carte, il faut des **résistances de rappel** (*pull-up*) sur SDA et SCL : la documentation recommande une résistance externe adaptée, avec une valeur usuelle de **1 kΩ à 10 kΩ**, et précise que le rappel interne n'est pas assez fort pour un bus rapide. Le TP active le rappel interne (`enable_internal_pullup`), ce qui suffit pour le simulateur.

!!Une adresse I2C fausse ne produit aucune erreur de compilation : le capteur ne répond simplement jamais, et chaque lecture échoue!!

## Le capteur simulé et ses 2 octets

Un capteur I2C répond par des **octets**. Le capteur de ce TP est **simplifié** : il renvoie **2 octets**, le premier est l'**octet de poids fort** (celui qui compte le plus, comme les centaines dans 342), le second l'**octet de poids faible** (comme les unités). Ensemble, ils forment un nombre **non signé de 16 bits**, de 0 à 65535.

Ce nombre vaut **(température + 40,0 °C) × 10**, c'est-à-dire la température en **dixièmes de degré**, décalée de 40,0 °C pour ne jamais être négative. Exemples : 20,0 °C donne 600, 28,0 °C donne 680, 28,1 °C donne 681.

**Attention :** ce n'est pas le protocole d'un capteur réel. Un capteur réel a son propre protocole, décrit dans sa **fiche technique** (*datasheet*) : souvent une commande à lui envoyer d'abord, un temps d'attente, parfois une somme de contrôle sur les octets reçus. Le TP supprime tout cela pour que vous vous concentriez sur le bus, les erreurs et le relais.

## Décoder les 2 octets du capteur

Voici comment passer des 2 octets à la température, étape par étape. Soit `octets[0] = 0x02` et `octets[1] = 0xA8` :

1. **Assembler** : `brut = (octets[0] << 8) | octets[1]`. Décaler de 8 bits vers la gauche multiplie par 256 : `0x02 << 8` vaut 512 ; en y ajoutant `0xA8` (168) on obtient **680**.
2. **Retirer le décalage** : `dixiemes = brut - 400`, soit 280 dixièmes de degré.
3. **Comparer** : 280 dixièmes, c'est 28,0 °C.

Pour afficher : `dixiemes / 10.0f` donne 28.0 (`%.1f` dans le texte de `ESP_LOGI` affiche un chiffre après la virgule).

Pourquoi garder des **entiers** (des dixièmes) plutôt que des flottants ? Parce que la comparaison `dixiemes > 280` est **exacte** ; avec des flottants, un calcul comme `brut * 0,1 - 40` peut donner 28,000001 au lieu de 28,0, et le relais s'allumerait à tort.

!!Si vous inversez les deux octets, (octets[1] << 8) | octets[0], 0x02 0xA8 devient 43010 : le programme croirait qu'il fait plus de 4000 °C et allumerait le relais en permanence!!

## Les étapes du pilote I2C maître

ESP-IDF propose un pilote I2C « nouvelle génération » dans `driver/i2c_master.h`. Trois étapes pour parler à un capteur :

1. **Créer le bus** avec `i2c_new_master_bus` : on décrit les broches et le réglage dans un `i2c_master_bus_config_t`.
2. **Ajouter le capteur** avec `i2c_master_bus_add_device` : on donne son adresse dans un `i2c_device_config_t`.
3. **Lire** avec `i2c_master_receive` (ou `i2c_master_transmit_receive`).

```cpp
esp_err_t i2c_new_master_bus(const i2c_master_bus_config_t *bus_config,
                             i2c_master_bus_handle_t *ret_bus_handle);
esp_err_t i2c_master_bus_add_device(i2c_master_bus_handle_t bus_handle,
                                    const i2c_device_config_t *dev_config,
                                    i2c_master_dev_handle_t *ret_handle);
esp_err_t i2c_master_receive(i2c_master_dev_handle_t i2c_dev, uint8_t *read_buffer,
                             size_t read_size, int xfer_timeout_ms);
esp_err_t i2c_master_transmit_receive(i2c_master_dev_handle_t i2c_dev,
                                      const uint8_t *write_buffer, size_t write_size,
                                      uint8_t *read_buffer, size_t read_size,
                                      int xfer_timeout_ms);
```

| Fonction | Rôle | Retours cités par la documentation |
| --- | --- | --- |
| `i2c_new_master_bus` | crée le bus, la poignée est écrite dans `*ret_bus_handle` | `ESP_OK` ; `ESP_ERR_NOT_FOUND` quand il n'y a plus de port I2C libre |
| `i2c_master_bus_add_device` | ajoute un périphérique sur le bus | `ESP_OK` ; `ESP_ERR_INVALID_ARG` (par exemple bus mal initialisé) |
| `i2c_master_receive` | lit `read_size` octets du périphérique | `ESP_OK` ; `ESP_ERR_INVALID_ARG` ; `ESP_ERR_TIMEOUT` |
| `i2c_master_transmit_receive` | écrit des octets puis lit, sans signal d'arrêt entre les deux | `ESP_OK` ; `ESP_ERR_INVALID_ARG` ; `ESP_ERR_TIMEOUT` |

Le code des étapes 1 et 2, tel que le TP l'utilise :

```cpp
i2c_master_bus_config_t bus_cfg = {};                 // tout à zéro, sauf :
bus_cfg.i2c_port = I2C_NUM_0;                         // le premier contrôleur I2C
bus_cfg.sda_io_num = SDA_GPIO;                        // broche des données
bus_cfg.scl_io_num = SCL_GPIO;                        // broche de l'horloge
bus_cfg.clk_source = I2C_CLK_SRC_DEFAULT;             // horloge par défaut
bus_cfg.glitch_ignore_cnt = 7;                        // filtre anti-parasites (valeur de l'exemple de la doc)
bus_cfg.flags.enable_internal_pullup = 1;             // rappel interne (voir plus haut)
i2c_master_bus_handle_t bus;
ESP_ERROR_CHECK(i2c_new_master_bus(&bus_cfg, &bus));

i2c_device_config_t dev_cfg = {};
dev_cfg.dev_addr_length = I2C_ADDR_BIT_LEN_7;         // adresse sur 7 bits
dev_cfg.device_address = 0x44;                        // sans bit lecture/écriture
dev_cfg.scl_speed_hz = 100000;                        // 100 kHz
i2c_master_dev_handle_t capteur;
ESP_ERROR_CHECK(i2c_master_bus_add_device(bus, &dev_cfg, &capteur));
```

Les numéros de broches SDA et SCL (21 et 22 dans ce TP) sont **notre choix** : ce sont les paramètres `sda_io_num` et `scl_io_num` qui les fixent. La documentation précise aussi que la fréquence de l'horloge ne doit pas dépasser 400 kHz ; 100 kHz est une valeur prudente.

Et une lecture : on passe un tableau, que la fonction remplit, et la **durée maximale** d'attente `xfer_timeout_ms`, en millisecondes.

```cpp
uint8_t octets[2] = {0, 0};
esp_err_t err = i2c_master_receive(capteur, octets, sizeof octets, 100);   // attendre au plus 100 ms
if (err != ESP_OK) {
    // les octets ne sont pas fiables : ne pas s'en servir
}
```

D'après la documentation, `xfer_timeout_ms` est une durée d'attente en millisecondes, et **-1 signifie attendre indéfiniment** : à éviter, un capteur muet bloquerait alors le programme. Le code `ESP_ERR_TIMEOUT` est documenté comme « l'opération a pris plus de `xfer_timeout_ms`, parce que le bus est occupé ou à cause d'une panne matérielle ».

!!Mettre -1 comme xfer_timeout_ms fait attendre sans fin : si le capteur ne répond plus, le programme se fige!!

## esp_err_t, esp_err_to_name et ESP_ERROR_CHECK

Presque toutes les fonctions d'ESP-IDF renvoient un `esp_err_t` : un code entier, `ESP_OK` quand tout s'est bien passé, un autre code sinon. La fonction `esp_err_to_name(err)` renvoie le **nom** de ce code sous forme de texte (par exemple `ESP_ERR_TIMEOUT`) : pratique dans un journal.

```cpp
ESP_LOGE(TAG, "lecture échouée : %s", esp_err_to_name(err));
```

Deux façons de réagir à une erreur :

- **tester** le code avec `if (err != ESP_OK)` et décider quoi faire : continuer, réessayer, journaliser ;
- **ESP_ERROR_CHECK(...)** : si le code n'est pas `ESP_OK`, il affiche l'erreur (code, endroit, instruction) puis **arrête le programme**. Dans le simulateur, c'est un `abort` et le contrôle vous le dit.

Quand utiliser lequel ?

- **`ESP_ERROR_CHECK` pour les erreurs de démarrage** : configurer la broche, créer le bus, ajouter le capteur. Si cela échoue, c'est une erreur de montage ou de programmation, rien ne peut marcher ensuite, et s'arrêter tout de suite est la bonne réaction.
- **Un `if` pour les erreurs qui peuvent arriver en marche normale** : une lecture de capteur peut échouer à cause d'un fil ou d'un parasite. L'arrêt du programme pour une simple lecture ratée serait une catastrophe : le ventilateur resterait dans son dernier état, sans surveillance.

Pour le test, utilisez `err != ESP_OK` plutôt que de comparer à `ESP_ERR_TIMEOUT` : la documentation des fonctions de lecture ne détaille pas le code renvoyé pour chaque cause d'échec, donc le plus sûr est de traiter **toute** erreur de la même façon.

!!Ne mettez jamais ESP_ERROR_CHECK autour de la lecture du capteur dans la boucle : la première panne passagère arrêterait tout le programme!!

## Le relais sur la GPIO 5

Un **relais** est un interrupteur commandé par un signal faible : l'ESP32 met une broche à 0 ou à 1, le relais ferme ou ouvre un circuit plus puissant (ici le ventilateur). On le commande comme une LED, avec une broche **en sortie** (voir la leçon 1) :

```cpp
gpio_config_t relais_cfg = {};
relais_cfg.pin_bit_mask = 1ULL << GPIO_NUM_5;   // la broche 5
relais_cfg.mode = GPIO_MODE_OUTPUT;             // en sortie
ESP_ERROR_CHECK(gpio_config(&relais_cfg));
ESP_ERROR_CHECK(gpio_set_level(GPIO_NUM_5, 0)); // au départ : éteint
```

**Convention de ce TP :** le relais est **actif haut** : niveau **1 = relais allumé**, niveau **0 = relais éteint**. Certains modules relais fonctionnent à l'inverse (actifs bas) : sur du vrai matériel, lisez la fiche du module. Ici, la convention est fixée et le contrôle la suit.

**Ne relisez pas le relais pour connaître son état.** La documentation de `gpio_get_level` dit que, si la broche n'est pas configurée en entrée (ou en entrée et sortie), la valeur renvoyée est toujours 0. Gardez donc l'état dans une **variable** (`relais_allume`), c'est plus simple et plus sûr.

!!Un relais non configuré en sortie ne commande rien : appeler gpio_set_level sans gpio_config donne un ventilateur qui ne bouge pas, et le contrôle le signale!!

## Le seuil de 28,0 °C et l'hystérésis

La règle du TP : le relais est **allumé si et seulement si la dernière température valide est strictement supérieure à 28,0 °C**. À 28,0 °C **pile**, il est éteint ; à 28,1 °C, allumé. En dixièmes : `dixiemes > 280`. Écrire `>=` à la place de `>` allumerait le relais une mesure trop tôt.

Dans la vie réelle, une température qui **hésite** autour du seuil (27,9 puis 28,1 puis 27,9...) ferait claquer le relais sans arrêt, ce qui l'use. Le remède s'appelle l'**hystérésis** : deux seuils au lieu d'un, par exemple allumer au-dessus de 28,0 °C mais n'éteindre qu'**en dessous de 27,0 °C** ; entre les deux, on garde l'état. **Le TP n'en demande pas** : la température simulée monte régulièrement, un seul seuil suffit, et le contrôle attend la règle simple ci-dessus. Retenez l'idée pour les régulations de la suite du module.

## Garder le dernier état quand la lecture échoue

Quand `i2c_master_receive` échoue, on ne connaît **pas** la température : l'octet lu n'est pas fiable. Trois réactions possibles, une seule bonne :

- **couper le relais** : le ventilateur s'arrête peut-être alors qu'il fait chaud ;
- **allumer le relais** : on le fait tourner peut-être pour rien ;
- **ne rien changer** : on garde le **dernier état décidé sur une mesure valide**, et on réessaie au tour suivant. C'est ce que fait le TP.

Concrètement, dans la boucle : si la lecture réussit, on met à jour `relais_allume` et la broche ; si elle échoue, on **ne touche à rien**. Le relais reste donc allumé pendant toute la panne s'il l'était avant, et éteint s'il l'était. À la première lecture réussie après la panne, la décision est refaite avec la nouvelle température.

Le contrôle regarde le relais **juste avant chaque lecture suivante** et le compare à ce que donne la dernière température valide. Dans le scénario, la longue panne (de 47 s à 59 s) commence alors que le relais est **déjà allumé** (depuis 45 s) : couper le relais pendant la panne est donc visible. La courte panne (de 12 s à 17 s) tombe, elle, relais éteint : allumer le relais « par sécurité » est visible aussi.

!!Une lecture ratée ne veut pas dire température basse : ne coupez pas le relais pendant la panne, et ne l'allumez pas non plus!!

## Une erreur par panne, pas une par lecture

Il faut **dire** qu'une panne a lieu : sans journal, personne ne le saurait. Mais le programme lit toutes les 5 s : si chaque lecture ratée écrivait une ligne, une panne d'une heure écrirait **720 lignes** identiques, qui noieraient les autres messages. La règle du TP : **un seul journal d'erreur par panne**, au niveau `ESP_LOGE` (ou `ESP_LOGW`). Une **panne** est une suite de lectures ratées consécutives ; elle se termine à la première lecture réussie.

La technique : une variable booléenne, `en_panne`, qui retient que la panne en cours a déjà été signalée.

```cpp
bool en_panne = false;
// dans la boucle :
if (err == ESP_OK) {
    if (en_panne) {
        ESP_LOGI(TAG, "capteur de nouveau disponible");   // information, pas une erreur
        en_panne = false;                                  // on réarme pour la prochaine panne
    }
    /* ... décision ... */
} else if (!en_panne) {                                    // première lecture ratée de la panne
    ESP_LOGE(TAG, "lecture échouée : %s", esp_err_to_name(err));
    en_panne = true;
}
```

Lecture pas à pas pour une panne de 3 lectures : la 1re ratée (`en_panne` faux) écrit le journal et passe à vrai ; la 2e et la 3e (`en_panne` vrai) ne font rien ; la 4e réussit, écrit « de nouveau disponible » en niveau information et remet `en_panne` à faux. Si l'on **oublie** de remettre `en_panne` à faux, la panne suivante ne serait **jamais** signalée.

Le contrôle compte les journaux de niveau `E` et `W` pendant chaque panne : il en faut **exactement un**. Le message de récupération, en niveau `I`, ne compte pas.

!!Un ESP_LOGE à chaque lecture ratée est le piège classique : le journal se remplit, et l'erreur qui compte se perd dans le bruit!!

## Un exemple pas à pas : un capteur de lumière

Ce n'est pas le TP, c'est un cas voisin pour s'entraîner, avec un capteur **imaginaire**. Un capteur de lumière est à l'adresse **0x52** ; il renvoie 2 octets, poids fort d'abord, valant la lumière en **demi-lux** (le nombre lu divisé par 2 donne des lux). Une lampe, sur un relais actif haut, doit s'allumer quand il y a **moins de 100 lux**.

Lecture de 0x01 0x2C : `(0x01 << 8) | 0x2C` = 256 + 44 = **300**, soit 150 lux. 150 n'est pas inférieur à 100 : la lampe s'éteint. Lecture de 0x00 0x50 : 80 demi-lux, soit **40 lux** : la lampe s'allume. Lecture de 0x00 0xC8 : 200, soit exactement **100 lux** : pas strictement inférieur, la lampe reste éteinte (même logique que le 28,0 °C pile).

```cpp
static esp_err_t lire_lumiere(int *demi_lux) {
    uint8_t octets[2] = {0, 0};
    esp_err_t err = i2c_master_receive(lumiere, octets, sizeof octets, 100);
    if (err != ESP_OK) {
        return err;                        // on renvoie l'erreur, on n'arrête rien
    }
    *demi_lux = (octets[0] << 8) | octets[1];
    return ESP_OK;
}

// dans la boucle
int demi_lux = 0;
if (lire_lumiere(&demi_lux) == ESP_OK) {
    lampe_allumee = demi_lux < 200;        // moins de 100 lux
    ESP_ERROR_CHECK(gpio_set_level(GPIO_NUM_4, lampe_allumee ? 1 : 0));
}                                          // sinon : la lampe garde son état
```

Si la lecture échoue pendant que la lampe est allumée, elle reste allumée jusqu'à une nouvelle mesure valide ; le journal d'erreur se gère avec une variable `en_panne`, comme ci-dessus.

## Ce que le simulateur simplifie

- Le capteur est **simplifié** : 2 octets avec la formule du TP, sans commande à envoyer ni somme de contrôle.
- Un capteur qui ne répond pas, ou à une autre adresse, fait renvoyer `ESP_ERR_TIMEOUT` tout de suite, **sans** faire avancer le temps : le simulateur ne mesure pas `xfer_timeout_ms`. Sur une vraie puce, la documentation ne détaille pas le code renvoyé selon la cause ; c'est pourquoi on teste `err != ESP_OK`.
- Les résistances de rappel et la vitesse du bus n'ont aucun effet.
- Le temps n'avance que pendant `vTaskDelay`.
- Le relais est un simple niveau de broche : on observe les changements de niveau, il ne chauffe pas et ne s'use pas.

## Le programme du TP en un coup d'œil

```text
app_main :
  1. configurer la GPIO 5 en sortie, relais éteint       (gpio_config, gpio_set_level, ESP_ERROR_CHECK)
  2. créer le bus I2C et ajouter le capteur 0x44         (i2c_new_master_bus, i2c_master_bus_add_device)
  boucle sans fin, toutes les 5 s :
     3. lire_temperature : 2 octets, brut - 400 = dixièmes de °C, ou le code d'erreur
     4a. lecture réussie : relais_allume = dixiemes > 280, gpio_set_level, journal de la mesure
         (et si en_panne : « capteur de nouveau disponible », en_panne = false)
     4b. lecture ratée : si !en_panne, ESP_LOGE puis en_panne = true ; le relais ne bouge pas
     5. attendre 5000 ms
```

Le contrôle simule **80 secondes** : la température monte de 20,0 °C à 35,0 °C, avec 27,9 °C, puis 28,0 °C pile, puis 28,1 °C autour de 40 s ; une panne courte à 15 s ; une panne de 12 s de 47 s à 59 s, relais déjà allumé. Il vérifie : lectures de l'adresse 0x44 toutes les 5 s, broche 5 en sortie, relais correct après chaque lecture (état gardé pendant les pannes), un seul journal d'erreur par panne, programme jamais arrêté.

## Pièges

!!ESP_ERROR_CHECK arrête le programme : réservez-le au démarrage, jamais à une lecture de capteur qui peut échouer en marche normale!!

!!Le relais est actif haut dans ce TP : niveau 1 = allumé. Avec un niveau inversé, le ventilateur tourne quand il fait froid!!

!!Comparez en dixièmes de degré avec un entier (dixiemes > 280) : c'est exact, alors qu'un calcul en flottants peut tomber à côté pile sur le seuil!!

!!Remettez en_panne à faux à la première lecture réussie, sinon la panne suivante ne sera jamais signalée!!

## À retenir

- **I2C** : deux fils, SDA et SCL ; un maître, des périphériques à **adresse sur 7 bits** ; un **ACK** confirme, un **NACK** (ou le silence) veut dire que l'échange a échoué.
- Les trois étapes du pilote maître : `i2c_new_master_bus`, `i2c_master_bus_add_device`, `i2c_master_receive` (ou `i2c_master_transmit_receive`), avec un `xfer_timeout_ms` fini (**-1 attend sans fin**).
- Le capteur simulé renvoie 2 octets, poids fort d'abord : `brut = (octets[0] << 8) | octets[1]`, puis `dixiemes = brut - 400`. Un vrai capteur a son propre protocole (fiche technique).
- `esp_err_t` : `ESP_OK` ou un code ; `esp_err_to_name` en donne le nom. **`ESP_ERROR_CHECK` pour le démarrage, un `if` pour les lectures en marche.**
- Relais **actif haut** sur la GPIO 5, configurée en sortie ; l'état se garde dans une variable, pas avec `gpio_get_level`.
- Relais allumé **si et seulement si** la dernière température valide est **> 28,0 °C** ; sur une lecture ratée, on **garde le dernier état**.
- **Un seul journal d'erreur par panne** : une variable `en_panne`, réarmée à la première lecture réussie.
- Idée pour plus tard : l'**hystérésis**, deux seuils pour éviter que le relais claque.
