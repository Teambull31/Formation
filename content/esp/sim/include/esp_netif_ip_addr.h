/* Fake ESP-IDF v5.x: esp_netif_ip_addr.h (subset: IPv4 address and its printf helpers). */
#pragma once

#include <stdint.h>

typedef struct {
    uint32_t addr;
} esp_ip4_addr_t;

#define esp_ip4_addr_get_byte(ipaddr, idx) (((const uint8_t *)(&(ipaddr)->addr))[idx])
#define esp_ip4_addr1(ipaddr) esp_ip4_addr_get_byte(ipaddr, 0)
#define esp_ip4_addr2(ipaddr) esp_ip4_addr_get_byte(ipaddr, 1)
#define esp_ip4_addr3(ipaddr) esp_ip4_addr_get_byte(ipaddr, 2)
#define esp_ip4_addr4(ipaddr) esp_ip4_addr_get_byte(ipaddr, 3)
#define esp_ip4_addr1_16(ipaddr) ((uint16_t)esp_ip4_addr1(ipaddr))
#define esp_ip4_addr2_16(ipaddr) ((uint16_t)esp_ip4_addr2(ipaddr))
#define esp_ip4_addr3_16(ipaddr) ((uint16_t)esp_ip4_addr3(ipaddr))
#define esp_ip4_addr4_16(ipaddr) ((uint16_t)esp_ip4_addr4(ipaddr))
#define IP2STR(ipaddr) esp_ip4_addr1_16(ipaddr), esp_ip4_addr2_16(ipaddr), esp_ip4_addr3_16(ipaddr), esp_ip4_addr4_16(ipaddr)
#define IPSTR "%d.%d.%d.%d"
