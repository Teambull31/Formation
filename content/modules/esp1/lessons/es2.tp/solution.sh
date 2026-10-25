#!/usr/bin/env bash
# Solution de référence du TP es2.
set -euo pipefail
cat > main.cpp <<'EOF'
#include "freertos/FreeRTOS.h"
#include "freertos/task.h"
#include "driver/gpio.h"
#include "esp_log.h"

static const char *TAG = "bouton";

static const int POLL_MS = 10;    // on lit le bouton toutes les 10 ms
static const int STABLE_MS = 30;  // un niveau compte s'il dure 30 ms sans changer

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

    int led_level = 0;
    int stable = 1;      // niveau accepté du bouton : 1 = relâché, 0 = enfoncé
    int candidate = 1;   // dernier niveau lu
    int since_ms = 0;    // depuis combien de temps il n'a pas changé
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
                led_level = !led_level;
                gpio_set_level(GPIO_NUM_2, led_level);
                ESP_LOGI(TAG, "appui, LED %s", led_level ? "allumée" : "éteinte");
            }
        }
        vTaskDelay(pdMS_TO_TICKS(POLL_MS));
    }
}
EOF
