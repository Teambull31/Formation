// esp_task_wdt.h shim: the task watchdog (TWDT).
//
// Documented behaviour reproduced: the TWDT is already initialised at boot (CONFIG_ESP_TASK_WDT_INIT),
// timeout CONFIG_ESP_TASK_WDT_TIMEOUT_S = 5 s, idle_core_mask 3, trigger_panic false: so esp_task_wdt_init
// returns ESP_ERR_INVALID_STATE until esp_task_wdt_deinit, and an application changes the settings with
// esp_task_wdt_reconfigure. The timer only runs while a task is subscribed. A subscribed task must call
// esp_task_wdt_reset; the timeout window restarts when every subscribed task has done so since the last restart.
// When it expires, the watchdog logs the tasks that did not reset it ("task_wdt" error lines) and
//   - trigger_panic false (the default): continues, and repeats every timeout while a task stays silent;
//   - trigger_panic true: resets the chip, reset reason ESP_RST_TASK_WDT.
// Trace: "wdt_reset" (tasks = names of the tasks that did not reset it, comma separated, panic = the
// configuration) at each expiry, then "reboot" (reason task_wdt) when it panics.
//
// Simplifications: the idle tasks are not modelled (the sim has no idle task, and a task spinning without
// blocking ends the run with busy_loop anyway); esp_task_wdt_add and a changed configuration restart the
// timeout window; a task deleted without esp_task_wdt_delete stays subscribed and is reported by name;
// the "users" API (esp_task_wdt_add_user and friends) and the backtrace lines are not provided;
// the repetition without panic is the sim's reading of the docs ("print a warning ... before continuing").
#include <algorithm>

#include "esp_log.h"
#include "esp_task_wdt.h"
#include "sim.h"

namespace {

struct Sub {
    TaskHandle_t task;
    bool fed = false;
};

bool inited = true;  // CONFIG_ESP_TASK_WDT_INIT
esp_task_wdt_config_t config = {5000, 3, false};
std::vector<Sub> subs;
int64_t deadline_ms = 0;
bool check_pending = false;
uint64_t generation = 0;  // checks scheduled before a deinit die

Sub *find(TaskHandle_t t) {
    for (auto &s : subs) if (s.task == t) return &s;
    return nullptr;
}

void arm();

void restart_window() { deadline_ms = sim::now_ms() + config.timeout_ms; }

void check(uint64_t gen) {
    if (gen != generation) return;
    check_pending = false;
    if (!inited || subs.empty()) return;
    if (sim::now_ms() < deadline_ms) { arm(); return; }
    std::string names;
    for (auto &s : subs) {
        if (s.fed) continue;
        names += (names.empty() ? "" : ",") + sim::name_of(s.task);
    }
    ESP_LOGE("task_wdt", "Task watchdog got triggered. The following tasks/users did not reset the watchdog in time:");
    for (auto &s : subs) if (!s.fed) ESP_LOGE("task_wdt", " - %s (CPU 0)", sim::name_of(s.task).c_str());
    sim::Event(sim::now_ms(), "wdt_reset").str("tasks", names).flag("panic", config.trigger_panic);
    if (config.trigger_panic) sim::reboot("task_wdt");
    restart_window();
    arm();
}

void arm() {
    if (check_pending || !inited || subs.empty()) return;
    check_pending = true;
    uint64_t gen = generation;
    sim::at(deadline_ms, [gen] { check(gen); });
}

esp_err_t resolve(TaskHandle_t t, TaskHandle_t &out) {
    if (!inited) return ESP_ERR_INVALID_STATE;
    out = t ? t : sim::current_task();
    return ESP_OK;
}

}  // namespace

extern "C" {

esp_err_t esp_task_wdt_init(const esp_task_wdt_config_t *c) {
    if (!c || c->timeout_ms == 0) return ESP_ERR_INVALID_ARG;
    if (inited) return ESP_ERR_INVALID_STATE;
    inited = true;
    config = *c;
    return ESP_OK;
}

esp_err_t esp_task_wdt_reconfigure(const esp_task_wdt_config_t *c) {
    if (!inited) return ESP_ERR_INVALID_STATE;
    if (!c || c->timeout_ms == 0) return ESP_ERR_INVALID_ARG;
    config = *c;
    if (!subs.empty()) { restart_window(); arm(); }
    return ESP_OK;
}

esp_err_t esp_task_wdt_deinit(void) {
    if (!inited || !subs.empty()) return ESP_ERR_INVALID_STATE;
    inited = false;
    ++generation;
    check_pending = false;
    return ESP_OK;
}

esp_err_t esp_task_wdt_add(TaskHandle_t task_handle) {
    TaskHandle_t t;
    if (esp_err_t e = resolve(task_handle, t)) return e;
    if (find(t)) return ESP_ERR_INVALID_ARG;
    subs.push_back({t, false});
    restart_window();
    arm();
    return ESP_OK;
}

esp_err_t esp_task_wdt_reset(void) {
    TaskHandle_t t;
    if (esp_err_t e = resolve(nullptr, t)) return e;
    Sub *s = find(t);
    if (!s) return ESP_ERR_NOT_FOUND;
    s->fed = true;
    if (std::all_of(subs.begin(), subs.end(), [](const Sub &x) { return x.fed; })) {
        for (auto &x : subs) x.fed = false;
        restart_window();
    }
    return ESP_OK;
}

esp_err_t esp_task_wdt_delete(TaskHandle_t task_handle) {
    TaskHandle_t t;
    if (esp_err_t e = resolve(task_handle, t)) return e;
    for (auto it = subs.begin(); it != subs.end(); ++it) {
        if (it->task != t) continue;
        subs.erase(it);
        if (!subs.empty() && std::all_of(subs.begin(), subs.end(), [](const Sub &x) { return x.fed; })) {
            for (auto &x : subs) x.fed = false;
            restart_window();
        }
        return ESP_OK;
    }
    return ESP_ERR_NOT_FOUND;
}

esp_err_t esp_task_wdt_status(TaskHandle_t task_handle) {
    TaskHandle_t t;
    if (esp_err_t e = resolve(task_handle, t)) return e;
    return find(t) ? ESP_OK : ESP_ERR_NOT_FOUND;
}

}  // extern "C"
