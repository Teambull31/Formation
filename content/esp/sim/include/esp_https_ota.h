/* Fake ESP-IDF v5.x: esp_https_ota.h (subset): the one-call esp_https_ota. No esp_https_ota_begin/perform/
 * finish/abort. esp_https_ota_config_t keeps the real names and order of the fields listed, not the others
 * (buffer_caps, ota_resumption, decrypt_cb, staging, ...); http_client_init_cb is accepted and never called. */
#pragma once

#include <stdbool.h>

#include "esp_err.h"
#include "esp_http_client.h"

#ifdef __cplusplus
extern "C" {
#endif

typedef esp_err_t (*http_client_init_cb_t)(esp_http_client_handle_t);

typedef struct {
    const esp_http_client_config_t *http_config;
    http_client_init_cb_t http_client_init_cb;
    bool bulk_flash_erase;
    bool partial_http_download;
    int max_http_request_size;
} esp_https_ota_config_t;

esp_err_t esp_https_ota(const esp_https_ota_config_t *ota_config);

#ifdef __cplusplus
}
#endif
