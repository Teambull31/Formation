#!/usr/bin/env bash
# Solution de référence du TP es3.
set -euo pipefail
cat > main.cpp <<'EOF'
#include "freertos/FreeRTOS.h"
#include "freertos/task.h"
#include "freertos/queue.h"
#include "driver/gpio.h"
#include "esp_log.h"

static const char *TAG = "files";

static const int POLL_MS = 10;    // on lit le bouton toutes les 10 ms
static const int STABLE_MS = 30;  // un niveau compte s'il dure 30 ms sans changer

static QueueHandle_t appuis;      // la file des appuis : créée dans app_main, lue par la tâche LED

// Producteur : sonde le bouton (anti-rebond du TP 2) et poste un événement par appui.
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
                if (xQueueSend(appuis, &numero, 0) != pdTRUE) {
                    ESP_LOGW(TAG, "file pleine, appui %d perdu", numero);
                }
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
        if (xQueueReceive(appuis, &numero, portMAX_DELAY) == pdTRUE) {
            led_level = !led_level;
            gpio_set_level(GPIO_NUM_2, led_level);
            ESP_LOGI(TAG, "appui %d reçu, LED %s", numero, led_level ? "allumée" : "éteinte");
        }
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

    appuis = xQueueCreate(8, sizeof(int));
    if (appuis == NULL) {
        ESP_LOGE(TAG, "file non créée (mémoire insuffisante)");
        return;
    }
    if (xTaskCreate(tache_led, "led", 4096, NULL, 5, NULL) != pdPASS) {
        ESP_LOGE(TAG, "tâche led non créée");
    }
    if (xTaskCreate(tache_bouton, "bouton", 4096, NULL, 5, NULL) != pdPASS) {
        ESP_LOGE(TAG, "tâche bouton non créée");
    }
}
EOF
