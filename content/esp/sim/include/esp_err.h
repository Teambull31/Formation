/* Fake ESP-IDF v5.x: esp_err.h (subset). */
#pragma once

#include <stdint.h>

#ifdef __cplusplus
extern "C" {
#endif

typedef int esp_err_t;

#define ESP_OK 0
#define ESP_FAIL -1

const char *esp_err_to_name(esp_err_t code);

void _esp_error_check_failed(esp_err_t rc, const char *file, int line, const char *function,
                             const char *expression) __attribute__((__noreturn__));

#define ESP_ERROR_CHECK(x)                                                                  \
    do {                                                                                    \
        esp_err_t err_rc_ = (x);                                                            \
        if (err_rc_ != ESP_OK) {                                                            \
            _esp_error_check_failed(err_rc_, __FILE__, __LINE__, __func__, #x);             \
        }                                                                                   \
    } while (0)

#ifdef __cplusplus
}
#endif
