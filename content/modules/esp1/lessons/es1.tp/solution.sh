#!/usr/bin/env bash
# Solution de référence du TP es1.
set -euo pipefail
cat > main.cpp <<'EOF'
#include "freertos/FreeRTOS.h"
#include "freertos/task.h"
#include "driver/gpio.h"
#include "esp_log.h"

static const char *TAG = "blink";

extern "C" void app_main(void) {
    gpio_config_t io = {};
    io.pin_bit_mask = 1ULL << GPIO_NUM_2;
    io.mode = GPIO_MODE_OUTPUT;
    ESP_ERROR_CHECK(gpio_config(&io));

    int level = 0;
    for (;;) {
        level = !level;
        gpio_set_level(GPIO_NUM_2, level);
        ESP_LOGI(TAG, "LED %s", level ? "allumée" : "éteinte");
        vTaskDelay(pdMS_TO_TICKS(500));
    }
}
EOF
