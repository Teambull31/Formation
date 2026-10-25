// FreeRTOS queues: fixed-size items copied in and out, FIFO. Blocking goes through the scheduler's
// wait_for/notify, so a task waiting on a queue costs no virtual time and wakes on the send (or the
// receive that makes room) or at its timeout. Only the baton holder runs, so the item storage needs
// no lock of its own. Trace: every queue creation and successful send/receive, and failed ones that
// waited; a failed zero-wait call is not traced (a polling loop would flood the trace).
#include <cstring>
#include <deque>
#include <vector>

#include "sim.h"  // FreeRTOS.h first, as queue.h requires
#include "freertos/queue.h"

struct QueueDefinition {
    int64_t id;
    UBaseType_t length;
    UBaseType_t item_size;
    std::deque<std::vector<unsigned char>> items;
    char item_key = 0;  // address receivers wait on
    char room_key = 0;  // address senders wait on
};

namespace {

int64_t next_id = 1;

void trace_op(const char *ev, QueueHandle_t q, bool ok, TickType_t waited) {
    if (!ok && waited == 0) return;
    sim::Event(sim::now_ms(), ev).num("queue", q->id).str("task", sim::current_name()).flag("ok", ok);
}

}  // namespace

extern "C" {

QueueHandle_t xQueueGenericCreate(const UBaseType_t uxQueueLength, const UBaseType_t uxItemSize, const uint8_t) {
    if (uxQueueLength == 0) return nullptr;  // FreeRTOS asserts on a zero length
    auto *q = new QueueDefinition{next_id++, uxQueueLength, uxItemSize, {}};
    sim::Event(sim::now_ms(), "queue_create").num("queue", q->id).num("length", uxQueueLength).num("item_size", uxItemSize);
    return q;
}

// Only queueSEND_TO_BACK is exposed (xQueueSend, xQueueSendToBack).
BaseType_t xQueueGenericSend(QueueHandle_t xQueue, const void *const pvItemToQueue, TickType_t xTicksToWait,
                             const BaseType_t) {
    bool ok = sim::wait_for(&xQueue->room_key, xTicksToWait, [&] { return xQueue->items.size() < xQueue->length; });
    if (ok) {
        auto *p = static_cast<const unsigned char *>(pvItemToQueue);
        xQueue->items.emplace_back(p, p + xQueue->item_size);
        sim::notify(&xQueue->item_key);
    }
    trace_op("queue_send", xQueue, ok, xTicksToWait);
    return ok ? pdTRUE : errQUEUE_FULL;
}

BaseType_t xQueueReceive(QueueHandle_t xQueue, void *const pvBuffer, TickType_t xTicksToWait) {
    bool ok = sim::wait_for(&xQueue->item_key, xTicksToWait, [&] { return !xQueue->items.empty(); });
    if (ok) {
        std::memcpy(pvBuffer, xQueue->items.front().data(), xQueue->item_size);
        xQueue->items.pop_front();
        sim::notify(&xQueue->room_key);
    }
    trace_op("queue_receive", xQueue, ok, xTicksToWait);
    return ok ? pdTRUE : pdFALSE;
}

UBaseType_t uxQueueMessagesWaiting(const QueueHandle_t xQueue) { return static_cast<UBaseType_t>(xQueue->items.size()); }

// As in FreeRTOS, the handle must not be used afterwards, nor the queue deleted while a task waits on it.
void vQueueDelete(QueueHandle_t xQueue) { delete xQueue; }

}  // extern "C"
