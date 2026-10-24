// One real thread per task, but only the task holding the baton (`current`) runs.
// A task gives the baton away only in a blocking call; the next task is the one
// with the earliest wake tick (ties: first to block), and the virtual clock jumps
// to that tick. This makes every run identical.
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
    TickType_t wake = 0;
    uint64_t seq = 0;
    bool alive = true;
    std::condition_variable cv;
};

namespace sim {
namespace {

using Clock = std::chrono::steady_clock;
constexpr auto kBusyLimit = std::chrono::milliseconds(1000);  // real time per slice before busy_loop

std::mutex m;
std::vector<std::unique_ptr<tskTaskControlBlock>> tasks;  // never shrinks: handles stay valid
tskTaskControlBlock *current = nullptr;
std::atomic<TickType_t> now{0};
uint64_t next_seq = 0;
Clock::time_point slice_start;
int64_t max_ms = 0;

int64_t to_ms(TickType_t t) { return static_cast<int64_t>(t) * portTICK_PERIOD_MS; }

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
    if (!next || to_ms(next->wake) > max_ms) end_at(max_ms, "deadline");
    if (next->wake > now) now = next->wake;
    current = next;
    slice_start = Clock::now();
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
    remove(nullptr);  // a task that returns is deleted, like app_main's task in ESP-IDF
}

tskTaskControlBlock *create_locked(TaskFunction_t fn, const char *name, void *arg) {
    auto t = std::make_unique<tskTaskControlBlock>();
    t->name = name ? name : "";
    t->fn = fn;
    t->arg = arg;
    t->wake = now;
    t->seq = next_seq++;
    tskTaskControlBlock *raw = t.get();
    tasks.push_back(std::move(t));
    Event(to_ms(now), "task_create").str("name", raw->name);
    std::thread(entry, raw).detach();
    return raw;
}

}  // namespace

void start(TaskFunction_t main_task, int64_t limit_ms) {
    std::unique_lock<std::mutex> lk(m);
    max_ms = limit_ms;
    current = create_locked(main_task, "main", nullptr);
    slice_start = Clock::now();
    current->cv.notify_one();
    for (;;) {  // this thread becomes the busy-loop watchdog
        lk.unlock();
        std::this_thread::sleep_for(std::chrono::milliseconds(20));
        lk.lock();
        if (Clock::now() - slice_start > kBusyLimit) end_at(to_ms(now), "busy_loop", current->name.c_str());
    }
}

TaskHandle_t create(TaskFunction_t fn, const char *name, void *arg) {
    std::lock_guard<std::mutex> lk(m);
    return create_locked(fn, name, arg);
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

TickType_t ticks() { return now; }

int64_t now_ms() { return to_ms(now); }

void end(const char *reason) {
    std::lock_guard<std::mutex> lk(m);
    end_at(to_ms(now), reason);
}

}  // namespace sim
