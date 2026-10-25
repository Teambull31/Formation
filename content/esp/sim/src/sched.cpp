// One real thread per task, but only the task holding the baton (`current`) runs.
// A task gives the baton away only in a blocking call; the next task is the one
// with the earliest wake tick (ties: first to block), and the virtual clock jumps
// to that tick. This makes every run identical. Wake ticks are 64-bit, so even
// portMAX_DELAY lands far past any run's deadline instead of wrapping around.
#include <unistd.h>

#include <atomic>
#include <chrono>
#include <condition_variable>
#include <memory>
#include <mutex>
#include <thread>
#include <vector>

#include "sim.h"

struct tskTaskControlBlock {
    std::string name;
    TaskFunction_t fn;
    void *arg;
    uint64_t wake = 0;
    uint64_t seq = 0;
    bool alive = true;
    const void *waiting_on = nullptr;  // kernel object this task is blocked on, if any
    std::condition_variable cv;
};

namespace sim {
namespace {

using Clock = std::chrono::steady_clock;
constexpr auto kBusyLimit = std::chrono::milliseconds(1000);  // real time without clock advance before busy_loop

std::mutex m;
std::vector<std::unique_ptr<tskTaskControlBlock>> tasks;  // never shrinks: handles stay valid
tskTaskControlBlock *current = nullptr;
std::atomic<uint64_t> now{0};
uint64_t next_seq = 0;
Clock::time_point clock_moved_at;  // last real time the virtual clock advanced
int64_t max_ms = 0;
tskTaskControlBlock *main_task_tcb = nullptr;

int64_t to_ms(uint64_t t) { return static_cast<int64_t>(t) * portTICK_PERIOD_MS; }

[[noreturn]] void end_at(int64_t t_ms, const char *reason, const char *task = nullptr) {
    {
        Event e(t_ms, "end");
        e.str("reason", reason);
        if (task) e.str("task", task);
    }
    _exit(std::string(reason) == "deadline" ? 0 : 1);
}

[[noreturn]] void park(std::unique_lock<std::mutex> &lk, tskTaskControlBlock *self) {
    for (;;) self->cv.wait(lk);
}

// Called with `m` held by the task giving the baton away.
void switch_from(std::unique_lock<std::mutex> &lk, tskTaskControlBlock *self) {
    tskTaskControlBlock *next = nullptr;
    for (auto &t : tasks) {
        if (t->alive && (!next || t->wake < next->wake || (t->wake == next->wake && t->seq < next->seq)))
            next = t.get();
    }
    if (!next || next->wake > static_cast<uint64_t>(max_ms) / portTICK_PERIOD_MS) end_at(max_ms, "deadline");
    if (next->wake > now) {
        now = next->wake;
        clock_moved_at = Clock::now();
    }
    current = next;
    if (next == self) return;
    next->cv.notify_one();
    if (!self->alive) return;
    self->cv.wait(lk, [&] { return current == self; });
}

void entry(tskTaskControlBlock *self) {
    {
        std::unique_lock<std::mutex> lk(m);
        self->cv.wait(lk, [&] { return current == self; });
    }
    self->fn(self->arg);
    if (self == main_task_tcb) remove(nullptr);  // ESP-IDF deletes the main task when app_main returns
    // Any other task returning is fatal in ESP-IDF v5 (FreeRTOS port's task exit handler).
    Event(to_ms(now), "log").str("level", "E").str("tag", "FreeRTOS")
        .str("msg", "FreeRTOS Task \"" + self->name + "\" should not return, Aborting now!");
    end("abort");
}

// stack < 0: the main task, whose stack comes from sdkconfig, not from xTaskCreate.
tskTaskControlBlock *create_locked(TaskFunction_t fn, const char *name, void *arg, int64_t stack = -1,
                                   UBaseType_t priority = 0) {
    auto t = std::make_unique<tskTaskControlBlock>();
    t->name = name ? name : "";
    t->fn = fn;
    t->arg = arg;
    t->wake = now;
    t->seq = next_seq++;
    tskTaskControlBlock *raw = t.get();
    tasks.push_back(std::move(t));
    {
        Event e(to_ms(now), "task_create");
        e.str("name", raw->name);
        if (stack >= 0) e.num("stack", stack).num("priority", priority);
    }
    std::thread(entry, raw).detach();
    return raw;
}

}  // namespace

void start(TaskFunction_t main_task, int64_t limit_ms) {
    std::unique_lock<std::mutex> lk(m);
    max_ms = limit_ms;
    current = main_task_tcb = create_locked(main_task, "main", nullptr);
    clock_moved_at = Clock::now();
    current->cv.notify_one();
    for (;;) {  // this thread becomes the busy-loop watchdog
        lk.unlock();
        std::this_thread::sleep_for(std::chrono::milliseconds(20));
        lk.lock();
        if (Clock::now() - clock_moved_at > kBusyLimit) end_at(to_ms(now), "busy_loop", current->name.c_str());
    }
}

TaskHandle_t create(TaskFunction_t fn, const char *name, void *arg, uint32_t stack, UBaseType_t priority) {
    std::lock_guard<std::mutex> lk(m);
    return create_locked(fn, name, arg, stack, priority);
}

const std::string &current_name() { return current->name; }

bool wait_for(const void *object, TickType_t ticks, const std::function<bool()> &ready) {
    std::unique_lock<std::mutex> lk(m);
    tskTaskControlBlock *self = current;
    const uint64_t deadline = now + ticks;
    while (!ready()) {  // woken but beaten to the item (or the room): wait again until the deadline
        if (now >= deadline) return false;
        self->wake = deadline;
        self->seq = next_seq++;
        self->waiting_on = object;
        switch_from(lk, self);
        self->waiting_on = nullptr;
    }
    return true;
}

void notify(const void *object) {
    std::lock_guard<std::mutex> lk(m);
    tskTaskControlBlock *first = nullptr;
    for (auto &t : tasks) {
        if (t->alive && t->waiting_on == object && (!first || t->seq < first->seq)) first = t.get();
    }
    if (!first) return;
    first->waiting_on = nullptr;
    first->wake = now;
    first->seq = next_seq++;
}

void delay(TickType_t ticks) {
    std::unique_lock<std::mutex> lk(m);
    tskTaskControlBlock *self = current;
    self->wake = now + ticks;
    self->seq = next_seq++;
    switch_from(lk, self);
}

void remove(TaskHandle_t task) {
    std::unique_lock<std::mutex> lk(m);
    tskTaskControlBlock *self = current;
    tskTaskControlBlock *victim = task ? task : self;
    victim->alive = false;
    if (victim != self) return;  // the victim is parked in a wait it will never leave
    switch_from(lk, self);
    park(lk, self);
}

TickType_t ticks() { return static_cast<TickType_t>(now); }  // wraps like the real counter

int64_t now_ms() { return to_ms(now); }

void end(const char *reason) {
    std::lock_guard<std::mutex> lk(m);
    end_at(to_ms(now), reason);
}

}  // namespace sim
