/* Fake ESP-IDF v5.x: esp_netif_types.h (subset: the STA got-IP event). */
#pragma once

#include <stdbool.h>

#include "esp_event_base.h"
#include "esp_netif_ip_addr.h"

#ifdef __cplusplus
extern "C" {
#endif

typedef struct esp_netif_obj esp_netif_t;

typedef struct {
    esp_ip4_addr_t ip;
    esp_ip4_addr_t netmask;
    esp_ip4_addr_t gw;
} esp_netif_ip_info_t;

ESP_EVENT_DECLARE_BASE(IP_EVENT);

typedef enum {
    IP_EVENT_STA_GOT_IP,
    IP_EVENT_STA_LOST_IP,
    IP_EVENT_AP_STAIPASSIGNED,
    IP_EVENT_GOT_IP6,
    IP_EVENT_ETH_GOT_IP,
    IP_EVENT_ETH_LOST_IP,
    IP_EVENT_PPP_GOT_IP,
    IP_EVENT_PPP_LOST_IP,
} ip_event_t;

typedef struct {
    esp_netif_t *esp_netif;
    esp_netif_ip_info_t ip_info;
    bool ip_changed;
} ip_event_got_ip_t;

#ifdef __cplusplus
}
#endif
