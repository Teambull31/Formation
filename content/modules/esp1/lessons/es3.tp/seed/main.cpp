// TP 3 : deux tâches FreeRTOS reliées par une file. La tâche « bouton » sonde le GPIO 4 et poste
// un événement par appui ; la tâche « led » attend ces événements et inverse la LED du GPIO 2.
// Suivez les étapes TODO dans l'ordre. Le contrôle compile ce fichier et simule 5 secondes
// pendant lesquelles on appuie 3 fois sur le bouton (avec des rebonds, comme au TP 2).
#include "freertos/FreeRTOS.h"
#include "freertos/task.h"
#include "freertos/queue.h"
#include "driver/gpio.h"
#include "esp_log.h"

static const char *TAG = "files";

static const int POLL_MS = 10;    // période de lecture du bouton
static const int STABLE_MS = 30;  // durée de stabilité exigée avant d'accepter un niveau

// TODO étape 1 : déclarer ici la file, partagée par les deux tâches : static QueueHandle_t appuis;

// Producteur : sonde le bouton et poste un événement par appui.
static void tache_bouton(void *arg) {
    int stable = 1;      // niveau accepté : 1 = relâché, 0 = enfoncé
    int candidate = 1;   // dernier niveau lu
    int since_ms = 0;    // depuis combien de temps il n'a pas changé
    int numero = 0;      // numéro de l'appui, envoyé dans la file
    for (;;) {
        int raw = gpio_get_level(GPIO_NUM_4);
        if (raw != candidate) {
            candidate = raw;
            since_ms = 0;
        } else {
            since_ms += POLL_MS;
        }
        if (candidate != stable && since_ms >= STABLE_MS) {
            stable = candidate;
            if (stable == 0) {
                numero++;
                // TODO étape 2 : poster l'appui sans attendre : xQueueSend(appuis, &numero, 0).
                // S'il ne renvoie pas pdTRUE (file pleine), écrire un ESP_LOGW.
            }
        }
        vTaskDelay(pdMS_TO_TICKS(POLL_MS));
    }
}

// Consommateur : dort jusqu'au prochain événement, puis inverse la LED.
static void tache_led(void *arg) {
    int led_level = 0;
    int numero = 0;
    for (;;) {
        // TODO étape 3 : attendre un événement : if (xQueueReceive(appuis, &numero, portMAX_DELAY) == pdTRUE)
        // et, dans ce if, inverser led_level, gpio_set_level(GPIO_NUM_2, led_level) puis ESP_LOGI(TAG, ...).
        // Pas de vTaskDelay ici : c'est xQueueReceive qui fait dormir la tâche.
    }
}

extern "C" void app_main(void) {
    gpio_config_t led = {};
    led.pin_bit_mask = 1ULL << GPIO_NUM_2;
    led.mode = GPIO_MODE_OUTPUT;
    ESP_ERROR_CHECK(gpio_config(&led));

    gpio_config_t btn = {};
    btn.pin_bit_mask = 1ULL << GPIO_NUM_4;
    btn.mode = GPIO_MODE_INPUT;
    btn.pull_up_en = GPIO_PULLUP_ENABLE;
    ESP_ERROR_CHECK(gpio_config(&btn));

    // TODO étape 4 : créer la file : appuis = xQueueCreate(8, sizeof(int)) ; si elle vaut NULL,
    // ESP_LOGE puis return.

    // TODO étape 5 : créer les deux tâches, la LED d'abord, chacune avec 4096 octets de pile et la priorité 5 :
    // xTaskCreate(tache_led, "led", 4096, NULL, 5, NULL) puis xTaskCreate(tache_bouton, "bouton", 4096, NULL, 5, NULL).
    // Vérifier que chacune renvoie pdPASS (sinon ESP_LOGE). app_main peut ensuite se terminer.
}
