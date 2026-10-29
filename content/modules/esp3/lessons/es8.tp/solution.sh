#!/usr/bin/env bash
# Solution de référence du TP es8.
set -euo pipefail
cat > main.cpp <<'EOF'
#include <atomic>
#include <stdio.h>
#include <string.h>
#include "freertos/FreeRTOS.h"
#include "freertos/task.h"
#include "freertos/event_groups.h"
#include "driver/gpio.h"
#include "esp_adc/adc_oneshot.h"
#include "esp_log.h"
#include "esp_event.h"
#include "esp_netif.h"
#include "esp_wifi.h"
#include "nvs_flash.h"
#include "mqtt_client.h"
#include "sdkconfig.h"

static const char *TAG = "mqtt";

static const char *URI_COURTIER = "mqtt://192.168.1.10:1883";  // le courtier de la maison (simulé)
static const char *TOPIC_TELEMETRIE = "home/devices/pool-ctl/telemetry";
static const char *TOPIC_STATUT = "home/devices/pool-ctl/status";
static const char *TOPIC_COMMANDE = "home/devices/pool-ctl/command";
static const int PERIODE_MS = 10000;    // une télémétrie toutes les 10 s
static const double LIMITE_PCT = 80.0;  // limite de sécurité du TP 6 : jamais de remplissage au-dessus

static const gpio_num_t RELAIS_GPIO = GPIO_NUM_5;  // relais de la pompe, actif haut (TP 6)
static const adc_channel_t CANAL = ADC_CHANNEL_6;  // capteur de niveau : ADC1, canal 6 (TP 4 et TP 6)
static const int RAW_0_PCT = 620;                  // valeur brute pour 0 %
static const int RAW_100_PCT = 3723;               // valeur brute pour 100 %

static const EventBits_t BIT_IP = 1 << 0;  // drapeau : l'adresse IP est obtenue

static EventGroupHandle_t groupe_wifi;
static adc_oneshot_unit_handle_t adc;
static esp_mqtt_client_handle_t client;
static std::atomic<bool> relais{false};  // état du relais : lu par app_main, écrit par la tâche mqtt_task

// ---- Fourni : le Wi-Fi, version minimale du TP 7 (sans attente croissante : la box de ce TP répond toujours) ----

static void gestionnaire_wifi(void *arg, esp_event_base_t base, int32_t id, void *data) {
    if (base == WIFI_EVENT && (id == WIFI_EVENT_STA_START || id == WIFI_EVENT_STA_DISCONNECTED)) {
        esp_wifi_connect();
    } else if (base == IP_EVENT && id == IP_EVENT_STA_GOT_IP) {
        xEventGroupSetBits(groupe_wifi, BIT_IP);
    }
}

// Bloque jusqu'à l'obtention d'une adresse IP : MQTT a besoin du réseau.
static void wifi_connecter(void) {
    esp_err_t ret = nvs_flash_init();
    if (ret == ESP_ERR_NVS_NO_FREE_PAGES || ret == ESP_ERR_NVS_NEW_VERSION_FOUND) {
        ESP_ERROR_CHECK(nvs_flash_erase());
        ret = nvs_flash_init();
    }
    ESP_ERROR_CHECK(ret);
    groupe_wifi = xEventGroupCreate();
    ESP_ERROR_CHECK(esp_netif_init());
    ESP_ERROR_CHECK(esp_event_loop_create_default());
    esp_netif_create_default_wifi_sta();
    wifi_init_config_t cfg = WIFI_INIT_CONFIG_DEFAULT();
    ESP_ERROR_CHECK(esp_wifi_init(&cfg));
    esp_event_handler_instance_t inst_wifi, inst_ip;
    ESP_ERROR_CHECK(esp_event_handler_instance_register(WIFI_EVENT, ESP_EVENT_ANY_ID, &gestionnaire_wifi, NULL, &inst_wifi));
    ESP_ERROR_CHECK(esp_event_handler_instance_register(IP_EVENT, IP_EVENT_STA_GOT_IP, &gestionnaire_wifi, NULL, &inst_ip));
    wifi_config_t conf = {};
    strncpy((char *)conf.sta.ssid, CONFIG_ESP_WIFI_SSID, sizeof(conf.sta.ssid) - 1);
    strncpy((char *)conf.sta.password, CONFIG_ESP_WIFI_PASSWORD, sizeof(conf.sta.password) - 1);
    ESP_ERROR_CHECK(esp_wifi_set_mode(WIFI_MODE_STA));
    ESP_ERROR_CHECK(esp_wifi_set_config(WIFI_IF_STA, &conf));
    ESP_ERROR_CHECK(esp_wifi_start());
    xEventGroupWaitBits(groupe_wifi, BIT_IP, pdFALSE, pdFALSE, portMAX_DELAY);
}

// ---- Fourni : le relais et le capteur, repris des TP 4 et 6 ----

// Relais de la pompe : sortie, éteint au démarrage (état sûr).
static void init_relais(void) {
    gpio_config_t cfg = {};
    cfg.pin_bit_mask = 1ULL << RELAIS_GPIO;
    cfg.mode = GPIO_MODE_OUTPUT;
    ESP_ERROR_CHECK(gpio_config(&cfg));
    ESP_ERROR_CHECK(gpio_set_level(RELAIS_GPIO, 0));
}

// Allume (true) ou éteint (false) le relais et retient son état.
static void regler_relais(bool allume) {
    ESP_ERROR_CHECK(gpio_set_level(RELAIS_GPIO, allume ? 1 : 0));
    relais = allume;
}

static void init_adc(void) {
    adc_oneshot_unit_init_cfg_t unit_cfg = {};
    unit_cfg.unit_id = ADC_UNIT_1;
    ESP_ERROR_CHECK(adc_oneshot_new_unit(&unit_cfg, &adc));
    adc_oneshot_chan_cfg_t chan_cfg = {};
    chan_cfg.atten = ADC_ATTEN_DB_12;
    chan_cfg.bitwidth = ADC_BITWIDTH_12;
    ESP_ERROR_CHECK(adc_oneshot_config_channel(adc, CANAL, &chan_cfg));
}

// Niveau de l'eau en pourcentage (0.0 à 100.0), étalonnage du TP 4. Si la lecture échoue : 100.0, le pire cas
// (état sûr : sans mesure, on ne remplit pas).
static double lire_niveau(void) {
    int raw = 0;
    if (adc_oneshot_read(adc, CANAL, &raw) != ESP_OK) {
        ESP_LOGE(TAG, "lecture du capteur impossible");
        return 100.0;
    }
    double pct = (raw - RAW_0_PCT) * 100.0 / (RAW_100_PCT - RAW_0_PCT);
    return pct < 0.0 ? 0.0 : pct > 100.0 ? 100.0 : pct;
}

// ---- À écrire ----


// Écrit dans buf le JSON {"level": 72.5, "relay": false} ; renvoie ce que renvoie snprintf.
static int construire_json(char *buf, size_t taille, double niveau, bool relais_actif) {
    return snprintf(buf, taille, "{\"level\": %.1f, \"relay\": %s}", niveau, relais_actif ? "true" : "false");
}

// Lit le niveau, construit le JSON, le publie sur le topic de télémétrie (QoS 0, non retenu).
static void publier_telemetrie(void) {
    char json[64];
    construire_json(json, sizeof(json), lire_niveau(), relais);
    int id = esp_mqtt_client_publish(client, TOPIC_TELEMETRIE, json, 0, 0, 0);
    if (id < 0) {
        ESP_LOGI(TAG, "télémétrie non envoyée : client déconnecté");
    }
}

// Exécute (ou refuse) la commande reçue : data n'est PAS terminée par un NUL, seule len dit sa taille.
static void traiter_commande(const char *data, int len) {
    char msg[64];
    int n = len < (int)sizeof(msg) - 1 ? len : (int)sizeof(msg) - 1;
    memcpy(msg, data, n);
    msg[n] = '\0';
    const char *p = strstr(msg, "\"relay\"");
    if (p == NULL) {
        return;  // pas une commande : on ignore
    }
    p += strlen("\"relay\"");
    while (*p == ' ' || *p == ':') {
        p++;
    }
    bool voulu;
    if (strncmp(p, "true", 4) == 0) {
        voulu = true;
    } else if (strncmp(p, "false", 5) == 0) {
        voulu = false;
    } else {
        return;  // la valeur n'est ni true ni false : on ignore
    }
    if (voulu) {
        double niveau = lire_niveau();
        if (niveau > LIMITE_PCT) {
            ESP_LOGW(TAG, "command refused: level=%d%%", (int)niveau);
            return;
        }
    }
    regler_relais(voulu);
}

// Gestionnaire des événements MQTT (tâche mqtt_task).
static void gestionnaire_mqtt(void *arg, esp_event_base_t base, int32_t id, void *data) {
    esp_mqtt_event_handle_t ev = (esp_mqtt_event_handle_t)data;
    switch ((esp_mqtt_event_id_t)id) {
    case MQTT_EVENT_CONNECTED:
        esp_mqtt_client_publish(ev->client, TOPIC_STATUT, "online", 0, 1, 1);
        esp_mqtt_client_subscribe_single(ev->client, TOPIC_COMMANDE, 1);
        break;
    case MQTT_EVENT_DATA:
        if (ev->topic_len == (int)strlen(TOPIC_COMMANDE) && strncmp(ev->topic, TOPIC_COMMANDE, ev->topic_len) == 0) {
            traiter_commande(ev->data, ev->data_len);
        }
        break;
    default:
        break;
    }
}

// Configure le client (courtier, testament), l'enregistre et le démarre.
static void demarrer_mqtt(void) {
    esp_mqtt_client_config_t cfg = {};
    cfg.broker.address.uri = URI_COURTIER;
    cfg.credentials.client_id = "pool-ctl";
    cfg.session.last_will.topic = TOPIC_STATUT;
    cfg.session.last_will.msg = "offline";
    cfg.session.last_will.qos = 1;
    cfg.session.last_will.retain = true;
    client = esp_mqtt_client_init(&cfg);
    ESP_ERROR_CHECK(esp_mqtt_client_register_event(client, (esp_mqtt_event_id_t)ESP_EVENT_ANY_ID, gestionnaire_mqtt, NULL));
    ESP_ERROR_CHECK(esp_mqtt_client_start(client));
}

extern "C" void app_main(void) {
    init_relais();
    init_adc();
    wifi_connecter();
    demarrer_mqtt();
    for (;;) {
        publier_telemetrie();
        vTaskDelay(pdMS_TO_TICKS(PERIODE_MS));
    }
}
EOF
