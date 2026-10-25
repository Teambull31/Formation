// Restarts: esp_restart, the task watchdog's panic and the scenario's "reboots_at_ms" (power cycles).
//
// A restart re-executes the simulator binary with the same arguments, so the learner's program starts again
// from app_main with fresh statics, heap, tasks, GPIO, ADC and I2C state, as after a reset on the chip. What
// survives is handed over through a memfd (inherited across exec, read once by the next boot):
//   - the run clock (the trace keeps absolute times; xTaskGetTickCount and esp_timer_get_time restart at 0),
//   - the reset reason and the index of the next scripted restart,
//   - the committed NVS content (uncommitted writes are lost), the tank level, the Wi-Fi attempt counter.
// The scenario is parsed again by the new process. Trace event: "reboot" (reason sw | task_wdt | scripted).
// Reset reasons: esp_restart gives ESP_RST_SW, the task watchdog with trigger_panic ESP_RST_TASK_WDT, a
// scripted restart (a power cycle) and the first boot ESP_RST_POWERON.
//
// Simplifications: a restart takes no virtual time; stdio buffers of the learner's program are lost (the
// chip loses its RAM too); esp_register_shutdown_handler is not provided, so nothing runs before a restart;
// more than 50 restarts in a row without the clock moving end the run with "busy_loop" (a boot loop).
#include <sys/mman.h>
#include <unistd.h>

#include <algorithm>
#include <cstdlib>
#include <cstring>
#include <sstream>

#include "esp_log.h"
#include "esp_system.h"
#include "sim.h"

namespace {

constexpr int kMaxStreak = 50;

int saved_argc = 0;
char **saved_argv = nullptr;
std::string self_exe;
std::vector<int64_t> scripted;  // sorted
size_t next_scripted = 0;
int reason = ESP_RST_POWERON;
int streak = 0;  // consecutive restarts without the run clock moving

}  // namespace

namespace sim {

void boot_args(int argc, char **argv) {
    saved_argc = argc;
    saved_argv = argv;
    char buf[4096];
    ssize_t n = ::readlink("/proc/self/exe", buf, sizeof buf - 1);
    self_exe = n > 0 ? std::string(buf, static_cast<size_t>(n)) : argv[0];
}

bool boot_load_scenario(const Json &root, std::string &err) {
    const Json *list = root.get("reboots_at_ms");
    if (!list) return true;
    if (list->type != Json::Array) { err = "\"reboots_at_ms\" doit être un tableau"; return false; }
    std::vector<int64_t> times;
    for (const Json &e : list->arr) {
        long long t = 0;
        if (!e.as_int(0, INT64_MAX >> 12, t)) { err = "reboots_at_ms : entiers >= 0 attendus"; return false; }
        times.push_back(t);
    }
    std::sort(times.begin(), times.end());
    scripted = std::move(times);
    return true;
}

int64_t boot_restore() {
    const char *fd_text = std::getenv("ESPSIM_STATE_FD");
    const char *trace_text = std::getenv("ESPSIM_TRACE_FD");
    if (!fd_text || !trace_text) return -1;
    int fd = std::atoi(fd_text);
    trace_fd = std::atoi(trace_text);
    ::unsetenv("ESPSIM_STATE_FD");
    ::unsetenv("ESPSIM_TRACE_FD");
    std::string text;
    char buf[4096];
    ssize_t n;
    while ((n = ::read(fd, buf, sizeof buf)) > 0) text.append(buf, static_cast<size_t>(n));
    ::close(fd);
    int64_t start = 0;
    std::istringstream lines(text);
    std::string line;
    while (std::getline(lines, line)) {
        std::istringstream in(line);
        std::string key;
        in >> key;
        if (key == "boot.ms") in >> start;
        else if (key == "boot.reason") in >> reason;
        else if (key == "boot.next") in >> next_scripted;
        else if (key == "boot.streak") in >> streak;
        else if (key == "plant") plant_restore(in);
        else if (key == "wifi") wifi_restore(in);
        else if (key.compare(0, 4, "nvs.") == 0) nvs_restore(key, in);
    }
    return start;
}

void boot_begin() {
    if (next_scripted < scripted.size()) at(scripted[next_scripted], [] { reboot("scripted"); });
    wifi_boot();
    mqtt_boot();
}

void reboot(const char *why) {
    int64_t now = now_ms();
    Event(now, "reboot").str("reason", why);
    int next_reason = std::strcmp(why, "sw") == 0 ? ESP_RST_SW : std::strcmp(why, "task_wdt") == 0 ? ESP_RST_TASK_WDT : ESP_RST_POWERON;
    if (std::strcmp(why, "scripted") == 0) ++next_scripted;
    int next_streak = now == boot_ms() ? streak + 1 : 0;
    if (next_streak > kMaxStreak) end("busy_loop");
    plant_sync();  // integrate the tank with the relay level of this boot before the pins reset
    std::ostringstream out;
    out << "boot.ms " << now << "\nboot.reason " << next_reason << "\nboot.next " << next_scripted << "\nboot.streak " << next_streak << "\n";
    plant_save(out);
    wifi_save(out);
    nvs_save(out);
    std::string state = out.str();
    int fd = ::memfd_create("espsim", 0);
    bool ok = fd >= 0;
    for (size_t off = 0; ok && off < state.size();) {
        ssize_t n = ::write(fd, state.data() + off, state.size() - off);
        if (n <= 0) ok = false;
        else off += static_cast<size_t>(n);
    }
    if (ok && ::lseek(fd, 0, SEEK_SET) == 0) {
        ::setenv("ESPSIM_STATE_FD", std::to_string(fd).c_str(), 1);
        ::setenv("ESPSIM_TRACE_FD", std::to_string(trace_fd).c_str(), 1);
        ::execv(self_exe.c_str(), saved_argv);
    }
    Event(now, "log").str("level", "E").str("tag", "esp_restart").str("msg", "the simulator could not restart itself");
    end("abort");
}

}  // namespace sim

extern "C" {

void esp_restart(void) { sim::reboot("sw"); }

esp_reset_reason_t esp_reset_reason(void) { return static_cast<esp_reset_reason_t>(reason); }

}  // extern "C"
