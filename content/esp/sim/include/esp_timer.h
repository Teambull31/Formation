/* Fake ESP-IDF v5.x: esp_timer.h (subset). Time is virtual. */
#pragma once

#include <stdint.h>

#ifdef __cplusplus
extern "C" {
#endif

int64_t esp_timer_get_time(void);

#ifdef __cplusplus
}
#endif
