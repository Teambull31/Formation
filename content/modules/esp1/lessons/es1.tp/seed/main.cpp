// TP 1 : faire clignoter la LED du GPIO 2 (500 ms allumée, 500 ms éteinte).
// Suivez les étapes TODO dans l'ordre. Le contrôle compile ce fichier et simule 10 secondes.
#include "freertos/FreeRTOS.h"
#include "freertos/task.h"
#include "driver/gpio.h"
#include "esp_log.h"

// Le tag des journaux de ce programme (étape 3) : une constante texte, visible seulement dans
// ce fichier (static), que l'on passe en premier argument de chaque ESP_LOGI.
static const char *TAG = "blink";

extern "C" void app_main(void) {
    // TODO étape 1 : déclarer un gpio_config_t (initialisé avec {}), remplir pin_bit_mask
    // (1ULL << GPIO_NUM_2) et mode (GPIO_MODE_OUTPUT), puis l'appliquer avec gpio_config(&...).
    // Enveloppez l'appel dans ESP_ERROR_CHECK(...).

    // TODO étape 2 : écrire une boucle infinie for (;;) { ... }. Avant elle, créez une variable
    // int level = 0 ; au début de chaque tour, inversez-la avec level = !level (premier tour : 1).

    // Dans la boucle :
    //   TODO étape 3 : gpio_set_level(GPIO_NUM_2, level), puis ESP_LOGI(TAG, "LED %s", ...)
    //                  pour dire si la LED est allumée ou éteinte.
    //   TODO étape 4 : attendre 500 ms avec vTaskDelay(pdMS_TO_TICKS(500)).
}
