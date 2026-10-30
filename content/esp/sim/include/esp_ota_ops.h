/* Fake ESP-IDF v5.x: esp_ota_ops.h (subset): the running partition, the image state, the rollback API.
 * No esp_ota_begin/write/end, no esp_ota_set_boot_partition, no esp_ota_get_next_update_partition, no
 * esp_ota_get_app_description (deprecated). */
#pragma once

#include <stdbool.h>

#include "esp_app_desc.h"
#include "esp_err.h"
#include "esp_flash_partitions.h"
#include "esp_partition.h"

#ifdef __cplusplus
extern "C" {
#endif

#define ESP_ERR_OTA_BASE 0x1500
#define ESP_ERR_OTA_PARTITION_CONFLICT (ESP_ERR_OTA_BASE + 0x01)
#define ESP_ERR_OTA_SELECT_INFO_INVALID (ESP_ERR_OTA_BASE + 0x02)
#define ESP_ERR_OTA_VALIDATE_FAILED (ESP_ERR_OTA_BASE + 0x03)
#define ESP_ERR_OTA_SMALL_SEC_VER (ESP_ERR_OTA_BASE + 0x04)
#define ESP_ERR_OTA_ROLLBACK_FAILED (ESP_ERR_OTA_BASE + 0x05)
#define ESP_ERR_OTA_ROLLBACK_INVALID_STATE (ESP_ERR_OTA_BASE + 0x06)

const esp_partition_t *esp_ota_get_running_partition(void);
esp_err_t esp_ota_get_state_partition(const esp_partition_t *partition, esp_ota_img_states_t *ota_state);
esp_err_t esp_ota_mark_app_valid_cancel_rollback(void);
esp_err_t esp_ota_mark_app_invalid_rollback_and_reboot(void);
const esp_partition_t *esp_ota_get_last_invalid_partition(void);
bool esp_ota_check_rollback_is_possible(void);

#ifdef __cplusplus
}
#endif
