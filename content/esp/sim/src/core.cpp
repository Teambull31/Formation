// ESP-IDF API shims (esp_err, esp_log, esp_timer, FreeRTOS tasks) and the harness `main`.
#include <signal.h>
#include <unistd.h>

#include <cstdarg>
#include <cstdio>
#include <cstdlib>
#include <cstring>
#include <fstream>
#include <iterator>

#include "esp_err.h"
#include "esp_log.h"
#include "esp_timer.h"
#include "sim.h"

extern "C" void app_main(void);

extern "C" {

const char *esp_err_to_name(esp_err_t code) {
    switch (code) {
        case ESP_OK: return "ESP_OK";
        case ESP_FAIL: return "ESP_FAIL";
        case ESP_ERR_INVALID_ARG: return "ESP_ERR_INVALID_ARG";
        case ESP_ERR_NOT_FOUND: return "ESP_ERR_NOT_FOUND";
        case ESP_ERR_TIMEOUT: return "ESP_ERR_TIMEOUT";
        default: return "UNKNOWN ERROR";
    }
}

void esp_log_write(esp_log_level_t level, const char *tag, const char *format, ...) {
    if (level < ESP_LOG_ERROR || level > ESP_LOG_VERBOSE) return;
    va_list ap;
    va_start(ap, format);
    va_list copy;
    va_copy(copy, ap);
    int n = std::vsnprintf(nullptr, 0, format, copy);
    va_end(copy);
    std::string msg(n > 0 ? static_cast<size_t>(n) : 0, '\0');
    if (n > 0) std::vsnprintf(&msg[0], msg.size() + 1, format, ap);
    va_end(ap);
    static const char kLetters[] = "?EWIDV";
    sim::Event(sim::now_ms(), "log")
        .str("level", std::string(1, kLetters[level]))
        .str("tag", tag ? tag : "")
        .str("msg", msg);
}

void _esp_error_check_failed(esp_err_t rc, const char *file, int line, const char *function,
                             const char *expression) {
    char msg[512];
    std::snprintf(msg, sizeof msg, "ESP_ERROR_CHECK failed: esp_err_t 0x%x (%s) file: \"%s\" line %d func: %s expression: %s",
                  static_cast<unsigned>(rc), esp_err_to_name(rc), file, line, function, expression);
    sim::Event(sim::now_ms(), "log").str("level", "E").str("tag", "esp_err").str("msg", msg);
    sim::end("abort");
}

int64_t esp_timer_get_time(void) { return sim::now_ms() * 1000; }

// usStackDepth is in bytes on ESP-IDF (words on vanilla FreeRTOS); the sim only traces it, it never overflows.
BaseType_t xTaskCreate(TaskFunction_t pxTaskCode, const char *const pcName, const configSTACK_DEPTH_TYPE usStackDepth,
                       void *const pvParameters, UBaseType_t uxPriority, TaskHandle_t *const pxCreatedTask) {
    TaskHandle_t handle = sim::create(pxTaskCode, pcName, pvParameters, usStackDepth, uxPriority);
    if (pxCreatedTask) *pxCreatedTask = handle;
    return pdPASS;
}

void vTaskDelay(const TickType_t xTicksToDelay) { sim::delay(xTicksToDelay); }

void vTaskDelete(TaskHandle_t xTaskToDelete) { sim::remove(xTaskToDelete); }

TickType_t xTaskGetTickCount(void) { return sim::ticks(); }

}  // extern "C"

namespace {

// Async-signal-safe: no allocation, one write, then the default action so the exit status keeps the signal.
void on_crash(int sig) {
    char line[96];
    int n = std::snprintf(line, sizeof line, "{\"t_ms\": %lld, \"ev\": \"end\", \"reason\": \"crash\", \"signal\": %d}\n",
                          static_cast<long long>(sim::now_ms()), sig);
    if (n > 0) (void)!::write(sim::trace_fd, line, static_cast<size_t>(n));
    ::signal(sig, SIG_DFL);
    ::raise(sig);
}

void app_main_task(void *) { app_main(); }

// Each later task validates its own section of the scenario here.
bool load_scenario(const char *path, std::string &err) {
    std::ifstream in(path, std::ios::binary);
    if (!in) { err = "fichier illisible"; return false; }
    std::string text((std::istreambuf_iterator<char>(in)), std::istreambuf_iterator<char>());
    sim::Json root;
    if (!sim::json_parse(text, root, err)) return false;
    if (root.type != sim::Json::Object) { err = "un objet JSON est attendu à la racine"; return false; }
    return sim::gpio_load_scenario(root, err) && sim::adc_load_scenario(root, err) &&
           sim::i2c_load_scenario(root, err) && sim::plant_load_scenario(root, err);
}

}  // namespace

int main(int argc, char **argv) {
    int64_t max_ms = 60000;
    const char *scenario_path = nullptr;
    for (int i = 1; i < argc; ++i) {
        if (std::strcmp(argv[i], "--max-ms") == 0 && i + 1 < argc) {
            char *rest = nullptr;
            max_ms = std::strtoll(argv[++i], &rest, 10);
            if (*rest != '\0' || max_ms < 0 || max_ms > (INT64_MAX >> 12)) {  // same bound as the scenario times
                std::fprintf(stderr, "--max-ms: entier entre 0 et %lld attendu\n", static_cast<long long>(INT64_MAX >> 12));
                return 2;
            }
        } else if (std::strcmp(argv[i], "--scenario") == 0 && i + 1 < argc) {
            scenario_path = argv[++i];
        } else {
            std::fprintf(stderr, "usage: %s [--scenario fichier.json] [--max-ms N]\n", argv[0]);
            return 2;
        }
    }
    if (scenario_path) {
        std::string err;
        if (!load_scenario(scenario_path, err)) {
            std::fprintf(stderr, "scénario %s : %s\n", scenario_path, err.c_str());
            return 2;
        }
    }
    sim::trace_fd = ::dup(STDOUT_FILENO);
    if (sim::trace_fd < 0 || ::dup2(STDERR_FILENO, STDOUT_FILENO) < 0) {
        std::perror("trace");
        return 2;
    }
    for (int sig : {SIGSEGV, SIGBUS, SIGFPE, SIGILL, SIGABRT}) ::signal(sig, on_crash);
    sim::start(app_main_task, max_ms);
}
