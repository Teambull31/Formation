// FreeRTOS event groups: 24 usable bits (the top byte of EventBits_t is kernel control, as in FreeRTOS).
// Blocking goes through the scheduler's wait_for/notify like queue.cpp: a task waiting costs no virtual
// time and wakes when a set satisfies it or at its timeout. As in FreeRTOS, xEventGroupSetBits releases
// every waiting task its bits satisfy, hands each the group value as it was at the set, and only then
// clears the bits of the tasks that asked for clear-on-exit (so two such waiters both see the bit).
// Not traced (a polling loop would flood the trace). Simplifications: the configASSERTs are aborts
// (no bits to wait for, or a control bit used); the handle must not be used after vEventGroupDelete
// nor deleted while a task waits on it (as for queues).
#include <algorithm>
#include <cstdlib>
#include <vector>

#include "sim.h"  // FreeRTOS.h first, as event_groups.h requires
#include "freertos/event_groups.h"

namespace {

constexpr EventBits_t kUsable = 0x00FFFFFF;

struct Waiter {
    EventBits_t wanted;
    bool all, clear_on_exit;
    bool released = false;
    EventBits_t seen = 0;
};

bool satisfied(EventBits_t bits, EventBits_t wanted, bool all) {
    return all ? (bits & wanted) == wanted : (bits & wanted) != 0;
}

}  // namespace

struct EventGroupDef_t {
    EventBits_t bits = 0;
    std::vector<Waiter *> waiters;
};

extern "C" {

EventGroupHandle_t xEventGroupCreate(void) { return new EventGroupDef_t; }

EventBits_t xEventGroupWaitBits(EventGroupHandle_t g, const EventBits_t wanted, const BaseType_t clear_on_exit,
                                const BaseType_t wait_for_all, TickType_t ticks) {
    if (wanted == 0 || (wanted & ~kUsable)) std::abort();
    if (satisfied(g->bits, wanted, wait_for_all)) {
        EventBits_t now = g->bits;
        if (clear_on_exit) g->bits &= ~wanted;
        return now;
    }
    if (ticks == 0) return g->bits;
    Waiter w{wanted, wait_for_all != pdFALSE, clear_on_exit != pdFALSE};
    g->waiters.push_back(&w);
    sim::wait_for(&w, ticks, [&] { return w.released; });
    g->waiters.erase(std::find(g->waiters.begin(), g->waiters.end(), &w));
    if (w.released) return w.seen;  // the setter already did the clearing
    EventBits_t now = g->bits;  // timeout: the bits as they are now, nothing cleared unless they are right after all
    if (clear_on_exit && satisfied(now, wanted, wait_for_all)) g->bits &= ~wanted;
    return now;
}

EventBits_t xEventGroupSetBits(EventGroupHandle_t g, const EventBits_t to_set) {
    if (to_set & ~kUsable) std::abort();
    g->bits |= to_set;
    EventBits_t to_clear = 0;
    for (Waiter *w : g->waiters) {
        if (w->released || !satisfied(g->bits, w->wanted, w->all)) continue;
        w->released = true;
        w->seen = g->bits;
        if (w->clear_on_exit) to_clear |= w->wanted;
        sim::notify(w);
    }
    g->bits &= ~to_clear;
    return g->bits;
}

EventBits_t xEventGroupClearBits(EventGroupHandle_t g, const EventBits_t to_clear) {
    if (to_clear & ~kUsable) std::abort();
    EventBits_t before = g->bits;
    g->bits &= ~to_clear;
    return before;
}

void vEventGroupDelete(EventGroupHandle_t g) { delete g; }

}  // extern "C"
