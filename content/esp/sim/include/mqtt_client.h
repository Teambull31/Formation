/* Fake ESP-IDF v5.x: mqtt_client.h (esp-mqtt, subset). Reduced: broker.verification is complete except for the
 * PSK and the cipher-suite list in use, but there are no client certificate/key credentials, no MQTT 5
 * properties, no esp_mqtt_client_subscribe_multiple/enqueue. */
#pragma once

#include <stdbool.h>
#include <stddef.h>
#include <stdint.h>

#include "esp_err.h"
#include "esp_event_base.h"

#ifdef __cplusplus
extern "C" {
#endif

ESP_EVENT_DECLARE_BASE(MQTT_EVENTS);

typedef struct esp_mqtt_client *esp_mqtt_client_handle_t;

typedef enum {
    MQTT_EVENT_ANY = -1,
    MQTT_EVENT_ERROR = 0,
    MQTT_EVENT_CONNECTED,
    MQTT_EVENT_DISCONNECTED,
    MQTT_EVENT_SUBSCRIBED,
    MQTT_EVENT_UNSUBSCRIBED,
    MQTT_EVENT_PUBLISHED,
    MQTT_EVENT_DATA,
    MQTT_EVENT_BEFORE_CONNECT,
    MQTT_EVENT_DELETED,
    MQTT_USER_EVENT,
} esp_mqtt_event_id_t;

typedef enum {
    MQTT_TRANSPORT_UNKNOWN = 0x0,
    MQTT_TRANSPORT_OVER_TCP,
    MQTT_TRANSPORT_OVER_SSL,
    MQTT_TRANSPORT_OVER_WS,
    MQTT_TRANSPORT_OVER_WSS
} esp_mqtt_transport_t;

typedef enum {
    MQTT_PROTOCOL_UNDEFINED = 0,
    MQTT_PROTOCOL_V_3_1,
    MQTT_PROTOCOL_V_3_1_1,
    MQTT_PROTOCOL_V_5,
} esp_mqtt_protocol_ver_t;

typedef enum {
    MQTT_ERROR_TYPE_NONE = 0,
    MQTT_ERROR_TYPE_TCP_TRANSPORT,
    MQTT_ERROR_TYPE_CONNECTION_REFUSED,
    MQTT_ERROR_TYPE_SUBSCRIBE_FAILED
} esp_mqtt_error_type_t;

#define MQTT_ERROR_TYPE_ESP_TLS MQTT_ERROR_TYPE_TCP_TRANSPORT

typedef enum {
    MQTT_CONNECTION_ACCEPTED = 0,
    MQTT_CONNECTION_REFUSE_PROTOCOL,
    MQTT_CONNECTION_REFUSE_ID_REJECTED,
    MQTT_CONNECTION_REFUSE_SERVER_UNAVAILABLE,
    MQTT_CONNECTION_REFUSE_BAD_USERNAME,
    MQTT_CONNECTION_REFUSE_NOT_AUTHORIZED
} esp_mqtt_connect_return_code_t;

typedef struct esp_mqtt_error_codes {
    esp_err_t esp_tls_last_esp_err;
    int esp_tls_stack_err;
    int esp_tls_cert_verify_flags;
    esp_mqtt_error_type_t error_type;
    esp_mqtt_connect_return_code_t connect_return_code;
    int esp_transport_sock_errno;
} esp_mqtt_error_codes_t;

typedef struct esp_mqtt_event_t {
    esp_mqtt_event_id_t event_id;
    esp_mqtt_client_handle_t client;
    char *data;
    int data_len;
    int total_data_len;
    int current_data_offset;
    char *topic;
    int topic_len;
    int msg_id;
    int session_present;
    esp_mqtt_error_codes_t *error_handle;
    bool retain;
    int qos;
    bool dup;
    esp_mqtt_protocol_ver_t protocol_ver;
} esp_mqtt_event_t;

typedef esp_mqtt_event_t *esp_mqtt_event_handle_t;

typedef struct esp_mqtt_client_config_t {
    struct broker_t {
        struct address_t {
            const char *uri;
            const char *hostname;
            esp_mqtt_transport_t transport;
            const char *path;
            uint32_t port;
        } address;
        struct verification_t {
            bool use_global_ca_store;
            esp_err_t (*crt_bundle_attach)(void *conf);
            const char *certificate;
            size_t certificate_len;
            const struct psk_key_hint *psk_hint_key;
            bool skip_cert_common_name_check;
            const char **alpn_protos;
            const char *common_name;
            const int *ciphersuites_list;
        } verification;
    } broker;
    struct credentials_t {
        const char *username;
        const char *client_id;
        bool set_null_client_id;
        struct authentication_t {
            const char *password;
        } authentication;
    } credentials;
    struct session_t {
        struct last_will_t {
            const char *topic;
            const char *msg;
            int msg_len;
            int qos;
            bool retain;
        } last_will;
        bool disable_clean_session;
        int keepalive;
        bool disable_keepalive;
        esp_mqtt_protocol_ver_t protocol_ver;
        int message_retransmit_timeout;
    } session;
    struct network_t {
        int reconnect_timeout_ms;
        int timeout_ms;
        int refresh_connection_after_ms;
        bool disable_auto_reconnect;
    } network;
    struct task_t {
        int priority;
        int stack_size;
    } task;
    struct buffer_t {
        int size;
        int out_size;
    } buffer;
} esp_mqtt_client_config_t;

esp_mqtt_client_handle_t esp_mqtt_client_init(const esp_mqtt_client_config_t *config);
esp_err_t esp_mqtt_client_start(esp_mqtt_client_handle_t client);
esp_err_t esp_mqtt_client_stop(esp_mqtt_client_handle_t client);
esp_err_t esp_mqtt_client_destroy(esp_mqtt_client_handle_t client);
esp_err_t esp_mqtt_client_register_event(esp_mqtt_client_handle_t client, esp_mqtt_event_id_t event, esp_event_handler_t event_handler, void *event_handler_arg);
int esp_mqtt_client_subscribe_single(esp_mqtt_client_handle_t client, const char *topic, int qos);
int esp_mqtt_client_unsubscribe(esp_mqtt_client_handle_t client, const char *topic);
int esp_mqtt_client_publish(esp_mqtt_client_handle_t client, const char *topic, const char *data, int len, int qos, int retain);

#define esp_mqtt_client_subscribe(client, topic_type, qos_or_size) esp_mqtt_client_subscribe_single(client, topic_type, qos_or_size)

#ifdef __cplusplus
}
#endif
