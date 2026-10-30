/* Fake ESP-IDF v5.x: esp_tls.h. Only the error codes (esp_tls_errors.h) are provided: the simulator has no
 * esp_tls_conn_*, no esp_tls_cfg_t, and takes the TLS settings from esp-mqtt and esp_http_client. */
#pragma once

#include "esp_tls_errors.h"
