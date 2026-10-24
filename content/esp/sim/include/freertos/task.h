/* Fake ESP-IDF v5.x: freertos/task.h (subset). */
#pragma once

#ifndef INC_FREERTOS_H
#error "include FreeRTOS.h must appear in source files before include task.h"
#endif

#ifdef __cplusplus
extern "C" {
#endif

typedef struct tskTaskControlBlock *TaskHandle_t;
typedef void (*TaskFunction_t)(void *);

BaseType_t xTaskCreate(TaskFunction_t pxTaskCode, const char *const pcName,
                       const configSTACK_DEPTH_TYPE usStackDepth, void *const pvParameters,
                       UBaseType_t uxPriority, TaskHandle_t *const pxCreatedTask);
void vTaskDelay(const TickType_t xTicksToDelay);
void vTaskDelete(TaskHandle_t xTaskToDelete);
TickType_t xTaskGetTickCount(void);

#ifdef __cplusplus
}
#endif
