// esp_https_ota / esp_ota_ops / esp_app_get_description shims: two OTA slots (ota_0, ota_1), their image states,
// the rollback, and a firmware server described by the scenario. Sections:
//   "ota": {"images": [{"url", "version", "valid", "drop_at_pct"}], "running_version", "previous_version"}
//       images: what the server holds, by exact URL. "valid": false is an image that downloads whole and fails
//       validation. "drop_at_pct" (null or 0 to 100): the connection is cut once that share of the image arrived.
//       version: at most 31 characters (esp_app_desc_t.version is char[32]).
//       running_version (default "1.0.0"): the version of the app that runs at the first boot; previous_version
//       (default "0.9.0"): the version in the other slot when "first_boot_after_ota" is set.
//   "boot": {"first_boot_after_ota": bool, "self_test_fails": bool}
//       first_boot_after_ota: the first boot is the first boot of a freshly installed image (slot ota_1, state
//       ESP_OTA_IMG_NEW, so PENDING_VERIFY at once as the bootloader makes it), the other slot holding
//       previous_version, valid. Without it the chip starts on ota_0 with an image that never went through OTA
//       (state ESP_OTA_IMG_UNDEFINED) and an empty ota_1.
//       self_test_fails: the new image is broken: while a PENDING_VERIFY image runs, MQTT cannot connect (the
//       broker looks unreachable). An application that validates itself only once it reached the broker will not.
//
// Behaviour taken from the ESP-IDF v5.5.3 docs (system/ota, esp_https_ota):
//   - CONFIG_BOOTLOADER_APP_ROLLBACK_ENABLE is on (sdkconfig.h). A new image starts in ESP_OTA_IMG_NEW, which the
//     bootloader turns into ESP_OTA_IMG_PENDING_VERIFY at its first boot; a reset while it is still PENDING_VERIFY
//     makes the bootloader abort it (ESP_OTA_IMG_ABORTED) and boot the previous app: event "rollback"
//     (why "not_validated"). esp_ota_mark_app_valid_cancel_rollback confirms it (ESP_OTA_IMG_VALID, ESP_OK;
//     also ESP_OK on an app that is already confirmed). esp_ota_mark_app_invalid_rollback_and_reboot marks the
//     running app as ESP_OTA_IMG_INVALID and restarts into the previous one (ESP_FAIL, and no restart, on an app with
//     no OTA-data entry, see below; ESP_ERR_OTA_ROLLBACK_FAILED, and no restart, when no other slot holds a bootable app); event "rollback" (why "marked_invalid"); restart reason SW.
//   - esp_https_ota writes the image into the other slot, does not restart (the application calls esp_restart) and,
//     on success, makes that slot the boot slot; ESP_OK. Failures (esp_https_ota.c and esp_http_client.c, v5.5.3):
//     ESP_ERR_INVALID_ARG (no config, no http_config, no URL, or no server-verification option at all: none of
//     cert_pem, crt_bundle_attach, use_global_ca_store (is_server_verification_enabled); refused before any connection, so
//     no trace event), ESP_ERR_HTTP_CONNECT (Wi-Fi without IP, server unreachable, TLS handshake failure: the error of
//     esp_http_client_open), ESP_FAIL (404, connection dropped during the download), ESP_ERR_OTA_VALIDATE_FAILED
//     (invalid image), ESP_ERR_OTA_ROLLBACK_INVALID_STATE (the running app is still PENDING_VERIFY: documented as
//     "a firmware upgrade is not possible"). The scheme is never read by esp_https_ota: an http:// URL is fetched in
//     clear text (cert_pem ignored, no handshake); the trace says so ("ota_begin" has cleartext: true), so that a TP can
//     refuse it. Whatever happens, the running slot and
//     the boot slot stay as they were until success; but the write erases the other slot, so after any failure
//     there is nothing to roll back to (esp_ota_check_rollback_is_possible is false).
//   - otadata: a slot has an OTA-data entry (and so a readable state) only once the OTA process chose it. A board
//     flashed by cable has none: the first app runs from ota_0 with no entry, esp_ota_get_state_partition then returns
//     ESP_ERR_NOT_FOUND and esp_ota_mark_app_valid_cancel_rollback returns ESP_FAIL (esp_ota_ops.c: "Running firmware is
//     factory"). An app with an entry whose state is not VALID (also UNDEFINED) becomes VALID. esp_ota_get_state_partition:
//     ESP_ERR_INVALID_ARG on a null argument, ESP_ERR_NOT_SUPPORTED for a partition that is not an OTA slot.
//
// Handed over to the next boot (the flash survives a reset), like the NVS: the boot slot, the version and state of
// both slots (boot.cpp). A reboot of any kind (esp_restart, watchdog, scripted power cycle) is the "reset" above.
//
// Timing (virtual): esp_https_ota blocks its caller (no thread is created): 100 ms to connect (the TLS handshake
// is traced then), then 20 ms per percent of the image, 2100 ms in all; the other tasks keep running.
//
// Simplifications: no image bytes, no sizes, no flash wear; the "valid" flag is the image check (magic byte,
// chip id, checksum and signature in ESP-IDF); no secure version or ESP_ERR_OTA_SMALL_SEC_VER; one slot pair (no
// factory partition, no ota_2..); esp_https_ota_begin/perform/finish/abort, esp_ota_begin/write/end,
// esp_ota_set_boot_partition and the http_client_init_cb are not provided or not called; a link loss during the
// download (Wi-Fi) is not detected (only the scenario's drop_at_pct); the URL needs no other scheme than http(s);
// the partition table addresses are samples; HTTP redirects, proxies and range
// requests are not simulated.
#include <cstring>
#include <sstream>

#include "esp_app_desc.h"
#include "esp_http_client.h"
#include "esp_https_ota.h"
#include "esp_ota_ops.h"
#include "esp_tls.h"
#include "sim.h"

namespace {

struct Image {
    std::string url, version;
    bool valid;
    int drop_pct;  // -1: none
};

struct Slot {
    std::string version;  // empty: nothing bootable
    uint32_t state = ESP_OTA_IMG_UNDEFINED;
    bool otadata = false;  // the OTA data partition holds an entry for this slot
};

constexpr int64_t kConnectMs = 100;
constexpr int kTicksPerPercent = 2;  // 20 ms
constexpr size_t kVersionMax = 31;

std::vector<Image> images;
std::string running_version = "1.0.0", previous_version = "0.9.0";
bool first_boot_after_ota = false, self_test_fails = false;

Slot slots[2];
int boot_slot = 0;     // the slot the next boot runs (otadata)
int running = 0;       // the slot this boot runs
bool restored = false;

esp_partition_t parts[2] = {
    {nullptr, ESP_PARTITION_TYPE_APP, ESP_PARTITION_SUBTYPE_APP_OTA_0, 0x110000, 0x100000, 0x1000, "ota_0", false, false},
    {nullptr, ESP_PARTITION_TYPE_APP, ESP_PARTITION_SUBTYPE_APP_OTA_1, 0x210000, 0x100000, 0x1000, "ota_1", false, false},
};

bool bootable(const Slot &s) {
    return !s.version.empty() && s.state != ESP_OTA_IMG_INVALID && s.state != ESP_OTA_IMG_ABORTED;
}

const char *hex_digits = "0123456789abcdef";

std::string enc(const std::string &s) {
    if (s.empty()) return "-";
    std::string out = "_";
    for (unsigned char c : s) { out += hex_digits[c >> 4]; out += hex_digits[c & 15]; }
    return out;
}

std::string dec(const std::string &s) {
    std::string out;
    for (size_t i = 1; i + 1 < s.size(); i += 2) out += static_cast<char>(std::stoi(s.substr(i, 2), nullptr, 16));
    return out;
}

void emit_rollback(const char *why, const std::string &from, const std::string &to) {
    sim::Event(sim::now_ms(), "rollback").str("why", why).str("from", sim::utf8(from)).str("to", sim::utf8(to));
}

bool string_field(const sim::Json &o, const char *key, size_t max, std::string &out, const char *where, std::string &err) {
    const sim::Json *v = o.get(key);
    if (!v) return true;
    if (v->type != sim::Json::String || v->str.empty() || v->str.size() > max) {
        err = std::string(where) + " : \"" + key + "\" doit être un texte de 1 à " + std::to_string(max) + " caractères";
        return false;
    }
    out = v->str;
    return true;
}

bool bool_field(const sim::Json &o, const char *key, bool &out, const char *where, std::string &err) {
    const sim::Json *v = o.get(key);
    if (!v) return true;
    if (v->type != sim::Json::Bool) { err = std::string(where) + " : \"" + key + "\" doit être un booléen"; return false; }
    out = v->b;
    return true;
}

}  // namespace

namespace sim {

bool ota_load_scenario(const Json &root, std::string &err) {
    std::vector<Image> list;
    std::string run_v = "1.0.0", prev_v = "0.9.0";
    if (const Json *o = root.get("ota")) {
        if (o->type != Json::Object) { err = "\"ota\" doit être un objet"; return false; }
        if (!only_keys(*o, {"images", "running_version", "previous_version"}, "ota", err)) return false;
        if (!string_field(*o, "running_version", kVersionMax, run_v, "ota", err) ||
            !string_field(*o, "previous_version", kVersionMax, prev_v, "ota", err)) return false;
        if (const Json *l = o->get("images")) {
            if (l->type != Json::Array) { err = "ota : \"images\" doit être un tableau"; return false; }
            for (const Json &e : l->arr) {
                if (e.type != Json::Object) { err = "ota : chaque image attend un objet {\"url\", \"version\", \"valid\", \"drop_at_pct\"}"; return false; }
                if (!only_keys(e, {"url", "version", "valid", "drop_at_pct"}, "ota : \"images\"", err)) return false;
                Image im{"", "", false, -1};
                const Json *url = e.get("url"), *ver = e.get("version"), *valid = e.get("valid"), *drop = e.get("drop_at_pct");
                long long pct = -1;
                if (!url || !ver || !valid || valid->type != Json::Bool ||
                    (drop && drop->type != Json::Null && !drop->as_int(0, 100, pct))) {
                    err = "ota : chaque image attend {\"url\": texte, \"version\": texte, \"valid\": booléen, \"drop_at_pct\"?: null ou 0 à 100}";
                    return false;
                }
                if (!string_field(e, "url", 2048, im.url, "ota : \"images\"", err) ||
                    !string_field(e, "version", kVersionMax, im.version, "ota : \"images\"", err)) return false;
                im.valid = valid->b;
                im.drop_pct = static_cast<int>(pct);
                for (const Image &other : list)
                    if (other.url == im.url) { err = "ota : l'URL \"" + im.url + "\" figure deux fois dans \"images\""; return false; }
                list.push_back(std::move(im));
            }
        }
    }
    bool first = false, broken = false;
    if (const Json *b = root.get("boot")) {
        if (b->type != Json::Object) { err = "\"boot\" doit être un objet"; return false; }
        if (!only_keys(*b, {"first_boot_after_ota", "self_test_fails"}, "boot", err)) return false;
        if (!bool_field(*b, "first_boot_after_ota", first, "boot", err) || !bool_field(*b, "self_test_fails", broken, "boot", err)) return false;
    }
    images = std::move(list);
    running_version = run_v;
    previous_version = prev_v;
    first_boot_after_ota = first;
    self_test_fails = broken;
    return true;
}

void ota_save(std::ostream &out) {
    out << "ota " << boot_slot << " " << enc(slots[0].version) << " " << slots[0].state << " " << slots[0].otadata << " "
        << enc(slots[1].version) << " " << slots[1].state << " " << slots[1].otadata << "\n";
}

void ota_restore(std::istream &in) {
    std::string v0, v1;
    if (in >> boot_slot >> v0 >> slots[0].state >> slots[0].otadata >> v1 >> slots[1].state >> slots[1].otadata) {
        slots[0].version = dec(v0);
        slots[1].version = dec(v1);
        restored = true;
    }
}

// The bootloader's work, before app_main.
void ota_boot() {
    if (!restored) {
        slots[0] = {running_version, ESP_OTA_IMG_UNDEFINED, false};
        slots[1] = {"", ESP_OTA_IMG_UNDEFINED, false};
        boot_slot = 0;
        if (first_boot_after_ota) {
            slots[0] = {previous_version, ESP_OTA_IMG_VALID, true};
            slots[1] = {running_version, ESP_OTA_IMG_NEW, true};
            boot_slot = 1;
        }
    }
    running = boot_slot;
    Slot &s = slots[running];
    if (s.state == ESP_OTA_IMG_NEW) {
        s.state = ESP_OTA_IMG_PENDING_VERIFY;
    } else if (s.state == ESP_OTA_IMG_PENDING_VERIFY) {  // reset without confirmation
        s.state = ESP_OTA_IMG_ABORTED;
        const Slot &previous = slots[1 - running];
        if (!bootable(previous)) {
            Event(now_ms(), "log").str("level", "E").str("tag", "boot").str("msg", "No bootable app partitions in the partition table");
            end("abort");
        }
        emit_rollback("not_validated", s.version, previous.version);
        running = boot_slot = 1 - running;
    }
}

bool ota_self_test_broken() { return self_test_fails && slots[running].state == ESP_OTA_IMG_PENDING_VERIFY; }

}  // namespace sim

extern "C" {

const esp_app_desc_t *esp_app_get_description(void) {
    static esp_app_desc_t desc;
    std::memset(&desc, 0, sizeof desc);
    desc.magic_word = ESP_APP_DESC_MAGIC_WORD;
    std::strncpy(desc.version, slots[running].version.c_str(), sizeof desc.version - 1);
    std::strncpy(desc.project_name, "esp-sim", sizeof desc.project_name - 1);
    std::strncpy(desc.idf_ver, "v5.5.3", sizeof desc.idf_ver - 1);
    return &desc;
}

const esp_partition_t *esp_ota_get_running_partition(void) { return &parts[running]; }

esp_err_t esp_ota_get_state_partition(const esp_partition_t *partition, esp_ota_img_states_t *ota_state) {
    if (!partition || !ota_state) return ESP_ERR_INVALID_ARG;
    for (int i = 0; i < 2; ++i) {
        if (partition != &parts[i]) continue;
        if (!slots[i].otadata) return ESP_ERR_NOT_FOUND;
        *ota_state = static_cast<esp_ota_img_states_t>(slots[i].state);
        return ESP_OK;
    }
    return ESP_ERR_NOT_SUPPORTED;
}

esp_err_t esp_ota_mark_app_valid_cancel_rollback(void) {
    Slot &s = slots[running];
    if (!s.otadata) return ESP_FAIL;  // "Running firmware is factory"
    s.state = ESP_OTA_IMG_VALID;
    sim::Event(sim::now_ms(), "ota_mark").flag("valid", true);
    return ESP_OK;
}

esp_err_t esp_ota_mark_app_invalid_rollback_and_reboot(void) {
    if (!slots[running].otadata) return ESP_FAIL;  // "Running firmware is factory", tested before the rollback target
    const Slot &previous = slots[1 - running];
    if (!bootable(previous)) return ESP_ERR_OTA_ROLLBACK_FAILED;
    sim::Event(sim::now_ms(), "ota_mark").flag("valid", false);
    emit_rollback("marked_invalid", slots[running].version, previous.version);
    slots[running].state = ESP_OTA_IMG_INVALID;
    boot_slot = 1 - running;
    sim::reboot("sw");
}

const esp_partition_t *esp_ota_get_last_invalid_partition(void) {
    for (int i = 0; i < 2; ++i)
        if (slots[i].state == ESP_OTA_IMG_INVALID || slots[i].state == ESP_OTA_IMG_ABORTED) return &parts[i];
    return nullptr;
}

bool esp_ota_check_rollback_is_possible(void) { return bootable(slots[1 - running]); }

esp_err_t esp_https_ota(const esp_https_ota_config_t *config) {
    if (!config || !config->http_config || !config->http_config->url || !*config->http_config->url) return ESP_ERR_INVALID_ARG;
    const esp_http_client_config_t &http = *config->http_config;
    std::string url = http.url;
    bool cleartext = url.compare(0, 7, "http://") == 0;
    if (!cleartext && url.compare(0, 8, "https://") != 0) return ESP_ERR_INVALID_ARG;
    if (!http.cert_pem && !http.crt_bundle_attach && !http.use_global_ca_store)
        return ESP_ERR_INVALID_ARG;  // "No option for server verification is enabled in esp_http_client config."
    int64_t begin = sim::now_ms();
    sim::Event(begin, "ota_begin").str("url", sim::utf8(url)).flag("cleartext", cleartext);
    auto finish = [&](esp_err_t e) {
        sim::Event(sim::now_ms(), "ota_end").str("url", sim::utf8(url)).flag("ok", e == ESP_OK).str("err", esp_err_to_name(e));
        return e;
    };
    if (sim::wifi_in_use() && !sim::wifi_has_ip()) return finish(ESP_ERR_HTTP_CONNECT);
    sim::delay(static_cast<TickType_t>(sim::tick_of(kConnectMs)));
    if (!cleartext) {
        sim::TlsPeer peer = sim::tls_peer(http.cert_pem, http.cert_len, http.crt_bundle_attach != nullptr, http.use_global_ca_store,
                                          http.skip_cert_common_name_check, http.common_name);
        if (!sim::tls_handshake(peer, sim::uri_host(url)).ok) return finish(ESP_ERR_HTTP_CONNECT);
    }
    const Image *img = nullptr;
    for (const Image &i : images) if (i.url == url) img = &i;
    if (!img) return finish(ESP_FAIL);  // HTTP 404
    if (slots[running].state == ESP_OTA_IMG_PENDING_VERIFY) return finish(ESP_ERR_OTA_ROLLBACK_INVALID_STATE);
    // esp_ota_begin erases the other slot: from here on it holds no bootable app, whatever the outcome.
    Slot &target = slots[1 - running];
    target = {"", ESP_OTA_IMG_UNDEFINED, false};
    int received = 0;
    for (; received < 100; ++received) {
        if (img->drop_pct >= 0 && received == img->drop_pct) return finish(ESP_FAIL);
        sim::delay(kTicksPerPercent);
    }
    if (img->drop_pct == 100) return finish(ESP_FAIL);
    if (!img->valid) return finish(ESP_ERR_OTA_VALIDATE_FAILED);
    target = {img->version, ESP_OTA_IMG_NEW, true};
    boot_slot = 1 - running;
    return finish(ESP_OK);
}

}  // extern "C"
