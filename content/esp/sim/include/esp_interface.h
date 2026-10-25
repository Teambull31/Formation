/* Fake ESP-IDF v5.x: esp_interface.h. */
#pragma once

#ifdef __cplusplus
extern "C" {
#endif

typedef enum {
    ESP_IF_WIFI_STA = 0,
    ESP_IF_WIFI_AP,
    ESP_IF_WIFI_NAN,
    ESP_IF_ETH,
    ESP_IF_IEEE802154,
    ESP_IF_MAX
} esp_interface_t;

#ifdef __cplusplus
}
#endif
