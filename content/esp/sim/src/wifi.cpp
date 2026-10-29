// esp_wifi.h / esp_netif.h shim: a Wi-Fi station whose access point follows the scenario's "wifi" section:
//   "up_from_ms": the AP exists from that time (default 0)
//   "down": [{"from_ms", "to_ms"}]: the AP is off in [from, to); a connected station loses the link at from_ms
//   "fail_attempts": n: the first n attempts that would succeed are refused (reason WIFI_REASON_CONNECTION_FAIL)
// The driver follows the documented sequence: esp_wifi_start posts WIFI_EVENT_STA_START; esp_wifi_connect
// starts ONE attempt (no automatic retry, the application reconnects from its WIFI_EVENT_STA_DISCONNECTED
// handler); success posts WIFI_EVENT_STA_CONNECTED then, once DHCP is done, IP_EVENT_STA_GOT_IP (only when
// esp_netif_create_default_wifi_sta was called, as without a netif nothing asks for an address). Events go
// through the default event loop, so handlers run in the task "sys_evt".
//
// Timing (virtual, in ticks of 10 ms): a refused or failed attempt ends 1000 ms after esp_wifi_connect
// with STA_DISCONNECTED (reason 201 WIFI_REASON_NO_AP_FOUND while the AP is off, 205 when refused); a
// successful one gives STA_CONNECTED after 300 ms and GOT_IP (192.168.1.42/24, gateway 192.168.1.1) 200 ms later.
// The attempt counter behind fail_attempts survives restarts (it describes the AP, not the chip).
//
// Simplifications: station mode only (AP/NAN calls are accepted but model nothing); no scan, no RSSI, no
// power save, no WIFI_EVENT_STA_BEACON_TIMEOUT; esp_wifi_set_config stores nothing but the SSID (an empty
// SSID makes esp_wifi_connect fail with ESP_ERR_WIFI_SSID, as documented) and checks the password length (a
// non-empty password shorter than 8 characters is ESP_ERR_WIFI_PASSWORD); no IP_EVENT_STA_LOST_IP; the
// config is not kept in NVS (but esp_wifi_init needs NVS initialised while nvs_enable is set: ESP_ERR_NVS_NOT_INITIALIZED); a second esp_netif_create_default_wifi_sta aborts (the docs forbid it); posts
// are dropped silently when the default event loop does not exist. A link loss also drops MQTT sessions.
#include <cstring>

#include "esp_wifi.h"
#include "nvs.h"
#include "sim.h"

ESP_EVENT_DEFINE_BASE(WIFI_EVENT);
ESP_EVENT_DEFINE_BASE(IP_EVENT);

struct esp_netif_obj {
    int unused;
};

namespace {

// Keep in step with FAIL_MS and CONNECT_MS in content/esp/checks/es7-tp.py (the check derives attempts from them).
constexpr int64_t kFailMs = 1000, kConnectMs = 300, kDhcpMs = 200;

struct Scenario {
    int64_t up_from_ms = 0;
    std::vector<sim::Window> down;
    int64_t fail_attempts = 0;
} scenario;

int64_t refused = 0;  // attempts refused so far (survives restarts)

bool netif_ready = false, inited = false, started = false, connecting = false, connected = false, has_ip = false;
esp_netif_obj sta_netif;
bool sta_netif_made = false;
wifi_mode_t mode = WIFI_MODE_STA;
std::string ssid;
uint64_t generation = 0;  // an attempt's timers die when it changes

bool ap_up(int64_t t) {
    if (t < scenario.up_from_ms) return false;
    for (auto &w : scenario.down) if (t >= w.from_ms && t < w.to_ms) return false;
    return true;
}

bool sta_mode() { return mode == WIFI_MODE_STA || mode == WIFI_MODE_APSTA; }

void post(const char *name, int32_t id, const void *data, size_t size, bool ip = false, int reason = 0) {
    // Traced after the post: a full queue (a handler stuck in sys_evt) or a missing default loop loses the event,
    // and the line then says "delivered": false so a check does not believe a handler saw it. The handlers run
    // later, in sys_evt, so the trace order does not change.
    esp_err_t posted = esp_event_post(ip ? IP_EVENT : WIFI_EVENT, id, data, size, 0);
    sim::Event e(sim::now_ms(), "wifi");
    e.str("event", name);
    if (reason) e.num("reason", reason);
    if (posted != ESP_OK) e.flag("delivered", false);
}

void post_disconnected(int reason) {
    wifi_event_sta_disconnected_t d = {};
    std::memcpy(d.ssid, ssid.data(), ssid.size());
    d.ssid_len = static_cast<uint8_t>(ssid.size());
    d.bssid[0] = 0x02;
    d.reason = static_cast<uint8_t>(reason);
    post("sta_disconnected", WIFI_EVENT_STA_DISCONNECTED, &d, sizeof d, false, reason);
}

void lose_link(int reason) {
    bool was_up = connected;
    connected = connecting = has_ip = false;
    ++generation;
    if (was_up) sim::mqtt_network_lost();
    post_disconnected(reason);
}

void got_ip() {
    if (!sta_netif_made) return;
    has_ip = true;
    ip_event_got_ip_t g = {};
    g.esp_netif = &sta_netif;
    auto set = [](esp_ip4_addr_t &a, int b0, int b1, int b2, int b3) {
        a.addr = static_cast<uint32_t>(b0) | static_cast<uint32_t>(b1) << 8 | static_cast<uint32_t>(b2) << 16 | static_cast<uint32_t>(b3) << 24;
    };
    set(g.ip_info.ip, 192, 168, 1, 42);
    set(g.ip_info.netmask, 255, 255, 255, 0);
    set(g.ip_info.gw, 192, 168, 1, 1);
    g.ip_changed = true;
    sim::Event(sim::now_ms(), "wifi").str("event", "got_ip").str("ip", "192.168.1.42");
    esp_event_post(IP_EVENT, IP_EVENT_STA_GOT_IP, &g, sizeof g, 0);
}

void finish_attempt(uint64_t gen) {
    if (gen != generation || !connecting) return;
    int64_t now = sim::now_ms();
    if (!ap_up(now)) { connecting = false; post_disconnected(WIFI_REASON_NO_AP_FOUND); return; }
    if (refused < scenario.fail_attempts) {
        ++refused;
        connecting = false;
        post_disconnected(WIFI_REASON_CONNECTION_FAIL);
        return;
    }
    connecting = false;
    connected = true;
    wifi_event_sta_connected_t c = {};
    std::memcpy(c.ssid, ssid.data(), ssid.size());
    c.ssid_len = static_cast<uint8_t>(ssid.size());
    c.bssid[0] = 0x02;
    c.channel = 1;
    c.authmode = WIFI_AUTH_WPA2_PSK;
    c.aid = 1;
    post("sta_connected", WIFI_EVENT_STA_CONNECTED, &c, sizeof c);
    sim::at(now + kDhcpMs, [gen] { if (gen == generation && connected) got_ip(); });
}

}  // namespace

namespace sim {

bool wifi_load_scenario(const Json &root, std::string &err) {
    const Json *w = root.get("wifi");
    if (!w) return true;
    if (w->type != Json::Object) { err = "\"wifi\" doit être un objet"; return false; }
    if (!only_keys(*w, {"up_from_ms", "down", "fail_attempts"}, "wifi", err)) return false;
    long long up = 0, fail = 0;
    if (const Json *j = w->get("up_from_ms"); j && !j->as_int(0, INT64_MAX >> 12, up)) {
        err = "wifi : \"up_from_ms\" entier >= 0 attendu";
        return false;
    }
    if (const Json *j = w->get("fail_attempts"); j && !j->as_int(0, 1000000, fail)) {
        err = "wifi : \"fail_attempts\" entier entre 0 et 1000000 attendu";
        return false;
    }
    Scenario s;
    s.up_from_ms = up;
    s.fail_attempts = fail;
    if (!parse_windows(w->get("down"), "wifi : \"down\"", s.down, err)) return false;
    scenario = std::move(s);
    return true;
}

void wifi_boot() {
    for (auto &w : scenario.down)
        at(w.from_ms, [] { if (connected || connecting) lose_link(WIFI_REASON_BEACON_TIMEOUT); });
}

void wifi_save(std::ostream &out) { out << "wifi " << refused << "\n"; }
void wifi_restore(std::istream &in) { in >> refused; }
bool wifi_in_use() { return inited; }
bool wifi_has_ip() { return has_ip; }

}  // namespace sim

extern "C" {

esp_err_t esp_netif_init(void) {
    netif_ready = true;
    return ESP_OK;
}

esp_netif_t *esp_netif_create_default_wifi_sta(void) {
    // The real function runs ESP_ERROR_CHECK on its steps: no esp_netif_init or no default event loop aborts.
    if (!netif_ready || !sim::event_loop_ready() || sta_netif_made)
        _esp_error_check_failed(ESP_ERR_INVALID_STATE, __FILE__, __LINE__, __func__, "esp_netif_create_default_wifi_sta");
    sta_netif_made = true;
    return &sta_netif;
}

esp_err_t esp_wifi_init(const wifi_init_config_t *config) {
    if (!config || config->magic != WIFI_INIT_CONFIG_MAGIC) return ESP_ERR_INVALID_ARG;
    if (inited) return ESP_ERR_INVALID_STATE;
    // The driver keeps its configuration in NVS when config->nvs_enable is set (the default of WIFI_INIT_CONFIG_DEFAULT()):
    // the sim makes the missing nvs_flash_init an error here, as the official examples' "Initialize NVS" step implies.
    if (config->nvs_enable && !sim::nvs_ready()) return ESP_ERR_NVS_NOT_INITIALIZED;
    inited = true;
    mode = WIFI_MODE_STA;  // documented default
    return ESP_OK;
}

esp_err_t esp_wifi_deinit(void) {
    if (!inited) return ESP_ERR_WIFI_NOT_INIT;
    if (connected) lose_link(WIFI_REASON_ASSOC_LEAVE);
    inited = started = connecting = connected = has_ip = false;
    ++generation;
    return ESP_OK;
}

esp_err_t esp_wifi_set_mode(wifi_mode_t m) {
    if (!inited) return ESP_ERR_WIFI_NOT_INIT;
    if (m < WIFI_MODE_NULL || m >= WIFI_MODE_MAX) return ESP_ERR_INVALID_ARG;
    mode = m;
    return ESP_OK;
}

esp_err_t esp_wifi_set_config(wifi_interface_t interface, wifi_config_t *conf) {
    if (!inited) return ESP_ERR_WIFI_NOT_INIT;
    if (!conf) return ESP_ERR_INVALID_ARG;
    if (interface != WIFI_IF_STA && interface != WIFI_IF_AP) return ESP_ERR_WIFI_IF;
    bool ok = interface == WIFI_IF_STA ? sta_mode() : (mode == WIFI_MODE_AP || mode == WIFI_MODE_APSTA);
    if (!ok) return ESP_ERR_WIFI_MODE;
    if (interface == WIFI_IF_STA) {
        size_t pw = strnlen(reinterpret_cast<const char *>(conf->sta.password), sizeof conf->sta.password);
        if (pw > 0 && pw < 8) return ESP_ERR_WIFI_PASSWORD;
        ssid.assign(reinterpret_cast<const char *>(conf->sta.ssid), strnlen(reinterpret_cast<const char *>(conf->sta.ssid), sizeof conf->sta.ssid));
    }
    return ESP_OK;
}

esp_err_t esp_wifi_start(void) {
    if (!inited) return ESP_ERR_WIFI_NOT_INIT;
    if (started) return ESP_OK;
    started = true;
    if (sta_mode()) post("sta_start", WIFI_EVENT_STA_START, nullptr, 0);
    return ESP_OK;
}

esp_err_t esp_wifi_stop(void) {
    if (!inited) return ESP_ERR_WIFI_NOT_INIT;
    if (!started) return ESP_OK;
    if (connected || connecting) lose_link(WIFI_REASON_ASSOC_LEAVE);
    started = false;
    if (sta_mode()) post("sta_stop", WIFI_EVENT_STA_STOP, nullptr, 0);
    return ESP_OK;
}

esp_err_t esp_wifi_connect(void) {
    if (!inited) return ESP_ERR_WIFI_NOT_INIT;
    if (!started) return ESP_ERR_WIFI_NOT_STARTED;
    if (!sta_mode()) return ESP_ERR_WIFI_MODE;
    if (ssid.empty()) return ESP_ERR_WIFI_SSID;
    if (connecting || connected) return ESP_ERR_WIFI_CONN;
    connecting = true;
    uint64_t gen = ++generation;
    // The outcome is decided when the attempt ends, from the AP state at that time.
    sim::at(sim::now_ms() + (ap_up(sim::now_ms()) && refused >= scenario.fail_attempts ? kConnectMs : kFailMs),
            [gen] { finish_attempt(gen); });
    return ESP_OK;
}

esp_err_t esp_wifi_disconnect(void) {
    if (!inited) return ESP_ERR_WIFI_NOT_INIT;
    if (!started) return ESP_ERR_WIFI_NOT_STARTED;
    if (connected || connecting) lose_link(WIFI_REASON_ASSOC_LEAVE);
    return ESP_OK;
}

}  // extern "C"
