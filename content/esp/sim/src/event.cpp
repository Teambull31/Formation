// esp_event.h shim: the default event loop. Posts are queued (32 entries, CONFIG_ESP_SYSTEM_EVENT_QUEUE_SIZE)
// and delivered by the loop task "sys_evt", which calls the handlers in registration order, loop-level
// (ANY_BASE) first, then base-level (ANY_ID), then event-level. Event data is copied at post time.
//
// Simplifications: only the default loop (no esp_event_loop_create / post_to / run); the handler tiers
// above are the sim's reading of the docs' "registration order" rule; a handler removed while an event is
// being dispatched still sees that event; unregistering a handler that was never registered returns ESP_OK.
#include <deque>
#include <memory>
#include <vector>

#include "esp_event.h"
#include "sim.h"

namespace {

constexpr size_t kQueueSize = 32;

struct Registration {
    esp_event_base_t base;
    int32_t id;
    esp_event_handler_t fn;
    void *arg;
};

struct Posted {
    esp_event_base_t base;
    int32_t id;
    std::vector<unsigned char> data;
    bool has_data;
};

bool loop_on = false;
std::vector<std::unique_ptr<Registration>> registrations;  // registration order
std::deque<Posted> queue;
TaskHandle_t loop_task = nullptr;
char item_key = 0, room_key = 0;

bool valid_combination(esp_event_base_t base, int32_t id) { return base != ESP_EVENT_ANY_BASE || id == ESP_EVENT_ANY_ID; }

void dispatch(Posted &p) {
    void *data = p.has_data ? p.data.data() : nullptr;
    // snapshot: a handler may register or unregister handlers
    std::vector<Registration> snapshot;
    for (int tier = 0; tier < 3; ++tier) {
        for (auto &r : registrations) {
            bool match = tier == 0 ? r->base == ESP_EVENT_ANY_BASE
                       : tier == 1 ? r->base == p.base && r->id == ESP_EVENT_ANY_ID && p.base != ESP_EVENT_ANY_BASE
                                   : r->base == p.base && r->id == p.id && r->id != ESP_EVENT_ANY_ID;
            if (match) snapshot.push_back(*r);
        }
    }
    for (auto &r : snapshot) r.fn(r.arg, p.base, p.id, data);
}

void loop_main(void *) {
    for (;;) {
        sim::wait_for(&item_key, portMAX_DELAY, [] { return !queue.empty(); });
        Posted p = std::move(queue.front());
        queue.pop_front();
        sim::notify(&room_key);
        dispatch(p);
    }
}

Registration *find(esp_event_base_t base, int32_t id, esp_event_handler_t fn) {
    for (auto &r : registrations) if (r->base == base && r->id == id && r->fn == fn) return r.get();
    return nullptr;
}

}  // namespace

namespace sim {
bool event_loop_ready() { return loop_on; }
}  // namespace sim

extern "C" {

esp_err_t esp_event_loop_create_default(void) {
    if (loop_on) return ESP_ERR_INVALID_STATE;
    loop_on = true;
    loop_task = sim::create_hidden(loop_main, "sys_evt", nullptr);
    return ESP_OK;
}

esp_err_t esp_event_loop_delete_default(void) {
    if (!loop_on) return ESP_ERR_INVALID_STATE;
    loop_on = false;
    registrations.clear();
    queue.clear();
    sim::remove(loop_task);
    loop_task = nullptr;
    return ESP_OK;
}

esp_err_t esp_event_handler_instance_register(esp_event_base_t event_base, int32_t event_id, esp_event_handler_t event_handler,
                                              void *event_handler_arg, esp_event_handler_instance_t *instance) {
    if (!loop_on) return ESP_ERR_INVALID_STATE;
    if (!event_handler || !instance || !valid_combination(event_base, event_id)) return ESP_ERR_INVALID_ARG;
    registrations.push_back(std::make_unique<Registration>(Registration{event_base, event_id, event_handler, event_handler_arg}));
    *instance = registrations.back().get();
    return ESP_OK;
}

// As in ESP-IDF, registering the same (base, id, handler) again only replaces its argument.
esp_err_t esp_event_handler_register(esp_event_base_t event_base, int32_t event_id, esp_event_handler_t event_handler, void *event_handler_arg) {
    if (!loop_on) return ESP_ERR_INVALID_STATE;
    if (!event_handler || !valid_combination(event_base, event_id)) return ESP_ERR_INVALID_ARG;
    if (Registration *r = find(event_base, event_id, event_handler)) {
        r->arg = event_handler_arg;
        return ESP_OK;
    }
    registrations.push_back(std::make_unique<Registration>(Registration{event_base, event_id, event_handler, event_handler_arg}));
    return ESP_OK;
}

esp_err_t esp_event_handler_unregister(esp_event_base_t event_base, int32_t event_id, esp_event_handler_t event_handler) {
    if (!loop_on) return ESP_ERR_INVALID_STATE;
    if (!event_handler || !valid_combination(event_base, event_id)) return ESP_ERR_INVALID_ARG;
    for (auto it = registrations.begin(); it != registrations.end(); ++it) {
        if ((*it)->base == event_base && (*it)->id == event_id && (*it)->fn == event_handler) {
            registrations.erase(it);
            break;
        }
    }
    return ESP_OK;
}

esp_err_t esp_event_handler_instance_unregister(esp_event_base_t event_base, int32_t event_id, esp_event_handler_instance_t instance) {
    if (!loop_on) return ESP_ERR_INVALID_STATE;
    if (!instance || !valid_combination(event_base, event_id)) return ESP_ERR_INVALID_ARG;
    for (auto it = registrations.begin(); it != registrations.end(); ++it) {
        if (it->get() == instance && (*it)->base == event_base && (*it)->id == event_id) {
            registrations.erase(it);
            return ESP_OK;
        }
    }
    return ESP_ERR_INVALID_ARG;
}

esp_err_t esp_event_post(esp_event_base_t event_base, int32_t event_id, const void *event_data, size_t event_data_size, TickType_t ticks_to_wait) {
    if (!loop_on) return ESP_ERR_INVALID_STATE;
    if (event_base == ESP_EVENT_ANY_BASE || (event_data_size > 0 && !event_data)) return ESP_ERR_INVALID_ARG;
    if (!sim::wait_for(&room_key, ticks_to_wait, [] { return queue.size() < kQueueSize; })) return ESP_ERR_TIMEOUT;
    Posted p{event_base, event_id, {}, event_data_size > 0};
    if (event_data_size > 0) {
        auto *b = static_cast<const unsigned char *>(event_data);
        p.data.assign(b, b + event_data_size);
    }
    queue.push_back(std::move(p));
    sim::notify(&item_key);
    return ESP_OK;
}

}  // extern "C"
