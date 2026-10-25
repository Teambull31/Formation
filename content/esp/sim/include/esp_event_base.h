/* Fake ESP-IDF v5.x: esp_event_base.h. */
#pragma once

#include <stddef.h>
#include <stdint.h>

#ifdef __cplusplus
extern "C" {
#endif

typedef const char *esp_event_base_t;
typedef void *esp_event_loop_handle_t;
typedef void (*esp_event_handler_t)(void *event_handler_arg, esp_event_base_t event_base, int32_t event_id, void *event_data);
typedef void *esp_event_handler_instance_t;

#define ESP_EVENT_DECLARE_BASE(id) extern esp_event_base_t const id
#define ESP_EVENT_DEFINE_BASE(id) esp_event_base_t const id = #id
#define ESP_EVENT_ANY_BASE NULL
#define ESP_EVENT_ANY_ID -1

#ifdef __cplusplus
}
#endif
