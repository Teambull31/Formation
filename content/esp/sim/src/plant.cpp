// Pool-tank plant: the level follows the relay pin on the virtual clock and is sampled through the ADC.
//
// Integer arithmetic only. The level is kept in units of 1/6e7 %, so that a rate in 1e-3 %/min
// changes it by exactly `rate * dt_ms` units: no floating point, no drift, no lost remainder.
// The tank is integrated lazily, to the current time, at every sample and before every pin change
// (plant_sync from gpio_set_level), so the relay level is constant between two integration points.
#include <algorithm>
#include <cmath>

#include "sim.h"

namespace {

constexpr int64_t kUnitsPerPct = 60000000;  // 1 % in level units
constexpr int64_t kFull = 100 * kUnitsPerPct;

struct Tank {
    bool present = false;
    int64_t level = 0;       // level units
    int64_t fill_milli = 0;  // 1e-3 %/min, applied while the relay pin is driven high
    int64_t loss_milli = 0;  // 1e-3 %/min, applied otherwise
    int relay_pin = 0;
    int channel = 0;
    int64_t raw_at_0 = 0, raw_at_100 = 0;
    std::vector<sim::Window> stuck;  // sorted by from_ms
    std::vector<int64_t> held;       // raw frozen when stuck[i] opened, valid when i < captured
    size_t captured = 0;
    int64_t last_ms = 0;             // integrated up to here
};

Tank tank;

int64_t project(int64_t level) { return tank.raw_at_0 + (tank.raw_at_100 - tank.raw_at_0) * level / kFull; }

void integrate(int64_t to_ms) {
    int64_t dt = to_ms - tank.last_ms;
    if (dt <= 0) return;
    int64_t rate = sim::gpio_driven_level(tank.relay_pin) ? tank.fill_milli : -tank.loss_milli;
    tank.level = std::clamp<int64_t>(tank.level + rate * dt, 0, kFull);
    tank.last_ms = to_ms;
}

void advance(int64_t now) {
    while (tank.captured < tank.stuck.size() && tank.stuck[tank.captured].from_ms <= now) {
        integrate(tank.stuck[tank.captured].from_ms);
        tank.held.push_back(project(tank.level));
        ++tank.captured;
    }
    integrate(now);
}

bool number(const sim::Json &obj, const char *key, double lo, double hi, double &out, std::string &err) {
    const sim::Json *j = obj.get(key);
    if (!j || j->type != sim::Json::Number || !(j->num >= lo && j->num <= hi)) {
        err = std::string("plant.tank : \"") + key + "\" nombre entre " + std::to_string(static_cast<int>(lo)) + " et " +
              std::to_string(static_cast<int>(hi)) + " attendu";
        return false;
    }
    out = j->num;
    return true;
}

bool integer(const sim::Json &obj, const char *key, long long lo, long long hi, long long &out, std::string &err) {
    const sim::Json *j = obj.get(key);
    if (!j || !j->as_int(lo, hi, out)) {
        err = std::string("plant.tank : \"") + key + "\" entier entre " + std::to_string(lo) + " et " + std::to_string(hi) + " attendu";
        return false;
    }
    return true;
}

}  // namespace

namespace sim {

bool parse_windows(const Json *list, const char *where, std::vector<Window> &out, std::string &err) {
    if (!list) return true;
    if (list->type != Json::Array) { err = std::string(where) + " doit être un tableau"; return false; }
    for (const Json &e : list->arr) {
        long long from = 0, to = 0;
        const Json *jf = e.type == Json::Object ? e.get("from_ms") : nullptr;
        const Json *jt = e.type == Json::Object ? e.get("to_ms") : nullptr;
        if (!jf || !jf->as_int(0, INT64_MAX >> 12, from) || !jt || !jt->as_int(from, INT64_MAX >> 12, to)) {
            err = std::string(where) + " : {\"from_ms\", \"to_ms\"} entiers avec 0 <= from_ms <= to_ms attendus";
            return false;
        }
        out.push_back({from, to});
    }
    return true;
}

bool plant_load_scenario(const Json &scenario, std::string &err) {
    const Json *plant = scenario.get("plant");
    if (!plant) return true;
    if (plant->type != Json::Object) { err = "\"plant\" doit être un objet"; return false; }
    const Json *t = plant->get("tank");
    if (!t) return true;
    if (t->type != Json::Object) { err = "plant : \"tank\" doit être un objet"; return false; }
    double level = 0, fill = 0, loss = 0;
    long long pin = 0, channel = 0, raw0 = 0, raw100 = 0;
    Tank k;
    if (!number(*t, "level_pct0", 0, 100, level, err) || !number(*t, "fill_pct_per_min", 0, 1000, fill, err) ||
        !number(*t, "loss_pct_per_min", 0, 1000, loss, err) || !integer(*t, "relay_pin", 0, 39, pin, err) ||
        !integer(*t, "adc_channel", 0, 9, channel, err) || !integer(*t, "raw_at_0", 0, 4095, raw0, err) ||
        !integer(*t, "raw_at_100", 0, 4095, raw100, err) || !parse_windows(t->get("stuck"), "plant.tank : \"stuck\"", k.stuck, err))
        return false;
    k.present = true;
    k.level = std::llround(level * static_cast<double>(kUnitsPerPct));
    k.fill_milli = std::llround(fill * 1000);
    k.loss_milli = std::llround(loss * 1000);
    k.relay_pin = static_cast<int>(pin);
    k.channel = static_cast<int>(channel);
    k.raw_at_0 = raw0;
    k.raw_at_100 = raw100;
    std::stable_sort(k.stuck.begin(), k.stuck.end(), [](const Window &a, const Window &b) { return a.from_ms < b.from_ms; });
    tank = std::move(k);
    return true;
}

void plant_sync() {
    if (tank.present) advance(now_ms());
}

bool plant_sample(int channel, int64_t &raw) {
    if (!tank.present || channel != tank.channel) return false;
    int64_t now = now_ms();
    advance(now);
    for (size_t i = 0; i < tank.captured; ++i) {
        if (now < tank.stuck[i].to_ms) { raw = tank.held[i]; return true; }  // opened (captured) and not yet over
    }
    raw = project(tank.level);
    return true;
}

}  // namespace sim
