// Internal interfaces shared by the simulator's translation units.
#pragma once

#include <cstdint>
#include <functional>
#include <istream>
#include <ostream>
#include <string>
#include <vector>

#include "esp_err.h"
#include "freertos/FreeRTOS.h"
#include "freertos/task.h"
#include "json.h"

namespace sim {

// trace.cpp: one JSON object per line on trace_fd, written when the Event is destroyed.
// main points trace_fd at the original stdout and sends fd 1 to stderr, so learner output
// (printf, std::cout, write(1, ...)) can neither break nor forge the trace.
extern int trace_fd;
// JSON text must be UTF-8: bytes that are not valid UTF-8 are shown as the Latin-1 characters they would be.
// Every trace field that carries learner or network bytes goes through it.
std::string utf8(const std::string &s);

class Event {
public:
    Event(int64_t t_ms, const char *ev);
    Event &str(const char *key, const std::string &value);
    Event &num(const char *key, int64_t value);
    Event &flag(const char *key, bool value);
    ~Event();

private:
    std::string line_;
};

// sched.cpp: baton-passing scheduler over real threads, with a virtual clock.
[[noreturn]] void start(TaskFunction_t main_task, int64_t max_ms, int64_t start_ms);
TaskHandle_t create(TaskFunction_t fn, const char *name, void *arg, uint32_t stack, UBaseType_t priority);
void delay(TickType_t ticks);
void remove(TaskHandle_t task);  // nullptr: the calling task; never returns then
TickType_t ticks();              // since the current boot, like xTaskGetTickCount
uint64_t ticks64();              // since the start of the run, never restarts
int64_t boot_ms();               // run time at which the current boot began
// Simulator-internal tasks (event loop, MQTT client, timeline): they run like any task but task_create
// does not trace them. They are stopped like the rest by a restart.
TaskHandle_t create_hidden(TaskFunction_t fn, const char *name, void *arg);
TaskHandle_t current_task();
const std::string &name_of(TaskHandle_t task);
int64_t now_ms();                // lock-free, safe from a signal handler
[[noreturn]] void end(const char *reason);
const std::string &current_name();
// Waits on a kernel object (queue.cpp): blocks the calling task until ready() is true or `ticks`
// elapse; ready() runs with the scheduler lock held. With ticks == 0 it never gives the baton away.
bool wait_for(const void *object, TickType_t ticks, const std::function<bool()> &ready);
void notify(const void *object);  // the first task waiting on object becomes runnable at the current tick

// gpio.cpp: validates and loads the "gpio_in" scenario section. False with err set when malformed.
bool gpio_load_scenario(const Json &scenario, std::string &err);
// The level a pin drives (0 when it is not an output): what a relay sees, unlike gpio_get_level.
int gpio_driven_level(int pin);

// adc.cpp, i2c.cpp, plant.cpp: validate and load the "adc", "i2c" and "plant" scenario sections.
bool adc_load_scenario(const Json &scenario, std::string &err);
bool i2c_load_scenario(const Json &scenario, std::string &err);
bool plant_load_scenario(const Json &scenario, std::string &err);

// Half-open time window [from, to) in ms, as in the "nack" and "stuck" scenario lists (plant.cpp).
struct Window { int64_t from_ms, to_ms; };
// Parses an optional list of {"from_ms", "to_ms"} (null list: none). False with err set when malformed.
bool parse_windows(const Json *list, const char *where, std::vector<Window> &out, std::string &err);

// plant.cpp: the tank level is integrated lazily and exactly (int64) up to now_ms, at every sample
// and before every pin change, so the relay level is constant between two integration points.
void plant_sync();
bool plant_sample(int channel, int64_t &raw);  // true when `channel` is the tank sensor; raw is 0..4095

// timeline.cpp: actions at a virtual time. fn runs in the hidden task "sim_hw" (holding the baton, so it may
// post events and wake tasks, but must not block) at the first tick >= t_ms (at once when already past).
void at(int64_t t_ms, std::function<void()> fn);

// Restarts (boot.cpp). A restart re-executes the simulator binary: the learner's program really starts again
// (statics, heap, tasks and peripherals are fresh), and only what survives a reset on the chip is handed over
// through a memfd: the run clock, the reset reason, the committed NVS, the tank, the Wi-Fi attempt counter.
bool boot_load_scenario(const Json &scenario, std::string &err);  // "reboots_at_ms"
void boot_args(int argc, char **argv);
// Reads the state left by the previous boot (no-op on the first one). Sets the trace fd and returns the run time.
int64_t boot_restore();
void boot_begin();                                                // from the main task, before app_main
[[noreturn]] void reboot(const char *why);                        // "sw", "task_wdt" or "scripted"

// Handed-over state: one "<key> <values>" line per item.
void plant_save(std::ostream &out);
void plant_restore(std::istream &in);
bool nvs_ready();  // nvs_flash_init was called in this boot (and not undone)
void nvs_save(std::ostream &out);
void nvs_restore(const std::string &key, std::istream &in);
void wifi_save(std::ostream &out);
void wifi_restore(std::istream &in);

// event.cpp, wifi.cpp, mqtt.cpp: scenario sections, boot hooks and cross-module queries.
bool wifi_load_scenario(const Json &scenario, std::string &err);
bool mqtt_load_scenario(const Json &scenario, std::string &err);
void wifi_boot();
void mqtt_boot();
bool event_loop_ready();
bool wifi_in_use();   // esp_wifi_init was called in this boot
bool wifi_has_ip();
void mqtt_network_lost();

// tls.cpp, ota.cpp: scenario sections "tls", "ota" and "boot", and the TLS handshake that esp-mqtt and
// esp_https_ota share.
bool tls_load_scenario(const Json &scenario, std::string &err);
bool ota_load_scenario(const Json &scenario, std::string &err);
// What a client brings to the handshake: its verification options (certificate: PEM with its NUL, or DER; the
// certificate bundle or the global store; the name to check; skip_cert_common_name_check).
struct TlsPeer {
    bool has_cert = false, binary = false, public_store = false, skip_cn = false;
    std::string pem, common_name;
};
// verify: the label traced as "verify"; err, stack_err and flags: esp_tls_last_esp_err, esp_tls_stack_err and
// esp_tls_cert_verify_flags when !ok.
struct TlsResult { bool ok; esp_err_t err; int stack_err, flags; std::string verify; };
TlsPeer tls_peer(const char *cert, size_t cert_len, bool bundle, bool global_store, bool skip_cn, const char *common_name);
TlsResult tls_handshake(const TlsPeer &peer, const std::string &host);  // traces "tls_handshake"
std::string uri_host(const std::string &uri);

// The flash survives a reset: slots, versions and image states are handed over like the NVS (boot.cpp).
void ota_save(std::ostream &out);
void ota_restore(std::istream &in);
void ota_boot();                // the bootloader's part of a boot, before app_main
bool ota_self_test_broken();    // the running image is PENDING_VERIFY and the scenario says its self-test fails

// A broker/AP outage or a reconnect timer never needs more precision than a tick.
inline uint64_t tick_of(int64_t ms) { return static_cast<uint64_t>((ms + portTICK_PERIOD_MS - 1) / portTICK_PERIOD_MS); }

}  // namespace sim
