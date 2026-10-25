/* Fake ESP-IDF v5.x: esp_netif.h (subset). */
#pragma once

#include "esp_err.h"
#include "esp_netif_ip_addr.h"
#include "esp_netif_types.h"
#include "esp_wifi_default.h"

#ifdef __cplusplus
extern "C" {
#endif

esp_err_t esp_netif_init(void);

#ifdef __cplusplus
}
#endif
