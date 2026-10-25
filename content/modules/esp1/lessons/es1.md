# Premier programme : LED et journaux

**Le problème concret :** faire clignoter une LED branchée sur un ESP32, et écrire dans un journal ce que le programme est en train de faire, sans jamais bloquer le processeur.

Cette leçon contient toute la théorie du TP. Lisez-la dans l'ordre : chaque section correspond à une étape du TP, et les messages du contrôle vous disent laquelle relire.

## Qu'est-ce qu'un ESP32 ?

Un **ESP32** est un petit ordinateur sur une puce de quelques euros, fabriqué par Espressif. Il a un processeur, de la mémoire, du Wi-Fi et du Bluetooth, et surtout des **broches** (appelées GPIO, pour General Purpose Input/Output). Une broche est un fil de cuivre que le programme sait mettre à 0 volt (niveau **0**, bas) ou à 3,3 volts (niveau **1**, haut). Avec une LED et une résistance branchées sur une broche, niveau 1 allume la LED et niveau 0 l'éteint. Avec un relais, on commande une pompe ou une lumière. C'est la base de toute la domotique.

Un ESP32 n'a pas de système d'exploitation comme un ordinateur : il n'y a ni fenêtre, ni clavier, ni fichiers. Votre programme est le seul maître à bord, et c'est lui qui démarre quand on branche la carte.

Les cartes de développement ont souvent une LED déjà soudée sur la broche **GPIO 2**. C'est celle du TP.

Le programme s'écrit avec **ESP-IDF**, le framework officiel d'Espressif, en C++. Ce que vous écrivez ici est du vrai code ESP-IDF : il fonctionne sur une vraie carte. Dans l'application, il tourne sur un simulateur qui imite ESP-IDF avec une horloge virtuelle (10 secondes simulées s'exécutent presque instantanément).

## Le point d'entrée : app_main

Sur un ordinateur, un programme C++ commence à `main`. Sous ESP-IDF, c'est le système qui démarre, puis qui appelle **votre** fonction `app_main`. Elle s'écrit toujours ainsi :

```cpp
extern "C" void app_main(void) {
    // votre code ici
}
```

`extern "C"` dit au compilateur C++ de ne pas changer le nom de la fonction : sans lui, le système ne la trouve pas. `void app_main(void)` ne prend rien et ne renvoie rien.

Un programme embarqué ne doit en général **jamais se terminer** : une machine de domotique tourne tant qu'elle est alimentée. On écrit donc une boucle infinie `for (;;) { ... }` dans `app_main`, et tout le travail se fait dans cette boucle.

Il faut aussi inclure les en-têtes des fonctions que l'on utilise. Pour ce TP, ce sont :

```cpp
#include "freertos/FreeRTOS.h"   // types et temps FreeRTOS (toujours avant task.h)
#include "freertos/task.h"       // vTaskDelay
#include "driver/gpio.h"         // gpio_config, gpio_set_level
#include "esp_log.h"             // ESP_LOGI
```

## Écrire dans le journal avec ESP_LOGI

Sur un ESP32, pas d'écran : pour savoir ce que fait le programme, il écrit des messages, les **journaux** (logs), envoyés par le câble USB vers l'ordinateur. On n'utilise pas `printf` : ESP-IDF fournit des macros qui ajoutent l'heure, le niveau et une étiquette.

```cpp
static const char *TAG = "monprog";
ESP_LOGI(TAG, "la valeur est %d", 42);
```

`static const char *TAG = "monprog";` se place en haut du fichier : c'est une constante texte, visible seulement dans ce fichier (`static`), que l'on réutilise dans tous les `ESP_LOGx`. C'est l'habitude de tous les programmes ESP-IDF : copiez-la telle quelle en changeant le texte.

Le premier argument est le **tag** : une courte étiquette qui dit d'où vient le message (ici `monprog`). Le deuxième est un **format** à la manière de `printf` : `%d` pour un entier, `%s` pour un texte, `%f` pour un nombre à virgule. Les arguments suivants remplissent ces emplacements.

Il y a un niveau par gravité, avec une macro chacune :

| Macro | Niveau | Usage |
| --- | --- | --- |
| `ESP_LOGE` | erreur | quelque chose a échoué |
| `ESP_LOGW` | avertissement | situation anormale mais non fatale |
| `ESP_LOGI` | information | le fonctionnement normal |

`ESP_LOGI` est celle que l'on utilise pour raconter ce que fait le programme.

Mini-référence :

- `ESP_LOGI(tag, format, ...)` : macro, sans valeur de retour. `tag` est un texte (`const char *`), `format` un format `printf`. Pas d'erreur possible à l'exécution, mais un format qui ne correspond pas aux arguments (`%d` avec un texte) est un bug que le compilateur signale.
- `ESP_LOGW` et `ESP_LOGE` ont la même forme.

## Configurer une broche avec gpio_config

Avant d'écrire sur une broche, on dit au processeur ce qu'elle fait : elle peut être une **sortie** (le programme impose le niveau, comme pour une LED) ou une **entrée** (le programme lit le niveau, comme pour un bouton). C'est la configuration, avec la structure `gpio_config_t` :

```cpp
gpio_config_t io = {};                      // tous les champs à zéro
io.pin_bit_mask = 1ULL << GPIO_NUM_4;       // quelles broches configurer
io.mode = GPIO_MODE_OUTPUT;                 // en sortie
ESP_ERROR_CHECK(gpio_config(&io));          // appliquer
```

Les champs de `gpio_config_t` que l'on utilise :

- `pin_bit_mask` : un nombre de 64 bits où **chaque bit représente une broche**. Pour la broche 4, on veut le bit numéro 4 à 1 : `1ULL << 4`, soit `1ULL << GPIO_NUM_4`. `1ULL` est le nombre 1 écrit sur 64 bits (le `ULL` est obligatoire : sans lui, le décalage déborde pour les grandes broches). On peut configurer plusieurs broches à la fois en additionnant leurs bits avec `|`.
- `mode` : `GPIO_MODE_OUTPUT` pour une sortie, `GPIO_MODE_INPUT` pour une entrée.
- `pull_up_en`, `pull_down_en`, `intr_type` : résistances internes et interruptions. Avec `= {}`, ils restent à zéro (désactivés), ce qui convient ici.

Mini-référence :

- `esp_err_t gpio_config(const gpio_config_t *pGPIOConfig)` : applique la configuration. Renvoie `ESP_OK` si tout va bien, `ESP_ERR_INVALID_ARG` si la configuration est invalide (masque vide ou numéro de broche impossible, mode inconnu).

Presque toutes les fonctions ESP-IDF renvoient un `esp_err_t`, un code d'erreur : `ESP_OK` (zéro) veut dire « réussi », tout autre code est un échec. La macro `ESP_ERROR_CHECK(appel)` vérifie ce code : si l'appel échoue, elle écrit un message d'erreur dans le journal et **arrête le programme**. C'est la bonne réaction au démarrage : un programme dont la LED n'est pas configurée ne sert à rien, autant le dire tout de suite.

!!Oublier de configurer la broche en sortie : le programme compile et semble marcher, mais sur une vraie carte la LED ne s'allume pas!!

## Allumer et éteindre avec gpio_set_level

Une fois la broche en sortie, on impose son niveau :

```cpp
gpio_set_level(GPIO_NUM_4, 1);   // niveau haut : 3,3 V
gpio_set_level(GPIO_NUM_4, 0);   // niveau bas : 0 V
```

Mini-référence :

- `esp_err_t gpio_set_level(gpio_num_t gpio_num, uint32_t level)` : `gpio_num` est la broche (`GPIO_NUM_2`, `GPIO_NUM_4`...), `level` vaut 0 ou 1 (toute autre valeur non nulle compte comme 1). Renvoie `ESP_OK`, ou `ESP_ERR_INVALID_ARG` si la broche n'existe pas ou ne peut pas être une sortie (les broches 34 à 39 sont en entrée seule sur l'ESP32).

Pour **faire clignoter**, il faut alterner entre 1 et 0. Le plus simple est une variable `level` que l'on inverse à chaque tour de boucle avec `!` (« non » logique) : `!0` vaut 1 et `!1` vaut 0.

```cpp
int level = 0;
level = !level;   // devient 1
level = !level;   // redevient 0
```

!!Ne confondez pas la broche et le niveau : GPIO_NUM_2 désigne la broche, l'argument suivant (0 ou 1) désigne l'état imposé!!

## Attendre sans bloquer avec vTaskDelay

Si on allume la LED puis qu'on l'éteint tout de suite, l'œil ne voit rien : le processeur travaille des millions de fois plus vite. Il faut **attendre**. La tentation est d'écrire une boucle vide qui compte jusqu'à un grand nombre. C'est le pire choix : pendant ce temps, le processeur tourne à fond pour ne rien faire, et personne d'autre ne peut travailler.

Sous ESP-IDF, le système en dessous de votre programme est **FreeRTOS**. Il fait tourner plusieurs « tâches » à tour de rôle, et `app_main` en est une. La bonne façon d'attendre est de **rendre la main** :

```cpp
vTaskDelay(pdMS_TO_TICKS(500));   // dormir 500 millisecondes
```

Pendant ce sommeil, FreeRTOS fait travailler les autres tâches (Wi-Fi, capteurs...) ou met le processeur au repos pour économiser du courant.

`vTaskDelay` compte en **ticks** : un tick est le battement d'horloge du système, 10 ms ici (100 ticks par seconde). Pour ne pas calculer à la main, la macro `pdMS_TO_TICKS(500)` convertit 500 millisecondes en ticks (50).

Mini-référence :

- `void vTaskDelay(const TickType_t xTicksToDelay)` : endort la tâche appelante pendant ce nombre de ticks. Ne renvoie rien, pas d'erreur possible.
- `pdMS_TO_TICKS(ms)` : macro qui convertit des millisecondes en ticks. Attention, elle arrondit vers le bas : `pdMS_TO_TICKS(5)` vaut 0 pour un tick de 10 ms, donc aucune attente.

Il y a une seconde raison de ne jamais boucler sans dormir : le **watchdog** (« chien de garde »). C'est un minuteur matériel qui surveille que chaque tâche rend la main de temps en temps. Si une tâche garde le processeur trop longtemps, le chien de garde conclut que le programme est bloqué et **le signale** : par défaut, un avertissement et la pile d'appels apparaissent dans le journal et le programme continue ; la carte ne redémarre que si la configuration (`CONFIG_ESP_TASK_WDT_PANIC`) le demande. Pendant ce temps, les autres tâches (Wi-Fi, tâche d'inactivité IDLE) n'ont plus la main. Une boucle qui contient un `vTaskDelay` n'a jamais ce problème. Le contrôle de ce TP signale d'ailleurs une tâche qui ne rend jamais la main.

!!Une boucle infinie sans vTaskDelay prive les autres tâches du processeur et déclenche l'alerte du watchdog (avertissement dans le journal, redémarrage si la configuration le demande)!!

## La boucle infinie

On assemble le tout dans `for (;;)` : à chaque tour, on change l'état, on journalise, on attend. Voici un exemple complet qui **n'est pas** le TP : il compte les secondes dans le journal et alterne un ventilateur branché sur la broche 4, toutes les secondes.

```cpp
#include "freertos/FreeRTOS.h"
#include "freertos/task.h"
#include "driver/gpio.h"
#include "esp_log.h"

static const char *TAG = "ventilo";

extern "C" void app_main(void) {
    gpio_config_t io = {};
    io.pin_bit_mask = 1ULL << GPIO_NUM_4;
    io.mode = GPIO_MODE_OUTPUT;
    ESP_ERROR_CHECK(gpio_config(&io));

    int tour = 0;
    for (;;) {
        gpio_set_level(GPIO_NUM_4, tour % 2);        // 0, 1, 0, 1...
        ESP_LOGI(TAG, "tour %d, niveau %d", tour, tour % 2);
        tour = tour + 1;
        vTaskDelay(pdMS_TO_TICKS(1000));             // une seconde
    }
}
```

Lecture : on configure la broche une fois, avant la boucle (inutile de répéter à chaque tour). Dans la boucle : agir, journaliser, attendre. `tour % 2` est le reste de la division par 2 : 0 pour les tours pairs, 1 pour les impairs.

Dans le TP, vous faites la même chose avec la broche 2, une période de 500 ms, et une variable `level` inversée à chaque tour au lieu de `tour % 2`.

## Pièges

!!Le tag doit rester le même partout : ici « blink ». Le premier argument de ESP_LOGI est le tag, pas le message!!

!!ESP_LOGE n'est pas ESP_LOGI : un journal d'erreur pour un fonctionnement normal fausse la lecture des journaux et le contrôle ne le compte pas!!

Autres erreurs fréquentes :

- Écrire `main` au lieu de `extern "C" void app_main(void)` : le système ne trouve pas le point d'entrée.
- Écrire `1 << GPIO_NUM_2` au lieu de `1ULL << GPIO_NUM_2` pour le masque : fonctionne pour la broche 2 mais déborde pour les broches 32 et plus.
- Mettre `vTaskDelay(500)` au lieu de `vTaskDelay(pdMS_TO_TICKS(500))` : 500 ticks, soit 5 secondes ici.
- Journaliser seulement l'allumage et oublier l'extinction : il faut un journal par changement.

## À retenir

**À retenir :** le point d'entrée est `extern "C" void app_main(void)` et ne se termine jamais ; `ESP_LOGI(TAG, format, ...)` écrit un journal d'information ; une broche se configure une fois avec `gpio_config` (`pin_bit_mask = 1ULL << GPIO_NUM_x`, `mode = GPIO_MODE_OUTPUT`), dans `ESP_ERROR_CHECK` ; `gpio_set_level(broche, 0 ou 1)` éteint ou allume ; on attend avec `vTaskDelay(pdMS_TO_TICKS(ms))` et jamais avec une boucle vide, sous peine de priver les autres tâches du processeur et de déclencher l'alerte du watchdog.
