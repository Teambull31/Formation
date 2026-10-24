// Internal interfaces shared by the simulator's translation units.
#pragma once

#include <cstdint>
#include <string>

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
TaskHandle_t create(TaskFunction_t fn, const char *name, void *arg);
void delay(TickType_t ticks);
void remove(TaskHandle_t task);  // nullptr: the calling task; never returns then
TickType_t ticks();
int64_t now_ms();                // lock-free, safe from a signal handler
[[noreturn]] void end(const char *reason);

// gpio.cpp: validates and loads the "gpio_in" scenario section. False with err set when malformed.
bool gpio_load_scenario(const Json &scenario, std::string &err);

}  // namespace sim
