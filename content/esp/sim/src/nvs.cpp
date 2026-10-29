// nvs.h / nvs_flash.h shim: the default "nvs" partition, integers, strings and blobs.
//
// Persistence: the simulator keeps two copies, the working one (what reads and writes see) and the committed
// one (what a restart keeps; handed over to the next boot, see boot.cpp). nvs_commit(handle) copies the
// handle's namespace from working to committed; a write that was not committed is lost at a restart. This is
// stricter than the real implementation, which writes flash right away (the docs only promise that
// nvs_commit makes the writes durable and that nvs_close may not): the sim enforces the documented contract,
// so that code which forgets nvs_commit fails here instead of working by luck. Everything a reset erases
// (open handles, the "initialised" state) is fresh at each boot, because the binary really restarts.
//
// Simplifications: no flash wear, pages or free-space accounting (nvs_flash_init never returns
// ESP_ERR_NVS_NO_FREE_PAGES, writes never return ESP_ERR_NVS_NOT_ENOUGH_SPACE); only the default partition;
// a namespace created by nvs_open(NVS_READWRITE) exists at once, committed or not; null pointers return
// ESP_ERR_INVALID_ARG where the real code would crash; an empty key is ESP_ERR_NVS_INVALID_NAME.
// Trace: nvs_set (each set_*) and nvs_commit.
#include <cstring>
#include <map>
#include <sstream>
#include <vector>

#include "nvs_flash.h"
#include "sim.h"

namespace {

enum Type { U8 = 0x01, I8 = 0x11, U16 = 0x02, I16 = 0x12, U32 = 0x04, I32 = 0x14, U64 = 0x08, I64 = 0x18, STR = 0x21, BLOB = 0x42 };

constexpr size_t kKeyMax = 15;        // NVS_KEY_NAME_MAX_SIZE - 1
constexpr size_t kStrMax = 4000;      // including the terminator
constexpr size_t kBlobMax = 508000;

struct Value {
    int type;
    std::vector<unsigned char> bytes;
};
using Space = std::map<std::string, std::map<std::string, Value>>;

Space working, committed;
bool initialised = false;
struct Handle {
    std::string ns;
    bool writable;
};
std::map<nvs_handle_t, Handle> handles;
nvs_handle_t next_handle = 1;

const char *type_name(int t) {
    switch (t) {
        case U8: return "u8"; case I8: return "i8"; case U16: return "u16"; case I16: return "i16";
        case U32: return "u32"; case I32: return "i32"; case U64: return "u64"; case I64: return "i64";
        case STR: return "str"; default: return "blob";
    }
}

esp_err_t check_key(const char *key) {
    if (!key) return ESP_ERR_INVALID_ARG;
    size_t n = std::strlen(key);
    if (n == 0) return ESP_ERR_NVS_INVALID_NAME;
    return n > kKeyMax ? ESP_ERR_NVS_KEY_TOO_LONG : ESP_OK;
}

esp_err_t lookup(nvs_handle_t h, Handle *&out) {
    if (!initialised) return ESP_ERR_NVS_NOT_INITIALIZED;
    auto it = handles.find(h);
    if (it == handles.end()) return ESP_ERR_NVS_INVALID_HANDLE;
    out = &it->second;
    return ESP_OK;
}

esp_err_t store(nvs_handle_t h, const char *key, int type, const void *data, size_t n, const std::string &shown) {
    Handle *hd;
    if (esp_err_t e = lookup(h, hd)) return e;
    if (esp_err_t e = check_key(key)) return e;
    if (!hd->writable) return ESP_ERR_NVS_READ_ONLY;
    auto *b = static_cast<const unsigned char *>(data);
    working[hd->ns][key] = Value{type, std::vector<unsigned char>(b, b + n)};
    sim::Event e(sim::now_ms(), "nvs_set");
    e.str("ns", hd->ns).str("key", key).str("type", type_name(type));
    if (type == STR) e.str("value", shown);
    else if (type == BLOB) e.num("size", static_cast<int64_t>(n));
    else if (type == U64 && std::strtoull(shown.c_str(), nullptr, 10) > static_cast<uint64_t>(INT64_MAX)) e.str("value", shown);
    else e.num("value", std::strtoll(shown.c_str(), nullptr, 10));
    return ESP_OK;
}

esp_err_t fetch(nvs_handle_t h, const char *key, int type, const Value *&out) {
    Handle *hd;
    if (esp_err_t e = lookup(h, hd)) return e;
    if (esp_err_t e = check_key(key)) return e;
    auto ns = working.find(hd->ns);
    if (ns == working.end()) return ESP_ERR_NVS_NOT_FOUND;
    auto it = ns->second.find(key);
    if (it == ns->second.end()) return ESP_ERR_NVS_NOT_FOUND;
    if (it->second.type != type) return ESP_ERR_NVS_TYPE_MISMATCH;
    out = &it->second;
    return ESP_OK;
}

template <typename T, int Ty>
esp_err_t set_int(nvs_handle_t h, const char *key, T v) {
    return store(h, key, Ty, &v, sizeof v, std::to_string(v));
}

template <typename T, int Ty>
esp_err_t get_int(nvs_handle_t h, const char *key, T *out) {
    if (!out) return ESP_ERR_INVALID_ARG;
    const Value *v;
    if (esp_err_t e = fetch(h, key, Ty, v)) return e;
    std::memcpy(out, v->bytes.data(), sizeof(T));
    return ESP_OK;
}

// Length protocol of nvs_get_str / nvs_get_blob: out == NULL asks for the size.
esp_err_t get_bytes(nvs_handle_t h, const char *key, int type, void *out, size_t *length) {
    const Value *v;
    if (esp_err_t e = fetch(h, key, type, v)) return e;  // the key is looked up first, as in nvs_get_str_or_blob
    if (!length) return ESP_ERR_NVS_INVALID_LENGTH;
    if (!out) { *length = v->bytes.size(); return ESP_OK; }
    if (*length < v->bytes.size()) { *length = v->bytes.size(); return ESP_ERR_NVS_INVALID_LENGTH; }
    std::memcpy(out, v->bytes.data(), v->bytes.size());
    *length = v->bytes.size();
    return ESP_OK;
}

std::string hex(const std::string &s) {
    static const char d[] = "0123456789abcdef";
    std::string out = "x";  // never empty, so a field is always one token
    for (unsigned char c : s) { out += d[c >> 4]; out += d[c & 15]; }
    return out;
}

std::string unhex(const std::string &s) {
    std::string out;
    for (size_t i = 1; i + 1 < s.size(); i += 2) out += static_cast<char>(std::stoi(s.substr(i, 2), nullptr, 16));
    return out;
}

}  // namespace

namespace sim {

bool nvs_ready() { return initialised; }

void nvs_save(std::ostream &o) {
    for (auto &ns : committed) {
        o << "nvs.ns " << hex(ns.first) << "\n";
        for (auto &kv : ns.second)
            o << "nvs.val " << hex(ns.first) << " " << hex(kv.first) << " " << kv.second.type << " "
              << hex(std::string(kv.second.bytes.begin(), kv.second.bytes.end())) << "\n";
    }
}

void nvs_restore(const std::string &key, std::istream &in) {
    std::string ns, k, data;
    int type = 0;
    if (key == "nvs.ns" && in >> ns) committed[unhex(ns)];
    else if (key == "nvs.val" && in >> ns >> k >> type >> data) {
        std::string d = unhex(data);
        committed[unhex(ns)][unhex(k)] = Value{type, std::vector<unsigned char>(d.begin(), d.end())};
    }
    working = committed;
}

}  // namespace sim

extern "C" {

esp_err_t nvs_flash_init(void) {
    initialised = true;
    return ESP_OK;
}

esp_err_t nvs_flash_deinit(void) {
    if (!initialised) return ESP_ERR_NVS_NOT_INITIALIZED;
    initialised = false;
    handles.clear();
    return ESP_OK;
}

// As documented, an initialised partition is de-initialised first.
esp_err_t nvs_flash_erase(void) {
    initialised = false;
    handles.clear();
    working.clear();
    committed.clear();
    return ESP_OK;
}

esp_err_t nvs_open(const char *namespace_name, nvs_open_mode_t open_mode, nvs_handle_t *out_handle) {
    if (!initialised) return ESP_ERR_NVS_NOT_INITIALIZED;
    if (!namespace_name || !out_handle || (open_mode != NVS_READONLY && open_mode != NVS_READWRITE)) return ESP_ERR_INVALID_ARG;
    size_t n = std::strlen(namespace_name);
    if (n == 0 || n > kKeyMax) return ESP_ERR_NVS_INVALID_NAME;
    if (!working.count(namespace_name)) {
        if (open_mode == NVS_READONLY) return ESP_ERR_NVS_NOT_FOUND;
        working[namespace_name];
        committed[namespace_name];
    }
    handles[next_handle] = Handle{namespace_name, open_mode == NVS_READWRITE};
    *out_handle = next_handle++;
    return ESP_OK;
}

esp_err_t nvs_set_i8(nvs_handle_t h, const char *k, int8_t v) { return set_int<int8_t, I8>(h, k, v); }
esp_err_t nvs_set_u8(nvs_handle_t h, const char *k, uint8_t v) { return set_int<uint8_t, U8>(h, k, v); }
esp_err_t nvs_set_i16(nvs_handle_t h, const char *k, int16_t v) { return set_int<int16_t, I16>(h, k, v); }
esp_err_t nvs_set_u16(nvs_handle_t h, const char *k, uint16_t v) { return set_int<uint16_t, U16>(h, k, v); }
esp_err_t nvs_set_i32(nvs_handle_t h, const char *k, int32_t v) { return set_int<int32_t, I32>(h, k, v); }
esp_err_t nvs_set_u32(nvs_handle_t h, const char *k, uint32_t v) { return set_int<uint32_t, U32>(h, k, v); }
esp_err_t nvs_set_i64(nvs_handle_t h, const char *k, int64_t v) { return set_int<int64_t, I64>(h, k, v); }
esp_err_t nvs_set_u64(nvs_handle_t h, const char *k, uint64_t v) { return set_int<uint64_t, U64>(h, k, v); }

esp_err_t nvs_set_str(nvs_handle_t h, const char *key, const char *value) {
    if (!value) return ESP_ERR_INVALID_ARG;
    size_t n = std::strlen(value) + 1;
    if (n > kStrMax) return ESP_ERR_NVS_VALUE_TOO_LONG;
    return store(h, key, STR, value, n, value);
}

esp_err_t nvs_set_blob(nvs_handle_t h, const char *key, const void *value, size_t length) {
    if (!value && length > 0) return ESP_ERR_INVALID_ARG;
    if (length > kBlobMax) return ESP_ERR_NVS_VALUE_TOO_LONG;
    return store(h, key, BLOB, value, length, "");
}

esp_err_t nvs_get_i8(nvs_handle_t h, const char *k, int8_t *o) { return get_int<int8_t, I8>(h, k, o); }
esp_err_t nvs_get_u8(nvs_handle_t h, const char *k, uint8_t *o) { return get_int<uint8_t, U8>(h, k, o); }
esp_err_t nvs_get_i16(nvs_handle_t h, const char *k, int16_t *o) { return get_int<int16_t, I16>(h, k, o); }
esp_err_t nvs_get_u16(nvs_handle_t h, const char *k, uint16_t *o) { return get_int<uint16_t, U16>(h, k, o); }
esp_err_t nvs_get_i32(nvs_handle_t h, const char *k, int32_t *o) { return get_int<int32_t, I32>(h, k, o); }
esp_err_t nvs_get_u32(nvs_handle_t h, const char *k, uint32_t *o) { return get_int<uint32_t, U32>(h, k, o); }
esp_err_t nvs_get_i64(nvs_handle_t h, const char *k, int64_t *o) { return get_int<int64_t, I64>(h, k, o); }
esp_err_t nvs_get_u64(nvs_handle_t h, const char *k, uint64_t *o) { return get_int<uint64_t, U64>(h, k, o); }

esp_err_t nvs_get_str(nvs_handle_t h, const char *key, char *out_value, size_t *length) { return get_bytes(h, key, STR, out_value, length); }
esp_err_t nvs_get_blob(nvs_handle_t h, const char *key, void *out_value, size_t *length) { return get_bytes(h, key, BLOB, out_value, length); }

esp_err_t nvs_erase_key(nvs_handle_t h, const char *key) {
    Handle *hd;
    if (esp_err_t e = lookup(h, hd)) return e;
    if (esp_err_t e = check_key(key)) return e;
    if (!hd->writable) return ESP_ERR_NVS_READ_ONLY;
    return working[hd->ns].erase(key) ? ESP_OK : ESP_ERR_NVS_NOT_FOUND;
}

esp_err_t nvs_erase_all(nvs_handle_t h) {
    Handle *hd;
    if (esp_err_t e = lookup(h, hd)) return e;
    if (!hd->writable) return ESP_ERR_NVS_READ_ONLY;
    working[hd->ns].clear();
    return ESP_OK;
}

esp_err_t nvs_commit(nvs_handle_t h) {
    Handle *hd;
    if (esp_err_t e = lookup(h, hd)) return e;
    if (!hd->writable) return ESP_ERR_NVS_READ_ONLY;
    committed[hd->ns] = working[hd->ns];
    sim::Event(sim::now_ms(), "nvs_commit").str("ns", hd->ns);
    return ESP_OK;
}

// Pending writes are not discarded by closing: they stay readable and can still be committed through
// another handle of the namespace, but nothing makes them durable except nvs_commit.
void nvs_close(nvs_handle_t h) { handles.erase(h); }

}  // extern "C"
