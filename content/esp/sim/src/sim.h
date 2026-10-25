// Internal interfaces shared by the simulator's translation units.
#pragma once

#include <cstdint>
#include <functional>
#include <string>
#include <vector>

#include "freertos/FreeRTOS.h"
#include "freertos/task.h"
#include "json.h"

namespace sim {

// trace.cpp: one JSON object per line on trace_fd, written when the Event is destroyed.
// main points trace_fd at the original stdout and sends fd 1 to stderr, so learner output
// (printf, std::cout, write(1, ...)) can neither break nor forge the trace.
extern int trace_fd;

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
[[noreturn]] void start(TaskFunction_t main_task, int64_t max_ms);
TaskHandle_t create(TaskFunction_t fn, const char *name, void *arg, uint32_t stack, UBaseType_t priority);
void delay(TickType_t ticks);
void remove(TaskHandle_t task);  // nullptr: the calling task; never returns then
TickType_t ticks();
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

}  // namespace sim
