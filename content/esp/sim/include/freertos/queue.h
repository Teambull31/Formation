/* Fake ESP-IDF v5.x: freertos/queue.h (subset). Items are copied in and out, FIFO, as in FreeRTOS. */
#pragma once

#ifndef INC_FREERTOS_H
#error "include FreeRTOS.h" must appear in source files before "include queue.h"
#endif

#ifdef __cplusplus
extern "C" {
#endif

typedef struct QueueDefinition * QueueHandle_t;

#define queueSEND_TO_BACK                     ( ( BaseType_t ) 0 )
#define queueQUEUE_TYPE_BASE                  ( ( uint8_t ) 0U )

#define xQueueCreate( uxQueueLength, uxItemSize )    xQueueGenericCreate( ( uxQueueLength ), ( uxItemSize ), ( queueQUEUE_TYPE_BASE ) )
#define xQueueSendToBack( xQueue, pvItemToQueue, xTicksToWait ) \
    xQueueGenericSend( ( xQueue ), ( pvItemToQueue ), ( xTicksToWait ), queueSEND_TO_BACK )
#define xQueueSend( xQueue, pvItemToQueue, xTicksToWait ) \
    xQueueGenericSend( ( xQueue ), ( pvItemToQueue ), ( xTicksToWait ), queueSEND_TO_BACK )

QueueHandle_t xQueueGenericCreate( const UBaseType_t uxQueueLength,
                                   const UBaseType_t uxItemSize,
                                   const uint8_t ucQueueType );
BaseType_t xQueueGenericSend( QueueHandle_t xQueue,
                              const void * const pvItemToQueue,
                              TickType_t xTicksToWait,
                              const BaseType_t xCopyPosition );
BaseType_t xQueueReceive( QueueHandle_t xQueue,
                          void * const pvBuffer,
                          TickType_t xTicksToWait );
UBaseType_t uxQueueMessagesWaiting( const QueueHandle_t xQueue );
void vQueueDelete( QueueHandle_t xQueue );

#ifdef __cplusplus
}
#endif
