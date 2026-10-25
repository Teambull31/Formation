// mqtt_client.h shim (esp-mqtt): a client talking to the scenario's broker, section "mqtt":
//   "broker_down": [{"from_ms", "to_ms"}]: the broker is unreachable in [from, to); connected clients lose
//                  their session at from_ms
//   "incoming": [{"t_ms", "topic", "payload", "qos"?, "retain"?}]: a message published to the broker at t_ms;
//                  every connected client subscribed to a matching filter (+ and # wildcards) gets MQTT_EVENT_DATA
// The network exists when Wi-Fi is not used by the program (e.g. Ethernet); once esp_wifi_init was called, a
// connection needs IP_EVENT_STA_GOT_IP, and losing the Wi-Fi link drops the session.
//
// Behaviour taken from the esp-mqtt docs: events reach the handlers in the client's own task ("mqtt_task",
// created by esp_mqtt_client_start), not in the default event loop; reconnection is automatic every
// network.reconnect_timeout_ms (default 10000) unless disable_auto_reconnect; a clean session (the default)
// forgets the subscriptions, so the application subscribes again in its MQTT_EVENT_CONNECTED handler;
// esp_mqtt_client_publish returns the message id (always 0 for QoS 0), -1 on failure, and while
// disconnected a QoS 0 message is refused (-1) whereas QoS 1 and 2 messages are queued and sent after the
// reconnection; esp_mqtt_client_subscribe_single returns -1 when not connected.
//
// Timing (virtual): a connection attempt (MQTT_EVENT_BEFORE_CONNECT) ends 100 ms later, with
// MQTT_EVENT_CONNECTED or MQTT_EVENT_ERROR (MQTT_ERROR_TYPE_TCP_TRANSPORT); the next attempt is
// reconnect_timeout_ms after that error or after MQTT_EVENT_DISCONNECTED. Trace: "mqtt_publish" (each
// message actually sent to the broker), "mqtt_subscribe", and "mqtt" for the events (event = before_connect,
// connected, disconnected, error, subscribed, unsubscribed, published, data).
//
// Simplifications: one broker, no keep-alive, no authentication or TLS, no Last Will delivery (the will of
// the configuration is traced with "connected" as lwt_topic), no retained-message store (a retained publish
// is only traced), no MQTT_EVENT_DISCONNECTED on esp_mqtt_client_stop, no fragmented DATA events, no outbox
// limit, QoS 1/2 handshakes reduced to one MQTT_EVENT_PUBLISHED, the subscription qos in a DATA event is the
// lower of the two, esp_mqtt_client_stop/destroy from a handler are not detected.
#include <algorithm>
#include <cerrno>
#include <cstring>
#include <deque>
#include <memory>

#include "mqtt_client.h"
#include "sim.h"

ESP_EVENT_DEFINE_BASE(MQTT_EVENTS);

namespace {

constexpr int64_t kConnectMs = 100;
constexpr int kDefaultReconnectMs = 10000;

struct Ev {
    int id;
    int msg_id = 0;
    std::string topic, data;
    int qos = 0;
    bool retain = false;
    int session_present = 0;
    int error_type = 0, sock_errno = 0;
};

struct Handler {
    int id;
    esp_event_handler_t fn;
    void *arg;
};

struct Out {
    std::string topic, data;
    int qos;
    bool retain;
    int id;
};

}  // namespace

struct esp_mqtt_client {
    std::string uri, hostname, client_id, lwt_topic;
    int reconnect_ms = kDefaultReconnectMs;
    bool auto_reconnect = true, clean = true;
    bool started = false, connected = false, destroyed = false, had_session = false;
    uint64_t gen = 0;  // timers of an earlier start/stop cycle die when it changes
    std::vector<Handler> handlers;
    std::deque<Ev> events;
    TaskHandle_t task = nullptr;
    char key = 0;
    std::vector<std::pair<std::string, int>> subs;
    std::vector<Out> outbox;
    int next_id = 1;
};

namespace {

struct Incoming {
    int64_t t_ms;
    std::string topic, payload;
    int qos;
    bool retain;
};

std::vector<sim::Window> broker_down;
std::vector<Incoming> incoming;
std::vector<std::unique_ptr<esp_mqtt_client>> clients;

bool broker_up(int64_t t) {
    for (auto &w : broker_down) if (t >= w.from_ms && t < w.to_ms) return false;
    return true;
}

bool network_ok() { return !sim::wifi_in_use() || sim::wifi_has_ip(); }

esp_mqtt_client *live(esp_mqtt_client_handle_t h) {
    for (auto &c : clients) if (c.get() == h && !c->destroyed) return h;
    return nullptr;
}

// JSON text must be UTF-8: bytes that are not valid UTF-8 are shown as the Latin-1 characters they would be.
std::string utf8(const std::string &s) {
    size_t i = 0;
    bool ok = true;
    while (i < s.size() && ok) {
        unsigned char c = s[i];
        size_t n = c < 0x80 ? 1 : (c >> 5) == 6 ? 2 : (c >> 4) == 14 ? 3 : (c >> 3) == 30 ? 4 : 0;
        if (n == 0 || i + n > s.size()) { ok = false; break; }
        for (size_t k = 1; k < n; ++k) ok = ok && (static_cast<unsigned char>(s[i + k]) >> 6) == 2;
        i += n;
    }
    if (ok) return s;
    std::string out;
    for (unsigned char c : s) {
        if (c < 0x80) out += static_cast<char>(c);
        else { out += static_cast<char>(0xC0 | c >> 6); out += static_cast<char>(0x80 | (c & 0x3F)); }
    }
    return out;
}

bool topic_matches(const std::string &filter, const std::string &topic) {
    size_t f = 0, t = 0;
    while (true) {
        size_t fe = filter.find('/', f), te = topic.find('/', t);
        std::string fl = filter.substr(f, fe == std::string::npos ? std::string::npos : fe - f);
        std::string tl = topic.substr(t, te == std::string::npos ? std::string::npos : te - t);
        if (fl == "#") return true;
        if (fl != "+" && fl != tl) return false;
        if (fe == std::string::npos || te == std::string::npos) return fe == te;
        f = fe + 1;
        t = te + 1;
    }
}

const char *event_name(int id) {
    switch (id) {
        case MQTT_EVENT_ERROR: return "error";
        case MQTT_EVENT_CONNECTED: return "connected";
        case MQTT_EVENT_DISCONNECTED: return "disconnected";
        case MQTT_EVENT_SUBSCRIBED: return "subscribed";
        case MQTT_EVENT_UNSUBSCRIBED: return "unsubscribed";
        case MQTT_EVENT_PUBLISHED: return "published";
        case MQTT_EVENT_DATA: return "data";
        default: return "before_connect";
    }
}

void emit(esp_mqtt_client *c, Ev ev) {
    sim::Event t(sim::now_ms(), "mqtt");
    t.str("event", event_name(ev.id));
    if (ev.id == MQTT_EVENT_CONNECTED) {
        t.str("client_id", c->client_id);
        if (!c->lwt_topic.empty()) t.str("lwt_topic", c->lwt_topic);
    } else if (ev.id == MQTT_EVENT_DATA) {
        t.str("topic", utf8(ev.topic));
    } else if (ev.id == MQTT_EVENT_ERROR) {
        t.num("sock_errno", ev.sock_errno);
    }
    if (!c->task) return;  // stopped: nobody to deliver to
    c->events.push_back(std::move(ev));
    sim::notify(&c->key);
}

void dispatch(esp_mqtt_client *c, Ev &ev) {
    esp_mqtt_error_codes_t err = {};
    err.error_type = static_cast<esp_mqtt_error_type_t>(ev.error_type);
    err.esp_transport_sock_errno = ev.sock_errno;
    esp_mqtt_event_t e = {};
    e.event_id = static_cast<esp_mqtt_event_id_t>(ev.id);
    e.client = c;
    e.data = &ev.data[0];
    e.data_len = e.total_data_len = static_cast<int>(ev.data.size());
    e.topic = &ev.topic[0];
    e.topic_len = static_cast<int>(ev.topic.size());
    e.msg_id = ev.msg_id;
    e.session_present = ev.session_present;
    e.error_handle = &err;
    e.retain = ev.retain;
    e.qos = ev.qos;
    e.protocol_ver = MQTT_PROTOCOL_V_3_1_1;
    std::vector<Handler> snapshot = c->handlers;
    for (auto &h : snapshot)
        if (h.id == MQTT_EVENT_ANY || h.id == ev.id) h.fn(h.arg, MQTT_EVENTS, ev.id, &e);
}

void client_main(void *arg) {
    auto *c = static_cast<esp_mqtt_client *>(arg);
    for (;;) {
        sim::wait_for(&c->key, portMAX_DELAY, [c] { return !c->events.empty(); });
        Ev ev = std::move(c->events.front());
        c->events.pop_front();
        dispatch(c, ev);
    }
}

void send(esp_mqtt_client *c, const Out &m) {
    sim::Event(sim::now_ms(), "mqtt_publish").str("topic", utf8(m.topic)).str("payload", utf8(m.data))
        .flag("retain", m.retain).num("qos", m.qos).num("msg_id", m.id);
    if (m.qos > 0) {
        Ev ev{MQTT_EVENT_PUBLISHED};
        ev.msg_id = m.id;
        emit(c, std::move(ev));
    }
}

void begin_attempt(esp_mqtt_client *c);

void schedule_retry(esp_mqtt_client *c) {
    if (!c->auto_reconnect) return;
    uint64_t gen = c->gen;
    sim::at(sim::now_ms() + c->reconnect_ms, [c, gen] { if (gen == c->gen && c->started && !c->connected) begin_attempt(c); });
}

void finish_attempt(esp_mqtt_client *c, uint64_t gen) {
    if (gen != c->gen || !c->started || c->connected) return;
    if (!network_ok() || !broker_up(sim::now_ms())) {
        Ev ev{MQTT_EVENT_ERROR};
        ev.error_type = MQTT_ERROR_TYPE_TCP_TRANSPORT;
        ev.sock_errno = network_ok() ? ECONNREFUSED : EHOSTUNREACH;
        emit(c, std::move(ev));
        schedule_retry(c);
        return;
    }
    c->connected = true;
    Ev ev{MQTT_EVENT_CONNECTED};
    ev.session_present = !c->clean && c->had_session;
    if (c->clean) c->subs.clear();
    c->had_session = true;
    emit(c, std::move(ev));
    std::vector<Out> pending;
    pending.swap(c->outbox);
    for (auto &m : pending) send(c, m);
}

void begin_attempt(esp_mqtt_client *c) {
    if (!c->started) return;
    emit(c, Ev{MQTT_EVENT_BEFORE_CONNECT});
    uint64_t gen = c->gen;
    sim::at(sim::now_ms() + kConnectMs, [c, gen] { finish_attempt(c, gen); });
}

void drop(esp_mqtt_client *c) {
    if (!c->connected) return;
    c->connected = false;
    emit(c, Ev{MQTT_EVENT_DISCONNECTED});
    schedule_retry(c);
}

void halt(esp_mqtt_client *c) {
    c->started = c->connected = false;
    ++c->gen;
    c->events.clear();
    if (c->task) sim::remove(c->task);
    c->task = nullptr;
}

void deliver(const Incoming &m) {
    for (auto &c : clients) {
        if (!c->connected) continue;
        int qos = -1;
        for (auto &s : c->subs) if (topic_matches(s.first, m.topic)) qos = qos < 0 ? s.second : std::max(qos, s.second);
        if (qos < 0) continue;
        Ev ev{MQTT_EVENT_DATA};
        ev.topic = m.topic;
        ev.data = m.payload;
        ev.qos = std::min(qos, m.qos);
        ev.retain = m.retain;
        emit(c.get(), std::move(ev));
    }
}

}  // namespace

namespace sim {

bool mqtt_load_scenario(const Json &root, std::string &err) {
    const Json *m = root.get("mqtt");
    if (!m) return true;
    if (m->type != Json::Object) { err = "\"mqtt\" doit être un objet"; return false; }
    std::vector<Window> down;
    if (!parse_windows(m->get("broker_down"), "mqtt : \"broker_down\"", down, err)) return false;
    std::vector<Incoming> in;
    if (const Json *list = m->get("incoming")) {
        if (list->type != Json::Array) { err = "mqtt : \"incoming\" doit être un tableau"; return false; }
        for (const Json &e : list->arr) {
            long long t = 0, qos = 0;
            const Json *jt = e.type == Json::Object ? e.get("t_ms") : nullptr;
            const Json *jtopic = e.type == Json::Object ? e.get("topic") : nullptr;
            const Json *jp = e.type == Json::Object ? e.get("payload") : nullptr;
            const Json *jq = e.type == Json::Object ? e.get("qos") : nullptr;
            const Json *jr = e.type == Json::Object ? e.get("retain") : nullptr;
            if (!jt || !jt->as_int(0, INT64_MAX >> 12, t) || !jtopic || jtopic->type != Json::String || jtopic->str.empty() ||
                !jp || jp->type != Json::String || (jq && !jq->as_int(0, 2, qos)) || (jr && jr->type != Json::Bool)) {
                err = "mqtt : chaque \"incoming\" attend {\"t_ms\": entier >= 0, \"topic\": texte non vide, \"payload\": texte, "
                      "\"qos\"?: 0 à 2, \"retain\"?: booléen}";
                return false;
            }
            in.push_back({t, jtopic->str, jp->str, static_cast<int>(qos), jr && jr->b});
        }
    }
    std::stable_sort(in.begin(), in.end(), [](const Incoming &a, const Incoming &b) { return a.t_ms < b.t_ms; });
    broker_down = std::move(down);
    incoming = std::move(in);
    return true;
}

void mqtt_boot() {
    for (auto &w : broker_down) at(w.from_ms, [] { for (auto &c : clients) drop(c.get()); });
    for (auto &m : incoming) at(m.t_ms, [&m] { deliver(m); });
}

void mqtt_network_lost() {
    for (auto &c : clients) drop(c.get());
}

}  // namespace sim

extern "C" {

esp_mqtt_client_handle_t esp_mqtt_client_init(const esp_mqtt_client_config_t *config) {
    if (!config) return nullptr;
    auto c = std::make_unique<esp_mqtt_client>();
    if (config->broker.address.uri) c->uri = config->broker.address.uri;
    if (config->broker.address.hostname) c->hostname = config->broker.address.hostname;
    c->client_id = config->credentials.client_id ? config->credentials.client_id : "ESP32_000000";
    if (config->session.last_will.topic) c->lwt_topic = config->session.last_will.topic;
    if (config->network.reconnect_timeout_ms > 0) c->reconnect_ms = config->network.reconnect_timeout_ms;
    c->auto_reconnect = !config->network.disable_auto_reconnect;
    c->clean = !config->session.disable_clean_session;
    clients.push_back(std::move(c));
    return clients.back().get();
}

esp_err_t esp_mqtt_client_register_event(esp_mqtt_client_handle_t client, esp_mqtt_event_id_t event, esp_event_handler_t event_handler, void *event_handler_arg) {
    esp_mqtt_client *c = live(client);
    if (!c || !event_handler) return ESP_ERR_INVALID_ARG;
    c->handlers.push_back({event, event_handler, event_handler_arg});
    return ESP_OK;
}

esp_err_t esp_mqtt_client_start(esp_mqtt_client_handle_t client) {
    esp_mqtt_client *c = live(client);
    if (!c || (c->uri.empty() && c->hostname.empty())) return ESP_ERR_INVALID_ARG;
    if (c->started) return ESP_FAIL;
    c->started = true;
    c->task = sim::create_hidden(client_main, "mqtt_task", c);
    begin_attempt(c);
    return ESP_OK;
}

esp_err_t esp_mqtt_client_stop(esp_mqtt_client_handle_t client) {
    esp_mqtt_client *c = live(client);
    if (!c) return ESP_ERR_INVALID_ARG;
    if (!c->started) return ESP_FAIL;
    halt(c);
    return ESP_OK;
}

esp_err_t esp_mqtt_client_destroy(esp_mqtt_client_handle_t client) {
    esp_mqtt_client *c = live(client);
    if (!c) return ESP_ERR_INVALID_ARG;
    halt(c);
    c->destroyed = true;  // the object stays allocated: pending timers still point at it
    return ESP_OK;
}

int esp_mqtt_client_subscribe_single(esp_mqtt_client_handle_t client, const char *topic, int qos) {
    esp_mqtt_client *c = live(client);
    if (!c || !topic || !*topic || qos < 0 || qos > 2 || !c->connected) return -1;
    int id = c->next_id++;
    bool known = false;
    for (auto &s : c->subs) if (s.first == topic) { s.second = qos; known = true; }
    if (!known) c->subs.emplace_back(topic, qos);
    sim::Event(sim::now_ms(), "mqtt_subscribe").str("topic", utf8(topic)).num("qos", qos).num("msg_id", id);
    Ev ev{MQTT_EVENT_SUBSCRIBED};
    ev.msg_id = id;
    emit(c, std::move(ev));
    return id;
}

int esp_mqtt_client_unsubscribe(esp_mqtt_client_handle_t client, const char *topic) {
    esp_mqtt_client *c = live(client);
    if (!c || !topic || !*topic || !c->connected) return -1;
    int id = c->next_id++;
    for (auto it = c->subs.begin(); it != c->subs.end(); ++it) {
        if (it->first == topic) { c->subs.erase(it); break; }
    }
    Ev ev{MQTT_EVENT_UNSUBSCRIBED};
    ev.msg_id = id;
    emit(c, std::move(ev));
    return id;
}

int esp_mqtt_client_publish(esp_mqtt_client_handle_t client, const char *topic, const char *data, int len, int qos, int retain) {
    esp_mqtt_client *c = live(client);
    if (!c || !topic || !*topic || qos < 0 || qos > 2 || (!data && len > 0)) return -1;
    if (len <= 0) len = data ? static_cast<int>(std::strlen(data)) : 0;
    Out m{topic, std::string(data ? data : "", static_cast<size_t>(len)), qos, retain != 0, qos ? c->next_id++ : 0};
    if (c->connected) { send(c, m); return m.id; }
    if (qos == 0) return -1;
    c->outbox.push_back(std::move(m));
    return c->outbox.back().id;
}

}  // extern "C"
