#!/usr/bin/env bash
# Solution de référence du TP es7.
set -euo pipefail
cat > main.cpp <<'EOF'
#include <string.h>
#include "freertos/FreeRTOS.h"
#include "freertos/task.h"
#include "freertos/event_groups.h"
#include "esp_log.h"
#include "esp_event.h"
#include "esp_netif.h"
#include "esp_wifi.h"
#include "nvs_flash.h"
#include "sdkconfig.h"

static const char *TAG = "wifi";

static const int MAX_TENTATIVES = 10;     // 10 tentatives de connexion au total, la première comprise
static const int ATTENTE_INIT_MS = 1000;  // attente après le 1er échec ; elle double à chaque échec
static const int ATTENTE_MAX_MS = 8000;   // plafond de l'attente

static const EventBits_t BIT_CONNECTE = 1 << 0;  // drapeau : l'adresse IP est obtenue
static const EventBits_t BIT_PERDU = 1 << 1;     // drapeau : une tentative a échoué (ou le lien est perdu)

static EventGroupHandle_t groupe;  // les drapeaux ci-dessus ; créé dans demarrer_wifi
static int echecs = 0;             // nombre d'échecs de suite

// Attente avant la prochaine tentative après n échecs de suite (n >= 1) : 1 s, 2 s, 4 s, 8 s, puis 8 s.
static int attente_ms(int n) {
    int ms = ATTENTE_INIT_MS;
    for (int i = 1; i < n && ms < ATTENTE_MAX_MS; i++) {
        ms *= 2;
    }
    return ms > ATTENTE_MAX_MS ? ATTENTE_MAX_MS : ms;
}

// Motif canonique d'initialisation de la NVS.
static void init_nvs(void) {
    esp_err_t ret = nvs_flash_init();
    if (ret == ESP_ERR_NVS_NO_FREE_PAGES || ret == ESP_ERR_NVS_NEW_VERSION_FOUND) {
        ESP_ERROR_CHECK(nvs_flash_erase());
        ret = nvs_flash_init();
    }
    ESP_ERROR_CHECK(ret);
}

// Appelé dans la tâche sys_evt : il note ce qui se passe et ne bloque jamais.
static void gestionnaire(void *arg, esp_event_base_t base, int32_t id, void *data) {
    if (base == WIFI_EVENT && id == WIFI_EVENT_STA_START) {
        esp_wifi_connect();
    } else if (base == WIFI_EVENT && id == WIFI_EVENT_STA_DISCONNECTED) {
        xEventGroupSetBits(groupe, BIT_PERDU);
    } else if (base == IP_EVENT && id == IP_EVENT_STA_GOT_IP) {
        ip_event_got_ip_t *ev = (ip_event_got_ip_t *)data;
        ESP_LOGI(TAG, "adresse IP : " IPSTR, IP2STR(&ev->ip_info.ip));
        xEventGroupSetBits(groupe, BIT_CONNECTE);
    }
}

static void demarrer_wifi(void) {
    groupe = xEventGroupCreate();
    ESP_ERROR_CHECK(esp_netif_init());
    ESP_ERROR_CHECK(esp_event_loop_create_default());
    esp_netif_create_default_wifi_sta();
    wifi_init_config_t cfg = WIFI_INIT_CONFIG_DEFAULT();
    ESP_ERROR_CHECK(esp_wifi_init(&cfg));

    esp_event_handler_instance_t inst_wifi, inst_ip;
    ESP_ERROR_CHECK(esp_event_handler_instance_register(WIFI_EVENT, ESP_EVENT_ANY_ID, &gestionnaire, NULL, &inst_wifi));
    ESP_ERROR_CHECK(esp_event_handler_instance_register(IP_EVENT, IP_EVENT_STA_GOT_IP, &gestionnaire, NULL, &inst_ip));

    wifi_config_t conf = {};
    strncpy((char *)conf.sta.ssid, CONFIG_ESP_WIFI_SSID, sizeof(conf.sta.ssid) - 1);
    strncpy((char *)conf.sta.password, CONFIG_ESP_WIFI_PASSWORD, sizeof(conf.sta.password) - 1);
    ESP_ERROR_CHECK(esp_wifi_set_mode(WIFI_MODE_STA));
    ESP_ERROR_CHECK(esp_wifi_set_config(WIFI_IF_STA, &conf));
    ESP_ERROR_CHECK(esp_wifi_start());
}

extern "C" void app_main(void) {
    init_nvs();
    demarrer_wifi();
    while (true) {
        EventBits_t bits = xEventGroupWaitBits(groupe, BIT_CONNECTE | BIT_PERDU, pdTRUE, pdFALSE, portMAX_DELAY);
        if (bits & BIT_CONNECTE) {
            echecs = 0;
        } else if (bits & BIT_PERDU) {
            echecs++;
            if (echecs >= MAX_TENTATIVES) {
                ESP_LOGE(TAG, "abandon : %d tentatives sans succès", MAX_TENTATIVES);
                return;
            }
            int ms = attente_ms(echecs);
            ESP_LOGW(TAG, "échec %d, nouvelle tentative dans %d ms", echecs, ms);
            vTaskDelay(pdMS_TO_TICKS(ms));
            esp_wifi_connect();
        }
    }
}
EOF
