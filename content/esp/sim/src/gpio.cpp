// driver/gpio.h shim: pin state, traced outputs, inputs driven by the scenario's "gpio_in" list.
#include <algorithm>
#include <vector>

#include "driver/gpio.h"
#include "sim.h"

namespace {

constexpr int kPins = 40;  // ESP32: GPIO 0-39, 34-39 are input-only

struct Pin {
    gpio_mode_t mode = GPIO_MODE_DISABLE;
    bool pull_up = false;
    int out = 0;
};

struct Step { int64_t t_ms; int level; };

Pin pins[kPins];
std::vector<Step> script[kPins];  // sorted by t_ms, later entries win on equal times

bool valid(int n) { return n >= 0 && n < kPins; }
bool input_only(int n) { return n >= 34; }
bool has_input(gpio_mode_t m) { return m == GPIO_MODE_INPUT || m == GPIO_MODE_INPUT_OUTPUT || m == GPIO_MODE_INPUT_OUTPUT_OD; }
bool has_output(gpio_mode_t m) { return m != GPIO_MODE_DISABLE && m != GPIO_MODE_INPUT; }

const char *mode_name(gpio_mode_t m) {
    switch (m) {
        case GPIO_MODE_INPUT: return "input";
        case GPIO_MODE_OUTPUT: return "output";
        case GPIO_MODE_OUTPUT_OD: return "output_od";
        case GPIO_MODE_INPUT_OUTPUT_OD: return "input_output_od";
        case GPIO_MODE_INPUT_OUTPUT: return "input_output";
        default: return "disable";
    }
}

bool valid_mode(int m) { return m == GPIO_MODE_DISABLE || m == GPIO_MODE_INPUT || m == GPIO_MODE_OUTPUT || m == GPIO_MODE_OUTPUT_OD || m == GPIO_MODE_INPUT_OUTPUT_OD || m == GPIO_MODE_INPUT_OUTPUT; }

void trace_config(int n) {
    sim::Event(sim::now_ms(), "gpio_config").num("pin", n).str("mode", mode_name(pins[n].mode)).flag("pull_up", pins[n].pull_up);
}

esp_err_t apply_direction(int n, gpio_mode_t mode) {
    if (!valid(n) || !valid_mode(mode)) return ESP_ERR_INVALID_ARG;
    if (input_only(n) && has_output(mode)) return ESP_ERR_INVALID_ARG;
    pins[n].mode = mode;
    return ESP_OK;
}

}  // namespace

namespace sim {

bool gpio_load_scenario(const Json &scenario, std::string &err) {
    const Json *list = scenario.get("gpio_in");
    if (!list) return true;
    if (list->type != Json::Array) { err = "\"gpio_in\" doit être un tableau"; return false; }
    for (const Json &e : list->arr) {
        long long t = 0, pin = 0, level = 0;
        const Json *jt = e.type == Json::Object ? e.get("t_ms") : nullptr;
        const Json *jp = e.type == Json::Object ? e.get("pin") : nullptr;
        const Json *jl = e.type == Json::Object ? e.get("level") : nullptr;
        if (!jt || !jt->as_int(0, INT64_MAX >> 11, t)) { err = "gpio_in : \"t_ms\" entier >= 0 attendu"; return false; }
        if (!jp || !jp->as_int(0, kPins - 1, pin)) { err = "gpio_in : \"pin\" entier entre 0 et 39 attendu"; return false; }
        if (!jl || !jl->as_int(0, 1, level)) { err = "gpio_in : \"level\" doit valoir 0 ou 1"; return false; }
        script[pin].push_back({t, static_cast<int>(level)});
    }
    for (auto &s : script)
        std::stable_sort(s.begin(), s.end(), [](const Step &a, const Step &b) { return a.t_ms < b.t_ms; });
    return true;
}

}  // namespace sim

extern "C" {

esp_err_t gpio_config(const gpio_config_t *cfg) {
    if (!cfg || cfg->pin_bit_mask == 0 || (cfg->pin_bit_mask >> kPins) != 0) return ESP_ERR_INVALID_ARG;
    if (!valid_mode(cfg->mode)) return ESP_ERR_INVALID_ARG;
    for (int n = 0; n < kPins; ++n) {
        if (!(cfg->pin_bit_mask >> n & 1)) continue;
        if (esp_err_t err = apply_direction(n, cfg->mode)) return err;
        pins[n].pull_up = cfg->pull_up_en == GPIO_PULLUP_ENABLE;
        trace_config(n);
    }
    return ESP_OK;
}

esp_err_t gpio_set_direction(gpio_num_t gpio_num, gpio_mode_t mode) {
    if (esp_err_t err = apply_direction(gpio_num, mode)) return err;
    trace_config(gpio_num);
    return ESP_OK;
}

esp_err_t gpio_set_pull_mode(gpio_num_t gpio_num, gpio_pull_mode_t pull) {
    if (!valid(gpio_num) || pull < GPIO_PULLUP_ONLY || pull > GPIO_FLOATING) return ESP_ERR_INVALID_ARG;
    pins[gpio_num].pull_up = pull == GPIO_PULLUP_ONLY || pull == GPIO_PULLUP_PULLDOWN;
    trace_config(gpio_num);
    return ESP_OK;
}

esp_err_t gpio_set_level(gpio_num_t gpio_num, uint32_t level) {
    if (!valid(gpio_num) || input_only(gpio_num)) return ESP_ERR_INVALID_ARG;
    pins[gpio_num].out = level ? 1 : 0;
    sim::Event(sim::now_ms(), "gpio_set").num("pin", gpio_num).num("level", pins[gpio_num].out)
        .str("task", sim::current_name());
    return ESP_OK;
}

int gpio_get_level(gpio_num_t gpio_num) {
    if (!valid(gpio_num) || !has_input(pins[gpio_num].mode)) return 0;
    const Pin &p = pins[gpio_num];
    int64_t now = sim::now_ms();
    const auto &s = script[gpio_num];
    for (auto it = s.rbegin(); it != s.rend(); ++it)
        if (it->t_ms <= now) return it->level;
    if (p.pull_up) return 1;
    return has_output(p.mode) ? p.out : 0;
}

}  // extern "C"
