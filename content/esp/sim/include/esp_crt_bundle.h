/* Fake ESP-IDF v5.x: esp_crt_bundle.h (subset). The simulated bundle holds public CAs only: it trusts a broker
 * or server only when the scenario's "tls" section says "public_ca": true. */
#pragma once

#include "esp_err.h"

#ifdef __cplusplus
extern "C" {
#endif

esp_err_t esp_crt_bundle_attach(void *conf);

#ifdef __cplusplus
}
#endif
