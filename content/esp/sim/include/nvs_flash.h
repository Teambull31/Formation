/* Fake ESP-IDF v5.x: nvs_flash.h (subset: the default "nvs" partition). */
#pragma once

#include "esp_err.h"
#include "nvs.h"

#ifdef __cplusplus
extern "C" {
#endif

esp_err_t nvs_flash_init(void);
esp_err_t nvs_flash_deinit(void);
esp_err_t nvs_flash_erase(void);

#ifdef __cplusplus
}
#endif
