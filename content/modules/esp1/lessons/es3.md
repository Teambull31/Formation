# Tâches FreeRTOS et files

**Le problème concret :** le programme doit surveiller un bouton toutes les 10 ms **et** commander une LED, sans que l'une des deux activités bloque l'autre. On découpe le travail en deux **tâches** qui se parlent par une **file**.

Cette leçon contient toute la théorie du TP. Lisez-la dans l'ordre : les messages du contrôle vous disent quelle section relire. Elle suppose les deux leçons précédentes (LED, `vTaskDelay`, bouton, anti-rebond).

## Qu'est-ce qu'une tâche

Jusqu'ici, tout votre programme tenait dans `app_main`, avec une seule boucle `for (;;)`. Dès que l'on veut faire **plusieurs choses à la fois** (lire un bouton, commander une LED, plus tard parler au Wi-Fi), une seule boucle devient vite un sac de nœuds.

Sous ESP-IDF, le système **FreeRTOS** sait faire tourner plusieurs **tâches**. Une tâche, c'est :

- une **fonction C** de la forme `void ma_tache(void *arg)`, qui contient en général une boucle infinie ;
- avec **sa propre pile** (la zone de mémoire où vivent ses variables locales, voir plus loin) ;
- que FreeRTOS fait avancer à tour de rôle avec les autres tâches.

`app_main` est elle-même une tâche, créée par ESP-IDF au démarrage. D'après la documentation, une tâche est toujours dans l'un de ces états : **en cours d'exécution** (Running), **prête** (Ready, elle attend son tour), **bloquée** (Blocked, elle attend un événement ou la fin d'un délai) ou **suspendue** (Suspended). Retenez surtout « bloquée » : c'est l'état d'une tâche qui dort dans `vTaskDelay` ou qui attend un message.

## Bloquer plutôt que sonder en boucle

Imaginez la tâche qui commande la LED. Elle doit réagir à chaque appui. Deux façons de l'écrire :

1. **Attente active** : elle demande sans arrêt « y a-t-il un appui ? », dans une boucle qui ne dort jamais. Elle occupe le processeur pour ne rien faire, et les tâches moins prioritaires qu'elle n'ont plus jamais la main (c'est la boucle vide de la leçon 1).
2. **Blocage** : elle dit à FreeRTOS « réveille-moi quand un appui arrive », puis elle dort. La documentation est claire : une tâche à l'état bloqué **ne consomme aucun temps processeur**. FreeRTOS la réveille au bon moment.

La deuxième façon est toujours préférable. `vTaskDelay` bloque la tâche **pendant une durée** ; une **file** (section suivante) permet de bloquer une tâche **jusqu'à l'arrivée d'un message**. C'est exactement ce qu'il faut à la tâche de la LED : dormir jusqu'au prochain appui.

La tâche du bouton, elle, n'a pas le choix : sans interruption, il faut lire la broche régulièrement. Mais elle **dort** 10 ms entre deux lectures avec `vTaskDelay`, ce qui est un blocage, pas une attente active.

## Créer une tâche avec xTaskCreate

On crée une tâche avec `xTaskCreate` :

```cpp
BaseType_t xTaskCreate(TaskFunction_t pxTaskCode, const char *const pcName,
                       const configSTACK_DEPTH_TYPE usStackDepth, void *const pvParameters,
                       UBaseType_t uxPriority, TaskHandle_t *const pxCreatedTask);
```

Les six paramètres, dans l'ordre :

| Paramètre | Rôle | Dans le TP |
| --- | --- | --- |
| `pxTaskCode` | la fonction de la tâche, `void f(void *arg)` | `tache_led` |
| `pcName` | un nom lisible, pour le débogage ; par défaut 15 caractères visibles au plus (`configMAX_TASK_NAME_LEN` vaut 16, en comptant le zéro final), un nom plus long est tronqué | `"led"` |
| `usStackDepth` | la taille de la pile, **en octets** sous ESP-IDF | `4096` |
| `pvParameters` | un pointeur passé tel quel à la fonction (son `arg`) | `NULL` |
| `uxPriority` | la priorité : plus le nombre est grand, plus la tâche est prioritaire | `5` |
| `pxCreatedTask` | où ranger la « poignée » de la tâche, ou `NULL` si on n'en a pas besoin | `NULL` |

**Valeur de retour :** `pdPASS` si la tâche a été créée, sinon un code d'erreur ; sous ESP-IDF, l'échec renvoie `errCOULD_NOT_ALLOCATE_REQUIRED_MEMORY` (pas assez de mémoire pour la pile ou la structure de la tâche). On vérifie donc :

```cpp
if (xTaskCreate(tache_led, "led", 4096, NULL, 5, NULL) != pdPASS) {
    ESP_LOGE(TAG, "tâche led non créée");
}
```

**Une fonction de tâche ne doit jamais se terminer.** La documentation le répète : les tâches sont écrites comme une boucle infinie et ne doivent jamais faire `return`. Une tâche qui a fini son travail se supprime elle-même avec `vTaskDelete(NULL)` (`NULL` désigne la tâche qui appelle). Si une fonction de tâche se termine quand même, ESP-IDF, lorsque l'option `CONFIG_FREERTOS_TASK_FUNCTION_WRAPPER` est active, écrit dans le journal « FreeRTOS Task "led" should not return, Aborting now! » et arrête le programme ; le simulateur fait la même chose.

**Exception : `app_main` a le droit de se terminer.** La documentation d'ESP-IDF l'autorise explicitement : la tâche principale est alors nettoyée et les autres tâches continuent normalement. On peut donc écrire un `app_main` qui configure les broches, crée les tâches, puis se termine. Attention : ses variables locales disparaissent avec elle, donc tout ce que les tâches partagent (la file) est déclaré **en dehors** des fonctions, avec `static`.

**Les priorités.** Sur la vraie puce, l'ordonnanceur de FreeRTOS fait toujours tourner la tâche prête la plus prioritaire, et il peut interrompre une tâche dès qu'une tâche plus prioritaire devient prête (préemption). `app_main` tourne à une priorité fixe, juste au-dessus du minimum ; une tâche de priorité 5 créée par `app_main` peut donc démarrer **avant même** la ligne suivante de `app_main`. Conséquence pratique : créez la file **avant** les tâches qui s'en servent.

!!Le simulateur de ce TP ignore les priorités : il fait tourner les tâches chacune à son tour, et ne change de tâche que lorsque la tâche courante se bloque (vTaskDelay, attente sur une file). Le TP ne dépend pas des priorités, mais sur la vraie puce elles comptent!!

Le simulateur accepte au plus 4 tâches en plus de `app_main` ; ce TP en utilise 2.

## La taille de la pile

Chaque tâche a sa **pile** : la zone de mémoire où sont rangées ses variables locales, les adresses de retour des fonctions qu'elle appelle et leurs paramètres. Plus la tâche appelle de fonctions imbriquées et plus elle a de variables locales, plus il lui faut de pile. Une fonction comme `ESP_LOGI`, qui met en forme du texte, a elle aussi besoin de place sur la pile.

**Unité :** sous ESP-IDF, la taille passée à `xTaskCreate` est en **octets**. La documentation insiste : c'est différent du FreeRTOS d'origine (dit « vanilla »), où elle est comptée en **mots**. Un exemple trouvé sur Internet pour un autre microcontrôleur peut donc indiquer une valeur quatre fois trop petite pour l'ESP32 (sur un processeur 32 bits comme celui de l'ESP32, un mot fait 4 octets).

Si la pile est trop petite, elle **déborde** : la tâche écrit dans la mémoire voisine et corrompt d'autres données. ESP-IDF range le débordement de pile parmi les erreurs fatales et propose des mécanismes de détection (options `CONFIG_FREERTOS_CHECK_STACKOVERFLOW` et `CONFIG_FREERTOS_WATCHPOINT_END_OF_STACK`), mais la documentation prévient que le mécanisme par point d'arrêt (watchpoint) ne détecte pas tous les débordements. Mieux vaut prévoir large dès le départ.

Le simulateur, lui, ne modélise pas la pile : une tâche créée avec 256 octets y tourne sans problème. C'est pourquoi **le contrôle du TP exige au moins 2048 octets** pour chaque tâche créée ; la solution en donne 4096.

!!Pile de 256 octets, ou valeur copiée d'un exemple compté en mots : la pile de la vraie puce risque de déborder, le contrôle refuse toute pile de moins de 2048 octets!!

## Les files : xQueueCreate, xQueueSend, xQueueReceive

Une **file** (en anglais *queue*) est une boîte aux lettres entre tâches. Une tâche y **dépose** des éléments, une autre les **retire**, dans l'ordre d'arrivée : le premier entré est le premier sorti. Il faut inclure `"freertos/queue.h"` (après `"freertos/FreeRTOS.h"`).

**Créer la file :** `xQueueCreate(longueur, taille_element)`.

```cpp
static QueueHandle_t appuis;                 // en dehors des fonctions : partagée
appuis = xQueueCreate(8, sizeof(int));       // 8 places, chacune de la taille d'un int
if (appuis == NULL) { /* pas assez de mémoire */ }
```

- `longueur` : le nombre maximal d'éléments que la file peut contenir en même temps ;
- `taille_element` : la taille de **chaque** élément en octets. Tous les éléments d'une file ont la même taille. On écrit `sizeof(int)` pour ne pas se tromper.
- Retour : un `QueueHandle_t` (une poignée qui désigne la file), ou `NULL` (0) si la file n'a pas pu être créée.

**Les éléments sont copiés.** `xQueueSend` recopie les octets de l'élément dans la file, `xQueueReceive` les recopie dans votre variable. On peut donc envoyer une variable locale puis la modifier aussitôt : la file garde sa propre copie.

**Envoyer :** `xQueueSend(file, &element, delai)`.

- `&element` : l'**adresse** de ce que l'on envoie (d'où le `&`) ;
- `delai` : combien de temps attendre une place libre si la file est **pleine**, en **ticks** (utilisez `pdMS_TO_TICKS(ms)`). Avec `0`, l'appel rend la main tout de suite si la file est pleine.
- Retour : `pdTRUE` si l'élément est dans la file, sinon `errQUEUE_FULL` (la file était pleine, et l'est restée pendant tout le délai).

**Recevoir :** `xQueueReceive(file, &variable, delai)`.

- `&variable` : l'adresse où recopier l'élément retiré ;
- `delai` : combien de temps attendre un élément si la file est **vide**, en ticks. Avec `0`, l'appel rend la main tout de suite si la file est vide. Avec **`portMAX_DELAY`**, la tâche attend **indéfiniment**, sans délai maximal (sous ESP-IDF, la configuration de FreeRTOS le permet : `INCLUDE_vTaskSuspend` vaut 1).
- Retour : `pdTRUE` si un élément a été reçu (il est alors retiré de la file), sinon `pdFALSE` (la file est restée vide pendant tout le délai).

Pendant ce délai, la tâche est **bloquée** : elle ne consomme pas de processeur, et elle est réveillée dès qu'un élément arrive (ou qu'une place se libère, pour l'envoi). C'est tout l'intérêt de la file.

`xQueueSend` et `xQueueReceive` ne s'appellent pas depuis une routine d'interruption, dit la documentation (il existe des variantes `...FromISR` pour cela, hors programme ici).

!!xQueueReceive(file, &x, 0) dans une boucle sans vTaskDelay est une attente active : la tâche tourne sans jamais dormir, le contrôle la signale comme une tâche qui ne rend jamais la main!!

## Producteur et consommateur

Le schéma du TP porte un nom classique : **producteur et consommateur**.

```
 tâche « bouton »                 file « appuis »               tâche « led »
 (producteur)                     (8 places)                    (consommateur)
 lit GPIO 4 toutes les 10 ms  ->  [ 1 ][ 2 ][   ][   ] ...  ->  bloquée sur xQueueReceive
 anti-rebond du TP 2              xQueueSend(..., 0)            (portMAX_DELAY), inverse la LED
```

- Le **producteur** fabrique des événements : ici, la tâche « bouton » sonde le bouton avec l'anti-rebond du TP 2 et, à chaque appui accepté, dépose le numéro de l'appui dans la file. Il envoie avec un délai 0 : s'il n'y a plus de place (huit appuis non traités, ce qui ne devrait jamais arriver), il ne reste pas coincé et écrit un avertissement.
- Le **consommateur** traite les événements : la tâche « led » attend avec `portMAX_DELAY`, se réveille à chaque événement, inverse la LED, puis se rebloque. Elle n'a **pas** besoin de `vTaskDelay` : c'est `xQueueReceive` qui la fait dormir.
- `app_main` prépare tout (broches, file, tâches), puis se termine.

Pourquoi pas une simple **variable globale** `int appui = 0;` que le bouton met à 1 et que la LED relit ? Parce que la tâche de la LED devrait alors la relire en boucle (attente active ou sondage), qu'un deuxième appui arrivé avant la relecture serait perdu, et que deux tâches qui écrivent la même variable sans protection peuvent se marcher dessus. La file règle les trois problèmes : réveil au bon moment, événements gardés dans l'ordre, accès protégé par FreeRTOS.

**Une seule source d'événements.** Dans le TP, seule la tâche « bouton » écrit dans la file : la LED ne doit changer qu'après un vrai appui. Le contrôle vérifie que les envois viennent d'une tâche créée par `xTaskCreate`, et non de `app_main` qui, lui, ne fait que préparer.

## Exemple complet qui n'est pas le TP

Voici un programme voisin : une tâche « compteur » envoie les nombres 1 à 5, un toutes les 250 ms, puis se supprime ; une tâche « journal » les reçoit avec un délai d'**une seconde** et signale quand rien n'arrive.

```cpp
#include "freertos/FreeRTOS.h"
#include "freertos/task.h"
#include "freertos/queue.h"
#include "esp_log.h"

static const char *TAG = "exemple";
static QueueHandle_t nombres;

static void tache_compteur(void *arg) {
    for (int n = 1; n <= 5; n++) {
        vTaskDelay(pdMS_TO_TICKS(250));
        if (xQueueSend(nombres, &n, pdMS_TO_TICKS(100)) != pdTRUE) {
            ESP_LOGW(TAG, "file pleine, %d perdu", n);
        }
    }
    vTaskDelete(NULL);   // travail fini : la tâche se supprime au lieu de faire return
}

static void tache_journal(void *arg) {
    int recu = 0;
    for (;;) {
        if (xQueueReceive(nombres, &recu, pdMS_TO_TICKS(1000)) == pdTRUE) {
            ESP_LOGI(TAG, "reçu %d (encore %u en attente)", recu, (unsigned)uxQueueMessagesWaiting(nombres));
        } else {
            ESP_LOGW(TAG, "rien reçu depuis une seconde");
        }
    }
}

extern "C" void app_main(void) {
    nombres = xQueueCreate(4, sizeof(int));
    if (nombres == NULL) {
        ESP_LOGE(TAG, "file non créée");
        return;
    }
    if (xTaskCreate(tache_journal, "journal", 3072, NULL, 4, NULL) != pdPASS) ESP_LOGE(TAG, "journal non créée");
    if (xTaskCreate(tache_compteur, "compteur", 3072, NULL, 4, NULL) != pdPASS) ESP_LOGE(TAG, "compteur non créée");
}
```

Lecture : la file est créée **avant** les tâches ; « journal » reçoit 1 à 250 ms, 2 à 500 ms, et ainsi de suite jusqu'à 5 à 1250 ms ; ensuite « compteur » s'est supprimée, la file reste vide, et `xQueueReceive` renvoie `pdFALSE` au bout d'une seconde : « rien reçu depuis une seconde » à 2250 ms, 3250 ms... Ici le délai fini sert à détecter un silence. Dans le TP, la tâche de la LED n'a rien d'autre à faire qu'attendre : elle utilise `portMAX_DELAY`.

## Le programme du TP en un coup d'œil

Le fichier de départ contient déjà, dans `app_main`, la configuration de la LED (GPIO 2 en sortie) et du bouton (GPIO 4 en entrée avec pull-up), exactement comme aux TP 1 et 2. Il contient aussi la fonction `tache_bouton` avec l'anti-rebond du TP 2 : lecture toutes les 10 ms (`POLL_MS`), niveau accepté après 30 ms de stabilité (`STABLE_MS`), action sur le front descendant (l'appui). Vous ajoutez :

1. la déclaration de la file, en dehors des fonctions ;
2. l'envoi dans la file, à l'endroit où le TP 2 inversait la LED ;
3. la réception bloquante dans `tache_led`, qui inverse la LED ;
4. la création de la file dans `app_main` ;
5. la création des deux tâches, la LED d'abord.

Le contrôle simule 5 secondes avec les trois appuis du TP 2, rebonds compris. La LED doit changer **une fois par appui**, dans les 60 ms qui suivent le premier front stable de l'appui. L'anti-rebond reste dans la tâche du bouton : la tâche de la LED ne voit que des appuis propres.

## Mini-référence

- `BaseType_t xTaskCreate(TaskFunction_t pxTaskCode, const char *const pcName, const configSTACK_DEPTH_TYPE usStackDepth, void *const pvParameters, UBaseType_t uxPriority, TaskHandle_t *const pxCreatedTask)` : crée une tâche. Pile en **octets** sous ESP-IDF. Retour : `pdPASS`, ou `errCOULD_NOT_ALLOCATE_REQUIRED_MEMORY` si la mémoire manque.
- `void vTaskDelete(TaskHandle_t xTaskToDelete)` : supprime une tâche ; `vTaskDelete(NULL)` supprime la tâche appelante (et ne revient pas). Pas de valeur de retour.
- `xQueueCreate(uxQueueLength, uxItemSize)` : crée une file de `uxQueueLength` éléments de `uxItemSize` octets. Retour : un `QueueHandle_t`, ou `NULL` (0) en cas d'échec. (C'est une macro qui appelle `xQueueGenericCreate`.)
- `xQueueSend(xQueue, pvItemToQueue, xTicksToWait)` : copie l'élément pointé à la fin de la file ; attend au plus `xTicksToWait` ticks une place libre. Retour : `pdTRUE`, ou `errQUEUE_FULL`. (Macro équivalente à `xQueueSendToBack`, qui appelle `xQueueGenericSend`.)
- `BaseType_t xQueueReceive(QueueHandle_t xQueue, void *const pvBuffer, TickType_t xTicksToWait)` : retire le premier élément et le copie dans `pvBuffer` ; attend au plus `xTicksToWait` ticks (`portMAX_DELAY` : sans limite) si la file est vide. Retour : `pdTRUE`, ou `pdFALSE`.
- `UBaseType_t uxQueueMessagesWaiting(const QueueHandle_t xQueue)` : nombre d'éléments actuellement dans la file.
- `void vQueueDelete(QueueHandle_t xQueue)` : supprime la file et libère sa mémoire ; la poignée ne doit plus servir ensuite.
- `portMAX_DELAY` : le délai « infini » pour les fonctions qui attendent.

`xQueueSend` et `xQueueReceive` ne s'appellent pas depuis une routine d'interruption.

## Pièges

!!Une tâche qui fait return : sur ESP-IDF elle fait arrêter le programme, terminez-la avec vTaskDelete(NULL) ou gardez une boucle infinie!!

Autres erreurs fréquentes :

- Créer les tâches **avant** la file : une tâche peut utiliser une poignée encore vide.
- Déclarer la file comme variable locale de `app_main` : elle n'est pas visible des tâches (et `app_main` peut se terminer).
- Oublier le `&` : `xQueueSend(appuis, numero, 0)` passe la valeur au lieu de l'adresse, et le compilateur C++ refuse de convertir un `int` en pointeur.
- Recevoir avec un délai 0 dans une boucle sans `vTaskDelay` : attente active, le contrôle signale la tâche qui ne rend jamais la main.
- Mettre le délai de sondage du bouton à 0 : `vTaskDelay(0)` ne fait pas avancer le temps, même problème.
- Envoyer depuis `app_main` au lieu de la tâche du bouton : la LED change sans appui.
- Donner une pile trop petite, ou une taille comptée en mots : pile en **octets**, au moins 2048 dans le TP.

## À retenir

**À retenir :** une tâche est une fonction `void f(void *arg)` en boucle infinie, créée par `xTaskCreate(fonction, "nom", pile_en_octets, arg, priorité, NULL)`, qui renvoie `pdPASS` en cas de succès ; elle ne fait jamais `return` (sinon `vTaskDelete(NULL)`), seule `app_main` peut se terminer ; la pile se compte en **octets** sous ESP-IDF ; une file se crée avec `xQueueCreate(longueur, sizeof(element))` avant les tâches, on y dépose une **copie** avec `xQueueSend(file, &x, délai)` (`pdTRUE` ou `errQUEUE_FULL`) et on retire avec `xQueueReceive(file, &x, délai)` (`pdTRUE` ou `pdFALSE`) ; une tâche bloquée sur `xQueueReceive(..., portMAX_DELAY)` dort sans consommer de processeur jusqu'au prochain élément : c'est le schéma producteur et consommateur, préférable à toute attente active.
