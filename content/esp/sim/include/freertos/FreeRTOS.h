/* Fake ESP-IDF v5.x: freertos/FreeRTOS.h (subset). Tick rate is the ESP-IDF default, 100 Hz. */
#ifndef INC_FREERTOS_H
#define INC_FREERTOS_H

#include <stddef.h>
#include <stdint.h>

typedef uint32_t TickType_t;
typedef int BaseType_t;
typedef unsigned int UBaseType_t;

#define configTICK_RATE_HZ 100
#define configSTACK_DEPTH_TYPE uint32_t

#define pdFALSE ((BaseType_t)0)
#define pdTRUE ((BaseType_t)1)
#define pdPASS (pdTRUE)
#define pdFAIL (pdFALSE)

#define portTICK_PERIOD_MS ((TickType_t)1000 / configTICK_RATE_HZ)
#define pdMS_TO_TICKS(xTimeInMs) \
    ((TickType_t)(((uint64_t)(xTimeInMs) * (uint64_t)configTICK_RATE_HZ) / (uint64_t)1000U))

#endif
