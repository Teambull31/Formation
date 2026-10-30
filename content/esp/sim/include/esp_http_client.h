/* Fake ESP-IDF v5.x: esp_http_client.h (subset): the configuration structure that esp_https_ota takes, the
 * handle type and the error codes. No esp_http_client_init/open/perform. esp_http_client_config_t keeps the
 * real names and order of the fields listed, but not the others (client certificate and key, user_agent,
 * method, event_handler, tls_version, ...); cert_pem shares its storage with cert_der in the real union. */
#pragma once

#include <stdbool.h>
#include <stddef.h>

#include "esp_err.h"

#ifdef __cplusplus
extern "C" {
#endif

#define ESP_ERR_HTTP_BASE (0x7000)
#define ESP_ERR_HTTP_MAX_REDIRECT (ESP_ERR_HTTP_BASE + 1)
#define ESP_ERR_HTTP_CONNECT (ESP_ERR_HTTP_BASE + 2)
#define ESP_ERR_HTTP_WRITE_DATA (ESP_ERR_HTTP_BASE + 3)
#define ESP_ERR_HTTP_FETCH_HEADER (ESP_ERR_HTTP_BASE + 4)
#define ESP_ERR_HTTP_INVALID_TRANSPORT (ESP_ERR_HTTP_BASE + 5)
#define ESP_ERR_HTTP_CONNECTING (ESP_ERR_HTTP_BASE + 6)
#define ESP_ERR_HTTP_EAGAIN (ESP_ERR_HTTP_BASE + 7)
#define ESP_ERR_HTTP_CONNECTION_CLOSED (ESP_ERR_HTTP_BASE + 8)
#define ESP_ERR_HTTP_NOT_MODIFIED (ESP_ERR_HTTP_BASE + 9)
#define ESP_ERR_HTTP_RANGE_NOT_SATISFIABLE (ESP_ERR_HTTP_BASE + 10)
#define ESP_ERR_HTTP_READ_TIMEOUT (ESP_ERR_HTTP_BASE + 11)
#define ESP_ERR_HTTP_INCOMPLETE_DATA (ESP_ERR_HTTP_BASE + 12)

typedef struct esp_http_client *esp_http_client_handle_t;

typedef enum {
    HTTP_TRANSPORT_UNKNOWN = 0x0,
    HTTP_TRANSPORT_OVER_TCP,
    HTTP_TRANSPORT_OVER_SSL,
} esp_http_client_transport_t;

typedef enum {
    HTTP_AUTH_TYPE_NONE = 0,
    HTTP_AUTH_TYPE_BASIC,
    HTTP_AUTH_TYPE_DIGEST,
} esp_http_client_auth_type_t;

typedef struct {
    const char *url;
    const char *host;
    int port;
    const char *username;
    const char *password;
    esp_http_client_auth_type_t auth_type;
    const char *path;
    const char *query;
    const char *cert_pem;
    size_t cert_len;
    int timeout_ms;
    bool disable_auto_redirect;
    int max_redirection_count;
    int max_authorization_retries;
    esp_http_client_transport_t transport_type;
    int buffer_size;
    int buffer_size_tx;
    void *user_data;
    bool is_async;
    bool use_global_ca_store;
    bool skip_cert_common_name_check;
    const char *common_name;
    esp_err_t (*crt_bundle_attach)(void *conf);
    bool keep_alive_enable;
} esp_http_client_config_t;

#ifdef __cplusplus
}
#endif
