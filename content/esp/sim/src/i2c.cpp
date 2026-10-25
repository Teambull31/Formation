// driver/i2c_master.h shim: devices answer with their scenario bytes (fixed, or a step function over time); unknown address or NACK window -> ESP_ERR_TIMEOUT.
#include <algorithm>
#include <cstdlib>
#include <cstring>
#include <memory>
#include <vector>

#include "driver/i2c_master.h"
#include "sim.h"

struct i2c_master_bus_t {
    int port;
};

struct i2c_master_dev_t {
    i2c_master_bus_t *bus;
    int addr;
};

namespace {

struct Step {
    int64_t t_ms;
    std::vector<uint8_t> bytes;
};

struct Target {
    int addr;
    std::vector<uint8_t> bytes;
    std::vector<Step> series;  // sorted by t_ms, later entries win on equal times; overrides "bytes" from its t_ms on
    std::vector<sim::Window> nack;
};

constexpr int kPorts = 2;
std::vector<Target> targets;
std::vector<std::unique_ptr<i2c_master_bus_t>> buses;
std::vector<std::unique_ptr<i2c_master_dev_t>> devs;

i2c_master_dev_t *find_dev(i2c_master_dev_handle_t h) {
    for (auto &d : devs) if (d.get() == h) return h;
    return nullptr;
}

bool parse_bytes(const sim::Json *bytes, std::vector<uint8_t> &out, std::string &err) {
    for (const sim::Json &b : bytes->arr) {
        long long v = 0;
        if (!b.as_int(0, 255, v)) { err = "i2c : chaque octet de \"bytes\" doit être un entier entre 0 et 255"; return false; }
        out.push_back(static_cast<uint8_t>(v));
    }
    return true;
}

bool find_bus(i2c_master_bus_handle_t h) {
    for (auto &b : buses) if (b.get() == h) return true;
    return false;
}

// One transfer to the device: the trace records it, a missing or NACKing device times out (the docs'
// ESP_ERR_TIMEOUT). A read gets the scenario bytes in force now (last series step, else "bytes"), zero padded.
esp_err_t transfer(i2c_master_dev_handle_t handle, const uint8_t *write_buffer, size_t write_size, uint8_t *read_buffer,
                   size_t read_size, bool writes, bool reads) {
    i2c_master_dev_t *d = find_dev(handle);
    if (!d || (writes && (!write_buffer || write_size == 0)) || (reads && (!read_buffer || read_size == 0)))
        return ESP_ERR_INVALID_ARG;
    int64_t now = sim::now_ms();
    const Target *t = nullptr;
    for (const Target &c : targets) if (c.addr == d->addr) t = &c;
    bool ok = t != nullptr;
    if (t) for (const sim::Window &w : t->nack) if (w.from_ms <= now && now < w.to_ms) ok = false;
    sim::Event(now, "i2c_xfer").num("addr", d->addr).flag("ok", ok);
    if (!ok) return ESP_ERR_TIMEOUT;
    if (reads) {
        const std::vector<uint8_t> *b = &t->bytes;
        for (const Step &s : t->series) if (s.t_ms <= now) b = &s.bytes;
        for (size_t i = 0; i < read_size; ++i) read_buffer[i] = i < b->size() ? (*b)[i] : 0;
    }
    return ESP_OK;
}

}  // namespace

namespace sim {

bool i2c_load_scenario(const Json &scenario, std::string &err) {
    const Json *map = scenario.get("i2c");
    if (!map) return true;
    if (map->type != Json::Object) { err = "\"i2c\" doit être un objet"; return false; }
    for (const auto &[key, dev] : map->obj) {
        char *rest = nullptr;
        long addr = std::strtol(key.c_str(), &rest, 0);
        if (key.empty() || *rest != '\0' || addr < 0 || addr > 0x3FF) { err = "i2c : adresse \"" + key + "\" invalide (ex. \"0x44\")"; return false; }
        if (dev.type != Json::Object) { err = "i2c : \"" + key + "\" doit être un objet"; return false; }
        Target t{static_cast<int>(addr), {}, {}, {}};
        const Json *bytes = dev.get("bytes"), *series = dev.get("series");
        if (!bytes && !series) { err = "i2c : \"bytes\" ou \"series\" attendu pour " + key; return false; }
        if (bytes && (bytes->type != Json::Array || !parse_bytes(bytes, t.bytes, err))) {
            if (err.empty()) err = "i2c : \"bytes\" tableau attendu pour " + key;
            return false;
        }
        if (series) {
            if (series->type != Json::Array) { err = "i2c : \"series\" tableau attendu pour " + key; return false; }
            for (const Json &e : series->arr) {
                long long at = 0;
                const Json *jt = e.type == Json::Object ? e.get("t_ms") : nullptr;
                const Json *jb = e.type == Json::Object ? e.get("bytes") : nullptr;
                if (!jt || !jt->as_int(0, INT64_MAX >> 11, at) || !jb || jb->type != Json::Array) {
                    err = "i2c : chaque pas de \"series\" attend {\"t_ms\": entier >= 0, \"bytes\": tableau}";
                    return false;
                }
                Step s{at, {}};
                if (!parse_bytes(jb, s.bytes, err)) return false;
                t.series.push_back(std::move(s));
            }
            std::stable_sort(t.series.begin(), t.series.end(), [](const Step &a, const Step &b) { return a.t_ms < b.t_ms; });
        }
        if (!parse_windows(dev.get("nack"), "i2c : \"nack\"", t.nack, err)) return false;
        targets.push_back(std::move(t));
    }
    return true;
}

}  // namespace sim

extern "C" {

esp_err_t i2c_new_master_bus(const i2c_master_bus_config_t *bus_config, i2c_master_bus_handle_t *ret_bus_handle) {
    if (!bus_config || !ret_bus_handle || bus_config->i2c_port < -1 || bus_config->i2c_port >= kPorts ||
        bus_config->sda_io_num < 0 || bus_config->sda_io_num >= GPIO_NUM_MAX ||
        bus_config->scl_io_num < 0 || bus_config->scl_io_num >= GPIO_NUM_MAX || bus_config->sda_io_num == bus_config->scl_io_num)
        return ESP_ERR_INVALID_ARG;
    int port = bus_config->i2c_port;
    for (int p = port < 0 ? 0 : port; p < (port < 0 ? kPorts : port + 1); ++p) {
        bool used = false;
        for (auto &b : buses) used = used || b->port == p;
        if (used) continue;
        buses.push_back(std::make_unique<i2c_master_bus_t>(i2c_master_bus_t{p}));
        *ret_bus_handle = buses.back().get();
        return ESP_OK;
    }
    return ESP_ERR_NOT_FOUND;  // no free port
}

esp_err_t i2c_master_bus_add_device(i2c_master_bus_handle_t bus_handle, const i2c_device_config_t *dev_config, i2c_master_dev_handle_t *ret_handle) {
    if (!find_bus(bus_handle) || !dev_config || !ret_handle) return ESP_ERR_INVALID_ARG;
    if (dev_config->dev_addr_length != I2C_ADDR_BIT_LEN_7 && dev_config->dev_addr_length != I2C_ADDR_BIT_LEN_10)
        return ESP_ERR_INVALID_ARG;
    int max = dev_config->dev_addr_length == I2C_ADDR_BIT_LEN_7 ? 0x7F : 0x3FF;
    if (dev_config->device_address > max) return ESP_ERR_INVALID_ARG;
    devs.push_back(std::make_unique<i2c_master_dev_t>(i2c_master_dev_t{bus_handle, dev_config->device_address}));
    *ret_handle = devs.back().get();
    return ESP_OK;
}

esp_err_t i2c_master_transmit(i2c_master_dev_handle_t i2c_dev, const uint8_t *write_buffer, size_t write_size, int xfer_timeout_ms) {
    (void)xfer_timeout_ms;  // transfers take no virtual time
    return transfer(i2c_dev, write_buffer, write_size, nullptr, 0, true, false);
}

esp_err_t i2c_master_receive(i2c_master_dev_handle_t i2c_dev, uint8_t *read_buffer, size_t read_size, int xfer_timeout_ms) {
    (void)xfer_timeout_ms;
    return transfer(i2c_dev, nullptr, 0, read_buffer, read_size, false, true);
}

esp_err_t i2c_master_transmit_receive(i2c_master_dev_handle_t i2c_dev, const uint8_t *write_buffer, size_t write_size, uint8_t *read_buffer, size_t read_size, int xfer_timeout_ms) {
    (void)xfer_timeout_ms;
    return transfer(i2c_dev, write_buffer, write_size, read_buffer, read_size, true, true);
}

esp_err_t i2c_del_master_bus(i2c_master_bus_handle_t bus_handle) {
    for (auto it = buses.begin(); it != buses.end(); ++it) {
        if (it->get() != bus_handle) continue;
        for (auto d = devs.begin(); d != devs.end();) d = d->get()->bus == bus_handle ? devs.erase(d) : d + 1;
        buses.erase(it);
        return ESP_OK;
    }
    return ESP_ERR_INVALID_ARG;
}

esp_err_t i2c_master_bus_rm_device(i2c_master_dev_handle_t handle) {
    for (auto it = devs.begin(); it != devs.end(); ++it) {
        if (it->get() != handle) continue;
        devs.erase(it);
        return ESP_OK;
    }
    return ESP_ERR_INVALID_ARG;
}

}  // extern "C"
