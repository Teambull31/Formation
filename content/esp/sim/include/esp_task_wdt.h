/* Fake ESP-IDF v5.x: esp_task_wdt.h (subset: task subscription, no "users"). */
#pragma once

#include <stdbool.h>
#include <stdint.h>

#include "esp_err.h"
#include "freertos/FreeRTOS.h"
#include "freertos/task.h"

#ifdef __cplusplus
extern "C" {
#endif

typedef struct {
    uint32_t timeout_ms;
    uint32_t idle_core_mask;
    bool trigger_panic;
} esp_task_wdt_config_t;

esp_err_t esp_task_wdt_init(const esp_task_wdt_config_t *config);
esp_err_t esp_task_wdt_reconfigure(const esp_task_wdt_config_t *config);
esp_err_t esp_task_wdt_deinit(void);
esp_err_t esp_task_wdt_add(TaskHandle_t task_handle);
esp_err_t esp_task_wdt_reset(void);
esp_err_t esp_task_wdt_delete(TaskHandle_t task_handle);
esp_err_t esp_task_wdt_status(TaskHandle_t task_handle);

#ifdef __cplusplus
}
#endif
