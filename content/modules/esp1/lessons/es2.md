# Bouton et anti-rebond

**Le problème concret :** un bouton poussoir est branché sur un ESP32. Chaque fois que l'on appuie dessus, une LED doit changer d'état **une seule fois**, même si le contact du bouton « tremble » pendant quelques millisecondes.

Cette leçon contient toute la théorie du TP. Lisez-la dans l'ordre : chaque section correspond à une étape, et les messages du contrôle vous disent laquelle relire. Elle suppose la leçon précédente (LED, `gpio_config`, `vTaskDelay`).

## Rappel : configurer la LED en sortie

La LED est sur la broche **GPIO 2**, exactement comme dans le TP précédent : une sortie, configurée une fois au début.

```cpp
gpio_config_t led = {};
led.pin_bit_mask = 1ULL << GPIO_NUM_2;
led.mode = GPIO_MODE_OUTPUT;
ESP_ERROR_CHECK(gpio_config(&led));
```

Ensuite, `gpio_set_level(GPIO_NUM_2, 1)` allume et `gpio_set_level(GPIO_NUM_2, 0)` éteint. Pour **inverser** la LED, on garde son état dans une variable `led_level` et on écrit `led_level = !led_level;` : `!0` vaut 1 et `!1` vaut 0.

## Configurer le bouton en entrée

Une broche en **entrée** ne commande rien : le programme **lit** la tension qu'elle reçoit et la traduit en niveau 0 (environ 0 V) ou 1 (environ 3,3 V). On la configure avec le même `gpio_config_t` que pour une sortie, en changeant le mode :

```cpp
gpio_config_t btn = {};
btn.pin_bit_mask = 1ULL << GPIO_NUM_4;
btn.mode = GPIO_MODE_INPUT;               // une entrée
btn.pull_up_en = GPIO_PULLUP_ENABLE;      // avec la résistance de rappel (section suivante)
ESP_ERROR_CHECK(gpio_config(&btn));
```

Les champs de `gpio_config_t`, d'après la documentation d'ESP-IDF : `pin_bit_mask` (« chaque bit correspond à une broche »), `mode` (entrée ou sortie), `pull_up_en` (résistance de rappel vers le haut), `pull_down_en` (vers le bas) et `intr_type` (type d'interruption). Avec `= {}`, tous les champs sont à zéro : pas de pull-up, pas de pull-down, pas d'interruption.

On lit ensuite le niveau avec :

- `int gpio_get_level(gpio_num_t gpio_num)` : renvoie 0 ou 1, le niveau de la broche **à l'instant de l'appel**. La documentation précise : si la broche n'est pas configurée en entrée (ou en entrée et sortie), la valeur renvoyée est toujours 0. Pas de code d'erreur : c'est un `int`, pas un `esp_err_t`.

```cpp
int niveau = gpio_get_level(GPIO_NUM_4);   // 0 ou 1
```

Une **interruption** est un mécanisme qui réveille le programme au moment exact où une broche change. ESP-IDF en propose, mais ce TP n'en utilise **pas** : nous lirons la broche nous-mêmes, régulièrement.

!!Oublier de configurer la broche en entrée : gpio_get_level renvoie toujours 0, et le bouton semble enfoncé en permanence!!

## La résistance de pull-up et la logique inversée

Un bouton poussoir est un simple interrupteur : quand on appuie, il relie la broche à la masse (0 V). Quand on **n'appuie pas**, il ne relie rien du tout : la broche est alors « en l'air » (on dit qu'elle **flotte**). Une broche qui flotte capte les parasites et peut lire 0 ou 1 au hasard.

La solution est une **résistance de pull-up** (« tirer vers le haut ») : une résistance entre la broche et le 3,3 V. Au repos, elle tire doucement la broche vers 3,3 V, donc la lecture est **1**. Quand on appuie, le bouton relie la broche à la masse, et ce contact l'emporte sur la résistance : la lecture passe à **0**.

Conséquence, à bien retenir, la **logique est inversée** :

| État du bouton | Niveau lu |
| --- | --- |
| relâché | 1 |
| enfoncé | 0 |

Autrement dit : **appui = 0**, repos = 1. C'est l'inverse de ce que l'on imagine d'instinct.

Les ESP32 ont de telles résistances **à l'intérieur** de la puce : il suffit de les activer avec `btn.pull_up_en = GPIO_PULLUP_ENABLE`, sans rien ajouter sur la carte. Elles n'existent pas sur toutes les broches : d'après la documentation, sur l'ESP32 seules les broches qui acceptent à la fois l'entrée et la sortie en ont, **les broches GPIO 34 à 39 (entrée seule) n'en ont pas** ; pour elles, il faudrait une résistance externe. La documentation de cette page ne donne pas la valeur de ces résistances internes, et ce TP n'en a pas besoin.

Dans le simulateur de ce TP, une entrée dont le pull-up n'est pas activé lit **0 en permanence** (le simulateur ne modélise pas les parasites d'une broche qui flotte). Le contrôle vous le dit : « entrée sans pull-up ».

!!Pull-up oublié : le programme lit 0 tout le temps et croit que le bouton est toujours enfoncé!!

!!Logique inversée : tester `if (niveau == 1)` pour détecter un appui est l'erreur classique, un appui vaut 0!!

## Les rebonds mécaniques

Un bouton est fait de deux lames métalliques qui se touchent. Au moment du contact, elles **rebondissent** l'une sur l'autre, comme une balle : pendant un court instant, le contact s'établit, se coupe, se rétablit, se coupe encore, avant de se stabiliser. Pour le processeur, qui lit très vite, **un seul appui ressemble à plusieurs appuis rapides**. Ces rebonds durent souvent quelques millisecondes à quelques dizaines de millisecondes selon le bouton.

Dans le TP, un appui est simulé ainsi (un niveau toutes les 10 ms) :

```
niveau 1 (repos)  ...  0  1  0  1  0  0  0  0  0  0  0  0  0  1 ...
                       |-- rebonds --||-- bouton tenu --|  relâché
                       (40 ms)           (80 ms)
```

Un programme naïf qui inverse la LED à chaque lecture de 0 compterait plusieurs appuis par appui réel : la LED clignote n'importe comment. Il faut **filtrer les rebonds**. Dans la vraie vie, un rebond peut aussi durer moins longtemps que la période de lecture et passer inaperçu ; le simulateur lit toutes les 10 ms (un tick), donc les rebonds du TP sont espacés de 10 ms pour que votre programme les voie.

!!Sans anti-rebond, un seul appui fait changer la LED plusieurs fois : le contrôle compte plus de trois changements!!

## Sonder le bouton à intervalle régulier

Comme on n'utilise pas d'interruption, le programme **sonde** le bouton (en anglais *polling*) : à intervalle régulier, il lit la broche, décide, puis dort avec `vTaskDelay`. C'est la boucle de la leçon précédente, avec une lecture au lieu d'une écriture.

```cpp
for (;;) {
    int raw = gpio_get_level(GPIO_NUM_4);   // lire
    // ... décider ...
    vTaskDelay(pdMS_TO_TICKS(10));          // dormir 10 ms
}
```

**Comment choisir la période ?** Elle doit être **plus courte que le plus court des appuis à ne pas rater**. Si l'appui dure 80 ms et que l'on lit toutes les 500 ms, la lecture tombe presque toujours en dehors de l'appui : il est **manqué**. Une période de 10 ms voit un appui de 80 ms environ 8 fois. Mais plus la période est courte, plus le processeur travaille pour rien : 10 ms est un bon compromis pour un bouton (c'est aussi le plus petit délai possible ici, un tick). Règle pratique : période au plus égale au tiers du plus court appui.

On sonde à période **fixe** : le temps écoulé entre deux lectures vaut la période. C'est ce qui permet de mesurer une durée en additionnant les périodes.

!!Sondage trop lent (par exemple toutes les 500 ms) : un appui de 80 ms passe entre deux lectures et n'est jamais vu!!

## L'anti-rebond par durée de stabilité

Principe : **n'accepter un niveau que s'il est resté identique assez longtemps**. Les rebonds changent de niveau toutes les 10 ms ; un vrai appui reste à 0 pendant au moins 80 ms. En exigeant par exemple **30 ms** de stabilité, les rebonds sont ignorés et l'appui est accepté.

On a besoin de trois variables :

- `stable` : le niveau **accepté** du bouton (1 = relâché au départ) ;
- `candidate` : le dernier niveau **lu** ;
- `since_ms` : depuis combien de millisecondes `candidate` n'a pas changé.

À chaque lecture `raw` :

```cpp
if (raw != candidate) {      // le niveau a bougé : on repart de zéro
    candidate = raw;
    since_ms = 0;
} else {                     // même niveau : on cumule la durée
    since_ms += POLL_MS;
}
if (candidate != stable && since_ms >= STABLE_MS) {
    stable = candidate;      // le nouveau niveau est accepté
    // ici, le bouton vient vraiment de changer d'état
}
```

**Premier front stable** : c'est l'instant où le signal prend son nouveau niveau et ne le quitte plus. Dans l'exemple du TP, c'est le dernier 0 des rebonds, 40 ms après le premier contact. Avec 30 ms de stabilité et une lecture toutes les 10 ms, l'appui est accepté environ 30 ms après ce front. Plus la durée de stabilité est longue, plus la réaction est lente : exiger 2 secondes de stabilité ferait **rater** un appui de 80 ms, qui ne dure jamais 2 secondes. Le contrôle exige que la LED change **au plus 60 ms après le premier front stable**.

!!Durée de stabilité plus longue que l'appui : l'appui n'est jamais accepté, la LED ne bouge pas!!

## Front ou niveau : réagir une seule fois

Quand le bouton est tenu enfoncé 80 ms, `raw` vaut 0 pendant huit lectures. Réagir **au niveau** (« tant que c'est 0, inverser la LED ») inverserait la LED à chaque lecture. On veut réagir au **front** : le **changement** de niveau, une seule fois.

- Un **front descendant** est le passage de 1 à 0 : c'est l'**appui** (logique inversée).
- Un **front montant** est le passage de 0 à 1 : c'est le **relâchement**.

Dans l'algorithme précédent, `stable` change exactement une fois par front accepté. Il suffit de n'agir que lorsque le nouveau niveau accepté est 0 :

```cpp
stable = candidate;
if (stable == 0) {           // front descendant : appui
    led_level = !led_level;
    gpio_set_level(GPIO_NUM_2, led_level);
}
```

Si l'on agissait aussi quand `stable` redevient 1, la LED changerait à l'appui **et** au relâchement : deux changements par appui, et le contrôle le signale.

## Exemple complet qui n'est pas le TP

Voici un programme voisin : un bouton sur la **broche 5** inverse une lampe sur la **broche 18** à chaque **relâchement** (au lieu de l'appui), avec une stabilité de 50 ms et une lecture toutes les 10 ms.

```cpp
#include "freertos/FreeRTOS.h"
#include "freertos/task.h"
#include "driver/gpio.h"
#include "esp_log.h"

static const char *TAG = "lampe";

extern "C" void app_main(void) {
    gpio_config_t lampe = {};
    lampe.pin_bit_mask = 1ULL << GPIO_NUM_18;
    lampe.mode = GPIO_MODE_OUTPUT;
    ESP_ERROR_CHECK(gpio_config(&lampe));

    gpio_config_t poussoir = {};
    poussoir.pin_bit_mask = 1ULL << GPIO_NUM_5;
    poussoir.mode = GPIO_MODE_INPUT;
    poussoir.pull_up_en = GPIO_PULLUP_ENABLE;
    ESP_ERROR_CHECK(gpio_config(&poussoir));

    int etat_lampe = 0;
    int accepte = 1;       // niveau accepté du poussoir
    int lu = 1;            // dernier niveau lu
    int duree = 0;         // durée sans changement, en ms
    for (;;) {
        int niveau = gpio_get_level(GPIO_NUM_5);
        if (niveau != lu) { lu = niveau; duree = 0; } else { duree += 10; }
        if (lu != accepte && duree >= 50) {
            accepte = lu;
            if (accepte == 1) {                       // front montant : relâchement
                etat_lampe = !etat_lampe;
                gpio_set_level(GPIO_NUM_18, etat_lampe);
                ESP_LOGI(TAG, "lampe %s", etat_lampe ? "allumée" : "éteinte");
            }
        }
        vTaskDelay(pdMS_TO_TICKS(10));
    }
}
```

Lecture : configuration unique avant la boucle ; dans la boucle, lire, mettre à jour la durée de stabilité, accepter le niveau s'il est stable, agir sur **un** type de front, dormir. Dans le TP, vous réagissez à l'**appui** (niveau 0) avec la broche 4, la LED de la broche 2 et 30 ms de stabilité.

## Pièges

!!Le bouton au repos lit 1 et enfoncé lit 0 : tester niveau == 1 pour détecter l'appui est le piège classique de la logique inversée!!

Autres erreurs fréquentes :

- Choisir une période de sondage plus longue que l'appui : appuis manqués.
- Oublier de remettre `since_ms` à zéro quand le niveau change : la durée de stabilité cumule des morceaux séparés par des rebonds.
- Écrire `since_ms += POLL_MS` sans `vTaskDelay(pdMS_TO_TICKS(POLL_MS))` dans la boucle : la durée calculée n'a plus de rapport avec le temps réel.
- Utiliser une broche de 34 à 39 pour un bouton avec pull-up interne : ces broches n'en ont pas.
- Lire l'état de la LED avec `gpio_get_level` sur une broche de sortie : ne le faites pas, gardez l'état dans une variable (`led_level`), c'est plus sûr.

## À retenir

**À retenir :** une entrée se configure avec `mode = GPIO_MODE_INPUT` ; `pull_up_en = GPIO_PULLUP_ENABLE` active la résistance de rappel interne (absente sur les broches 34 à 39), qui fait lire 1 au repos : la logique est **inversée**, appui = 0 ; les contacts rebondissent, donc on n'accepte un niveau que s'il est **stable** assez longtemps (compteur `since_ms` remis à zéro à chaque changement) ; on sonde à période fixe, plus courte que le plus court des appuis (ici 10 ms) ; on réagit au **front** (le changement accepté vers 0), pas au niveau, pour un seul changement de la LED par appui.
