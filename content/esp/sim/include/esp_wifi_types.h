/* Fake ESP-IDF v5.x: esp_wifi_types.h (subset, STA only; the AP config is shortened, event and reason
 * enums keep the real values of the constants listed). */
#pragma once

#include <stdbool.h>
#include <stdint.h>

#include "esp_event_base.h"

#ifdef __cplusplus
extern "C" {
#endif

typedef enum {
    WIFI_MODE_NULL = 0,
    WIFI_MODE_STA,
    WIFI_MODE_AP,
    WIFI_MODE_APSTA,
    WIFI_MODE_NAN,
    WIFI_MODE_MAX
} wifi_mode_t;

typedef enum {
    WIFI_IF_STA = 0,
    WIFI_IF_AP = 1,
    WIFI_IF_NAN = 2,
    WIFI_IF_MAX
} wifi_interface_t;

typedef enum {
    WIFI_AUTH_OPEN = 0,
    WIFI_AUTH_WEP,
    WIFI_AUTH_WPA_PSK,
    WIFI_AUTH_WPA2_PSK,
    WIFI_AUTH_WPA_WPA2_PSK,
    WIFI_AUTH_ENTERPRISE,
    WIFI_AUTH_WPA2_ENTERPRISE = WIFI_AUTH_ENTERPRISE,
    WIFI_AUTH_WPA3_PSK,
    WIFI_AUTH_WPA2_WPA3_PSK,
    WIFI_AUTH_WAPI_PSK,
    WIFI_AUTH_OWE,
    WIFI_AUTH_WPA3_ENT_192,
    WIFI_AUTH_WPA3_EXT_PSK,
    WIFI_AUTH_WPA3_EXT_PSK_MIXED_MODE,
    WIFI_AUTH_DPP,
    WIFI_AUTH_WPA3_ENTERPRISE,
    WIFI_AUTH_WPA2_WPA3_ENTERPRISE,
    WIFI_AUTH_WPA_ENTERPRISE,
    WIFI_AUTH_MAX
} wifi_auth_mode_t;

typedef enum {
    WIFI_REASON_UNSPECIFIED = 1,
    WIFI_REASON_AUTH_EXPIRE = 2,
    WIFI_REASON_AUTH_LEAVE = 3,
    WIFI_REASON_ASSOC_EXPIRE = 4,
    WIFI_REASON_ASSOC_TOOMANY = 5,
    WIFI_REASON_NOT_AUTHED = 6,
    WIFI_REASON_NOT_ASSOCED = 7,
    WIFI_REASON_ASSOC_LEAVE = 8,
    WIFI_REASON_BEACON_TIMEOUT = 200,
    WIFI_REASON_NO_AP_FOUND = 201,
    WIFI_REASON_AUTH_FAIL = 202,
    WIFI_REASON_ASSOC_FAIL = 203,
    WIFI_REASON_HANDSHAKE_TIMEOUT = 204,
    WIFI_REASON_CONNECTION_FAIL = 205,
} wifi_err_reason_t;

typedef enum {
    WIFI_FAST_SCAN = 0,
    WIFI_ALL_CHANNEL_SCAN
} wifi_scan_method_t;

typedef enum {
    WIFI_CONNECT_AP_BY_SIGNAL = 0,
    WIFI_CONNECT_AP_BY_SECURITY
} wifi_sort_method_t;

typedef struct {
    int8_t rssi;
    wifi_auth_mode_t authmode;
    uint8_t rssi_5g_adjustment;
} wifi_scan_threshold_t;

typedef struct {
    bool capable;
    bool required;
} wifi_pmf_config_t;

typedef enum {
    WPA3_SAE_PWE_UNSPECIFIED,
    WPA3_SAE_PWE_HUNT_AND_PECK,
    WPA3_SAE_PWE_HASH_TO_ELEMENT,
    WPA3_SAE_PWE_BOTH,
} wifi_sae_pwe_method_t;

typedef enum {
    WPA3_SAE_PK_MODE_AUTOMATIC = 0,
    WPA3_SAE_PK_MODE_ONLY = 1,
    WPA3_SAE_PK_MODE_DISABLED = 2,
} wifi_sae_pk_mode_t;

#define SAE_H2E_IDENTIFIER_LEN 32

typedef struct {
    uint8_t ssid[32];
    uint8_t password[64];
    wifi_scan_method_t scan_method;
    bool bssid_set;
    uint8_t bssid[6];
    uint8_t channel;
    uint16_t listen_interval;
    wifi_sort_method_t sort_method;
    wifi_scan_threshold_t threshold;
    wifi_pmf_config_t pmf_cfg;
    uint32_t rm_enabled:1;
    uint32_t btm_enabled:1;
    uint32_t mbo_enabled:1;
    uint32_t ft_enabled:1;
    uint32_t owe_enabled:1;
    uint32_t transition_disable:1;
    uint32_t reserved1:26;
    wifi_sae_pwe_method_t sae_pwe_h2e;
    wifi_sae_pk_mode_t sae_pk_mode;
    uint8_t failure_retry_cnt;
    uint8_t sae_h2e_identifier[SAE_H2E_IDENTIFIER_LEN];
} wifi_sta_config_t;

typedef struct {
    uint8_t ssid[32];
    uint8_t password[64];
    uint8_t ssid_len;
    uint8_t channel;
    wifi_auth_mode_t authmode;
    uint8_t ssid_hidden;
    uint8_t max_connection;
    uint16_t beacon_interval;
} wifi_ap_config_t;

typedef union {
    wifi_ap_config_t ap;
    wifi_sta_config_t sta;
} wifi_config_t;

ESP_EVENT_DECLARE_BASE(WIFI_EVENT);

typedef enum {
    WIFI_EVENT_WIFI_READY = 0,
    WIFI_EVENT_SCAN_DONE,
    WIFI_EVENT_STA_START,
    WIFI_EVENT_STA_STOP,
    WIFI_EVENT_STA_CONNECTED,
    WIFI_EVENT_STA_DISCONNECTED,
    WIFI_EVENT_STA_AUTHMODE_CHANGE,
} wifi_event_t;

typedef struct {
    uint8_t ssid[32];
    uint8_t ssid_len;
    uint8_t bssid[6];
    uint8_t channel;
    wifi_auth_mode_t authmode;
    uint16_t aid;
} wifi_event_sta_connected_t;

typedef struct {
    uint8_t ssid[32];
    uint8_t ssid_len;
    uint8_t bssid[6];
    uint8_t reason;
    int8_t rssi;
} wifi_event_sta_disconnected_t;

#ifdef __cplusplus
}
#endif
