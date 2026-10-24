/* Fake ESP-IDF v5.x: esp_log.h (subset). Each log becomes one "log" trace event. */
#pragma once

#ifdef __cplusplus
extern "C" {
#endif

typedef enum {
    ESP_LOG_NONE = 0,
    ESP_LOG_ERROR = 1,
    ESP_LOG_WARN = 2,
    ESP_LOG_INFO = 3,
    ESP_LOG_DEBUG = 4,
    ESP_LOG_VERBOSE = 5,
} esp_log_level_t;

void esp_log_write(esp_log_level_t level, const char *tag, const char *format, ...)
    __attribute__((format(printf, 3, 4)));

#define ESP_LOGE(tag, format, ...) esp_log_write(ESP_LOG_ERROR, tag, format, ##__VA_ARGS__)
#define ESP_LOGW(tag, format, ...) esp_log_write(ESP_LOG_WARN, tag, format, ##__VA_ARGS__)
#define ESP_LOGI(tag, format, ...) esp_log_write(ESP_LOG_INFO, tag, format, ##__VA_ARGS__)
#define ESP_LOGD(tag, format, ...) esp_log_write(ESP_LOG_DEBUG, tag, format, ##__VA_ARGS__)

#ifdef __cplusplus
}
#endif
