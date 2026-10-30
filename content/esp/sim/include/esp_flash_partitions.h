/* Fake ESP-IDF v5.x: esp_flash_partitions.h (subset): the OTA image states only. */
#pragma once

#ifdef __cplusplus
extern "C" {
#endif

typedef enum {
    ESP_OTA_IMG_NEW = 0x0U,
    ESP_OTA_IMG_PENDING_VERIFY = 0x1U,
    ESP_OTA_IMG_VALID = 0x2U,
    ESP_OTA_IMG_INVALID = 0x3U,
    ESP_OTA_IMG_ABORTED = 0x4U,
    ESP_OTA_IMG_UNDEFINED = 0xFFFFFFFFU,
} esp_ota_img_states_t;

#ifdef __cplusplus
}
#endif
