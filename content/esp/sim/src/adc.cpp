// esp_adc/adc_oneshot.h shim: raw readings follow the scenario's "adc" points (or the tank plant).
#include <algorithm>
#include <memory>
#include <vector>

#include "esp_adc/adc_oneshot.h"
#include "sim.h"

struct adc_oneshot_unit_ctx_t {
    adc_unit_t unit;
    bool configured[10] = {};
    int bits[10] = {};
};

namespace {

constexpr int kChannels = 10;  // ESP32: ADC1 0-7, ADC2 0-9
constexpr int kMaxRaw = 4095;

struct Point { int64_t t_ms; int64_t raw; };

std::vector<Point> points[kChannels];  // sorted by t_ms, later entries win on equal times
std::vector<std::unique_ptr<adc_oneshot_unit_ctx_t>> units;

adc_oneshot_unit_ctx_t *find(adc_oneshot_unit_handle_t h) {
    for (auto &u : units) if (u.get() == h) return h;
    return nullptr;
}

bool valid_bitwidth(int b) { return b == ADC_BITWIDTH_DEFAULT || (b >= ADC_BITWIDTH_9 && b <= ADC_BITWIDTH_12); }

// Linear interpolation, int64 with truncation toward zero; clamped before the first and after the last point.
int64_t scenario_raw(int channel, int64_t now) {
    const auto &p = points[channel];
    if (p.empty()) return 0;
    size_t i = 0;
    while (i + 1 < p.size() && p[i + 1].t_ms <= now) ++i;
    if (now <= p.front().t_ms) return p.front().raw;
    if (i + 1 == p.size()) return p[i].raw;
    return p[i].raw + (p[i + 1].raw - p[i].raw) * (now - p[i].t_ms) / (p[i + 1].t_ms - p[i].t_ms);
}

}  // namespace

namespace sim {

bool adc_load_scenario(const Json &scenario, std::string &err) {
    const Json *list = scenario.get("adc");
    if (!list) return true;
    if (list->type != Json::Array) { err = "\"adc\" doit être un tableau"; return false; }
    for (const Json &e : list->arr) {
        long long t = 0, ch = 0, raw = 0;
        const Json *jt = e.type == Json::Object ? e.get("t_ms") : nullptr;
        const Json *jc = e.type == Json::Object ? e.get("channel") : nullptr;
        const Json *jr = e.type == Json::Object ? e.get("raw") : nullptr;
        if (!jt || !jt->as_int(0, INT64_MAX >> 11, t)) { err = "adc : \"t_ms\" entier >= 0 attendu"; return false; }
        if (!jc || !jc->as_int(0, kChannels - 1, ch)) { err = "adc : \"channel\" entier entre 0 et 9 attendu"; return false; }
        if (!jr || !jr->as_int(0, kMaxRaw, raw)) { err = "adc : \"raw\" entier entre 0 et 4095 attendu"; return false; }
        points[ch].push_back({t, raw});
    }
    for (auto &p : points)
        std::stable_sort(p.begin(), p.end(), [](const Point &a, const Point &b) { return a.t_ms < b.t_ms; });
    return true;
}

}  // namespace sim

extern "C" {

esp_err_t adc_oneshot_new_unit(const adc_oneshot_unit_init_cfg_t *init_config, adc_oneshot_unit_handle_t *ret_unit) {
    if (!init_config || !ret_unit || (init_config->unit_id != ADC_UNIT_1 && init_config->unit_id != ADC_UNIT_2))
        return ESP_ERR_INVALID_ARG;
    for (auto &u : units) if (u->unit == init_config->unit_id) return ESP_ERR_NOT_FOUND;  // peripheral already claimed
    units.push_back(std::make_unique<adc_oneshot_unit_ctx_t>());
    units.back()->unit = init_config->unit_id;
    *ret_unit = units.back().get();
    return ESP_OK;
}

esp_err_t adc_oneshot_config_channel(adc_oneshot_unit_handle_t handle, adc_channel_t channel, const adc_oneshot_chan_cfg_t *config) {
    adc_oneshot_unit_ctx_t *u = find(handle);
    if (!u || !config || channel < 0 || channel >= kChannels || !valid_bitwidth(config->bitwidth) ||
        config->atten < ADC_ATTEN_DB_0 || config->atten > ADC_ATTEN_DB_12)
        return ESP_ERR_INVALID_ARG;
    u->configured[channel] = true;
    u->bits[channel] = config->bitwidth == ADC_BITWIDTH_DEFAULT ? 12 : config->bitwidth;
    return ESP_OK;
}

esp_err_t adc_oneshot_read(adc_oneshot_unit_handle_t handle, adc_channel_t chan, int *out_raw) {
    adc_oneshot_unit_ctx_t *u = find(handle);
    if (!u || !out_raw || chan < 0 || chan >= kChannels || !u->configured[chan]) return ESP_ERR_INVALID_ARG;
    int64_t raw = 0;
    if (!sim::plant_sample(chan, raw)) raw = scenario_raw(chan, sim::now_ms());
    raw >>= 12 - u->bits[chan];
    *out_raw = static_cast<int>(raw);
    sim::Event(sim::now_ms(), "adc_read").num("channel", chan).num("raw", raw);
    return ESP_OK;
}

esp_err_t adc_oneshot_del_unit(adc_oneshot_unit_handle_t handle) {
    for (auto it = units.begin(); it != units.end(); ++it) {
        if (it->get() != handle) continue;
        units.erase(it);
        return ESP_OK;
    }
    return ESP_ERR_INVALID_ARG;
}

}  // extern "C"
