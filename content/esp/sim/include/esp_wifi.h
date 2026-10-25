/* Fake ESP-IDF v5.x: esp_wifi.h (subset: station mode). wifi_init_config_t keeps only a few of the real
 * driver-tuning fields (a learner only passes WIFI_INIT_CONFIG_DEFAULT() through). */
#pragma once

#include <stdint.h>

#include "esp_err.h"
#include "esp_event.h"
#include "esp_interface.h"
#include "esp_netif.h"
#include "esp_wifi_default.h"
#include "esp_wifi_types.h"

#ifdef __cplusplus
extern "C" {
#endif

#define ESP_ERR_WIFI_BASE 0x3000
#define ESP_ERR_WIFI_NOT_INIT (ESP_ERR_WIFI_BASE + 1)
#define ESP_ERR_WIFI_NOT_STARTED (ESP_ERR_WIFI_BASE + 2)
#define ESP_ERR_WIFI_NOT_STOPPED (ESP_ERR_WIFI_BASE + 3)
#define ESP_ERR_WIFI_IF (ESP_ERR_WIFI_BASE + 4)
#define ESP_ERR_WIFI_MODE (ESP_ERR_WIFI_BASE + 5)
#define ESP_ERR_WIFI_STATE (ESP_ERR_WIFI_BASE + 6)
#define ESP_ERR_WIFI_CONN (ESP_ERR_WIFI_BASE + 7)
#define ESP_ERR_WIFI_NVS (ESP_ERR_WIFI_BASE + 8)
#define ESP_ERR_WIFI_MAC (ESP_ERR_WIFI_BASE + 9)
#define ESP_ERR_WIFI_SSID (ESP_ERR_WIFI_BASE + 10)
#define ESP_ERR_WIFI_PASSWORD (ESP_ERR_WIFI_BASE + 11)
#define ESP_ERR_WIFI_TIMEOUT (ESP_ERR_WIFI_BASE + 12)
#define ESP_ERR_WIFI_WAKE_FAIL (ESP_ERR_WIFI_BASE + 13)
#define ESP_ERR_WIFI_WOULD_BLOCK (ESP_ERR_WIFI_BASE + 14)
#define ESP_ERR_WIFI_NOT_CONNECT (ESP_ERR_WIFI_BASE + 15)

#define WIFI_INIT_CONFIG_MAGIC 0x1F2F3F4F

typedef struct {
    int static_rx_buf_num;
    int dynamic_rx_buf_num;
    int static_tx_buf_num;
    int dynamic_tx_buf_num;
    int nvs_enable;
    int magic;
} wifi_init_config_t;

#define WIFI_INIT_CONFIG_DEFAULT() { 10, 32, 16, 32, 1, WIFI_INIT_CONFIG_MAGIC }

esp_err_t esp_wifi_init(const wifi_init_config_t *config);
esp_err_t esp_wifi_deinit(void);
esp_err_t esp_wifi_set_mode(wifi_mode_t mode);
esp_err_t esp_wifi_start(void);
esp_err_t esp_wifi_stop(void);
esp_err_t esp_wifi_connect(void);
esp_err_t esp_wifi_disconnect(void);
esp_err_t esp_wifi_set_config(wifi_interface_t interface, wifi_config_t *conf);

#ifdef __cplusplus
}
#endif
