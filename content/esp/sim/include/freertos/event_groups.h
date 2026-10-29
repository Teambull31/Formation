/* Fake ESP-IDF v5.x: freertos/event_groups.h (subset). Bits are 24 usable bits (EventBits_t is a 32-bit TickType_t, the top byte is kernel control). */
#pragma once

#ifndef INC_FREERTOS_H
#error "include FreeRTOS.h" must appear in source files before "include event_groups.h"
#endif

#ifdef __cplusplus
extern "C" {
#endif

typedef struct EventGroupDef_t * EventGroupHandle_t;
typedef TickType_t EventBits_t;

EventGroupHandle_t xEventGroupCreate( void );
EventBits_t xEventGroupWaitBits( EventGroupHandle_t xEventGroup,
                                 const EventBits_t uxBitsToWaitFor,
                                 const BaseType_t xClearOnExit,
                                 const BaseType_t xWaitForAllBits,
                                 TickType_t xTicksToWait );
EventBits_t xEventGroupSetBits( EventGroupHandle_t xEventGroup,
                                const EventBits_t uxBitsToSet );
EventBits_t xEventGroupClearBits( EventGroupHandle_t xEventGroup,
                                  const EventBits_t uxBitsToClear );
void vEventGroupDelete( EventGroupHandle_t xEventGroup );

#ifdef __cplusplus
}
#endif
