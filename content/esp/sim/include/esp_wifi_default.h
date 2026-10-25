/* Fake ESP-IDF v5.x: esp_wifi_default.h (subset: the default STA netif). */
#pragma once

#include "esp_netif_types.h"

#ifdef __cplusplus
extern "C" {
#endif

esp_netif_t *esp_netif_create_default_wifi_sta(void);

#ifdef __cplusplus
}
#endif
