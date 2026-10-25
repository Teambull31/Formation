// TP 2 : le bouton du GPIO 4 inverse la LED du GPIO 2, une seule fois par appui.
// Suivez les étapes TODO dans l'ordre. Le contrôle compile ce fichier et simule 5 secondes
// pendant lesquelles on appuie 3 fois sur le bouton (avec des rebonds).
#include "freertos/FreeRTOS.h"
#include "freertos/task.h"
#include "driver/gpio.h"
#include "esp_log.h"

static const char *TAG = "bouton";

static const int POLL_MS = 10;    // période de lecture du bouton (étape 3)
static const int STABLE_MS = 30;  // durée de stabilité exigée avant d'accepter un niveau (étape 4)

extern "C" void app_main(void) {
    // TODO étape 1 : configurer la LED en sortie, comme dans le TP 1 : un gpio_config_t led = {} avec
    // pin_bit_mask = 1ULL << GPIO_NUM_2 et mode = GPIO_MODE_OUTPUT, appliqué par gpio_config(&led)
    // dans ESP_ERROR_CHECK.

    // TODO étape 2 : configurer le bouton en entrée avec pull-up : un gpio_config_t btn = {} avec
    // pin_bit_mask = 1ULL << GPIO_NUM_4, mode = GPIO_MODE_INPUT et pull_up_en = GPIO_PULLUP_ENABLE,
    // appliqué par gpio_config(&btn) dans ESP_ERROR_CHECK.

    // TODO étape 3 : avant la boucle, créer int led_level = 0, int stable = 1 (bouton relâché),
    // int candidate = 1 et int since_ms = 0. Puis écrire for (;;) { ... } qui, à chaque tour,
    // lit int raw = gpio_get_level(GPIO_NUM_4) et se termine par vTaskDelay(pdMS_TO_TICKS(POLL_MS)).

    // Dans la boucle :
    //   TODO étape 4 : si raw != candidate, candidate = raw et since_ms = 0 ; sinon since_ms += POLL_MS.
    //   TODO étape 5 : si candidate != stable et since_ms >= STABLE_MS, alors stable = candidate ;
    //                  et si stable == 0 (appui), inverser led_level, gpio_set_level(GPIO_NUM_2, led_level)
    //                  puis ESP_LOGI(TAG, ...).
}
