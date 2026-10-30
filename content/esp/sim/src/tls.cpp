// TLS toward the scenario's server, shared by esp-mqtt (mqtts://) and esp_https_ota (https://). Section "tls":
//   "server_cert_valid": false: the server presents an expired certificate (default true)
//   "handshake_fail": [{"from_ms", "to_ms"}]: the server closes the connection during the handshake in [from, to)
//   "server_cert": the PEM of the server certificate (self-signed, so it is its own CA). The check driver makes it
//                  at run time (esp_check.py) and passes it here: the repository holds no certificate and no key.
//                  The simulator also exposes it to the program as the symbol _binary_server_cert_pem_start (a
//                  NUL-terminated string), what EMBED_TXTFILES "server_cert.pem" gives in a real project. Absent:
//                  any well-formed certificate of the client is trusted. At most 8191 bytes.
//   "server_cn": the common name of that certificate (default: the host of the URL, so the name matches)
//   "public_ca": true: the server certificate is signed by a public CA, so the certificate bundle and the global
//                  CA store trust it (default false: a private broker, which they do not trust)
//
// Decisions, from the ESP-IDF v5.5.3 docs of esp-tls, esp-mqtt and esp_https_ota:
//   - Verification options are the client certificate (esp-mqtt broker.verification.certificate, esp_http_client
//     cert_pem: PEM with its NUL, or DER with its length), the global CA store or the certificate bundle. With none
//     of them the connection fails at setup: the docs say "the client will return a fatal error by default" (the
//     insecure CONFIG_ESP_TLS_INSECURE mode is not simulated). Error: ESP_ERR_MBEDTLS_SSL_SETUP_FAILED.
//   - The client certificate must be the server's (self-signed: its own CA). The bundle and the global store are
//     the same thing here (a public store, no esp_tls_set_global_ca_store call needed).
//   - The name checked is broker.verification.common_name (esp_http_client: common_name) or else the host of the URL;
//     skip_cert_common_name_check (a security reduction according to the docs) bypasses only that check: the
//     handshake still fails on an untrusted or expired certificate, and the trace says "cn_skipped" whenever the
//     flag is set, whether or not the name would have matched.
//   - Errors as esp-tls reports them (esp_tls_last_esp_err, esp_tls_stack_err, esp_tls_cert_verify_flags):
//       verification failed: ESP_ERR_MBEDTLS_SSL_HANDSHAKE_FAILED, MBEDTLS_ERR_X509_CERT_VERIFY_FAILED (-0x2700),
//       flags BADCERT_EXPIRED 0x01 | BADCERT_CN_MISMATCH 0x04 | BADCERT_NOT_TRUSTED 0x08 (the mbedTLS values);
//       server closes: ESP_ERR_MBEDTLS_SSL_HANDSHAKE_FAILED, MBEDTLS_ERR_SSL_CONN_EOF (-0x7280);
//       unparsable certificate: ESP_ERR_MBEDTLS_X509_CRT_PARSE_FAILED, MBEDTLS_ERR_PEM_NO_HEADER_FOOTER_PRESENT (-0x1080).
//     The docs name the three fields and not these values: they are the mbedTLS constants esp-tls forwards
//     (sign of esp_tls_stack_err: the mbedTLS return value, negative).
// Trace: "tls_handshake" {host, ok, verify}; verify = ok | cn_skipped | failed:no_verification | failed:parse |
// failed:handshake | failed:not_trusted | failed:expired | failed:cn_mismatch (the first failing check).
//
// Simplifications: no key exchange, no cipher suites or protocol versions (alpn_protos, ciphersuites_list and the PSK
// are ignored), no client certificate (mutual TLS), no session tickets, no certificate chain or revocation: the
// certificate of the client is compared with the server's, ignoring white space; the dates of the certificate are
// not read (expiry is the scenario's "server_cert_valid"); a TLS handshake takes no virtual time of its own.
#include <algorithm>
#include <cctype>
#include <cstring>

#include "esp_crt_bundle.h"
#include "esp_tls.h"
#include "sim.h"

extern "C" {
// What EMBED_TXTFILES makes of the server certificate in a real project (PEM, NUL-terminated).
char _binary_server_cert_pem_start[8192];
}

namespace {

constexpr int kVerifyFailed = -0x2700, kConnEof = -0x7280, kPemNoHeader = -0x1080;
constexpr int kBadExpired = 0x01, kBadCnMismatch = 0x04, kBadNotTrusted = 0x08;

bool server_valid = true, public_ca = false;
std::vector<sim::Window> fail_windows;
std::string server_cert, server_cn;

std::string squash(const std::string &s) {
    std::string out;
    for (char c : s) if (!std::isspace(static_cast<unsigned char>(c))) out += c;
    return out;
}

bool well_formed(const std::string &pem) {
    size_t b = pem.find("-----BEGIN CERTIFICATE-----");
    return b != std::string::npos && pem.find("-----END CERTIFICATE-----", b) != std::string::npos;
}

}  // namespace

extern "C" esp_err_t esp_crt_bundle_attach(void *) { return ESP_OK; }

namespace sim {

bool tls_load_scenario(const Json &root, std::string &err) {
    const Json *t = root.get("tls");
    if (!t) return true;
    if (t->type != Json::Object) { err = "\"tls\" doit être un objet"; return false; }
    if (!only_keys(*t, {"server_cert_valid", "handshake_fail", "server_cert", "server_cn", "public_ca"}, "tls", err)) return false;
    const Json *valid = t->get("server_cert_valid"), *ca = t->get("public_ca"), *cert = t->get("server_cert"), *cn = t->get("server_cn");
    if ((valid && valid->type != Json::Bool) || (ca && ca->type != Json::Bool)) {
        err = "tls : \"server_cert_valid\" et \"public_ca\" doivent être des booléens";
        return false;
    }
    if (cert && (cert->type != Json::String || cert->str.size() >= sizeof _binary_server_cert_pem_start)) {
        err = "tls : \"server_cert\" doit être un texte PEM de moins de 8192 octets";
        return false;
    }
    if (cn && (cn->type != Json::String || cn->str.empty())) { err = "tls : \"server_cn\" doit être un texte non vide"; return false; }
    std::vector<Window> windows;
    if (!parse_windows(t->get("handshake_fail"), "tls : \"handshake_fail\"", windows, err)) return false;
    server_valid = !valid || valid->b;
    public_ca = ca && ca->b;
    server_cert = cert ? cert->str : "";
    server_cn = cn ? cn->str : "";
    fail_windows = std::move(windows);
    std::memset(_binary_server_cert_pem_start, 0, sizeof _binary_server_cert_pem_start);
    std::memcpy(_binary_server_cert_pem_start, server_cert.data(), server_cert.size());
    return true;
}

std::string uri_host(const std::string &uri) {
    size_t s = uri.find("://");
    std::string rest = s == std::string::npos ? uri : uri.substr(s + 3);
    rest = rest.substr(0, rest.find_first_of("/?#"));
    if (size_t at = rest.rfind('@'); at != std::string::npos) rest = rest.substr(at + 1);
    if (!rest.empty() && rest[0] == '[') return rest.substr(1, rest.find(']') == std::string::npos ? std::string::npos : rest.find(']') - 1);
    return rest.substr(0, rest.find(':'));
}

TlsPeer tls_peer(const char *cert, size_t len, bool bundle, bool global_store, bool skip_cn, const char *cn) {
    TlsPeer p;
    p.public_store = bundle || global_store;
    p.skip_cn = skip_cn;
    if (cn) p.common_name = cn;
    if (cert) {
        p.has_cert = true;
        // PEM ends with its NUL (a length, when given, counts it); anything else is taken for DER, which is not read.
        if (len == 0) p.pem = cert;
        else if (cert[len - 1] == '\0') p.pem = std::string(cert, strnlen(cert, len));
        else p.binary = true;
    }
    return p;
}

TlsResult tls_handshake(const TlsPeer &peer, const std::string &host) {
    TlsResult r{true, ESP_OK, 0, 0, peer.skip_cn ? "cn_skipped" : "ok"};
    int64_t now = now_ms();
    if (!peer.has_cert && !peer.public_store) {
        r = {false, ESP_ERR_MBEDTLS_SSL_SETUP_FAILED, 0, 0, "failed:no_verification"};
    } else if (std::any_of(fail_windows.begin(), fail_windows.end(), [now](const Window &w) { return now >= w.from_ms && now < w.to_ms; })) {
        r = {false, ESP_ERR_MBEDTLS_SSL_HANDSHAKE_FAILED, kConnEof, 0, "failed:handshake"};
    } else if (!peer.public_store && (peer.binary || !well_formed(peer.pem))) {
        r = {false, ESP_ERR_MBEDTLS_X509_CRT_PARSE_FAILED, kPemNoHeader, 0, "failed:parse"};
    } else {
        bool trusted = peer.public_store ? public_ca : server_cert.empty() || squash(peer.pem) == squash(server_cert);
        const std::string &expected = peer.common_name.empty() ? host : peer.common_name;
        const std::string &presented = server_cn.empty() ? host : server_cn;
        int flags = (server_valid ? 0 : kBadExpired) | (peer.skip_cn || expected == presented ? 0 : kBadCnMismatch) | (trusted ? 0 : kBadNotTrusted);
        if (flags) {
            r = {false, ESP_ERR_MBEDTLS_SSL_HANDSHAKE_FAILED, kVerifyFailed, flags,
                 flags & kBadNotTrusted ? "failed:not_trusted" : flags & kBadExpired ? "failed:expired" : "failed:cn_mismatch"};
        }
    }
    Event(now, "tls_handshake").str("host", utf8(host)).flag("ok", r.ok).str("verify", r.verify);
    return r;
}

}  // namespace sim
