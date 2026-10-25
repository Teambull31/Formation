// Virtual-time actions for the scenario-driven parts (Wi-Fi, MQTT broker, watchdog, scripted restarts).
// One hidden task, "sim_hw", sleeps until the earliest action and runs it at that tick, with the baton, so
// actions interleave with the learner's tasks exactly like any other task wake-up: deterministic, and with
// the same tick resolution (10 ms). Actions with the same tick run in the order they were added.
// Simplification: the task is created on first use, so programs that never touch these features keep the
// thread budget of the sandbox (a hidden task is a real thread).
#include <map>
#include <utility>

#include "sim.h"

namespace {

using Key = std::pair<uint64_t, uint64_t>;  // tick, insertion number
std::map<Key, std::function<void()>> actions;
uint64_t next_number = 0;
bool dirty = false;
char wake_key = 0;
TaskHandle_t hw = nullptr;

void hw_main(void *) {
    for (;;) {
        while (!actions.empty() && actions.begin()->first.first <= sim::ticks64()) {
            auto fn = std::move(actions.begin()->second);
            actions.erase(actions.begin());
            fn();
        }
        dirty = false;
        TickType_t wait = portMAX_DELAY;
        if (!actions.empty()) {
            uint64_t d = actions.begin()->first.first - sim::ticks64();
            wait = d > 0xfffffffeu ? 0xfffffffeu : static_cast<TickType_t>(d);
        }
        sim::wait_for(&wake_key, wait, [] { return dirty; });
    }
}

}  // namespace

namespace sim {

void at(int64_t t_ms, std::function<void()> fn) {
    actions.emplace(Key{tick_of(t_ms), next_number++}, std::move(fn));
    dirty = true;
    if (!hw) hw = create_hidden(hw_main, "sim_hw", nullptr);
    else notify(&wake_key);
}

}  // namespace sim
