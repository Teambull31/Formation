#!/usr/bin/env bash
# Solution de référence du TP es4.
set -euo pipefail
cat > main.cpp <<'EOF'
#include "freertos/FreeRTOS.h"
#include "freertos/task.h"
#include "esp_adc/adc_oneshot.h"
#include "esp_log.h"

static const char *TAG = "niveau";

static const adc_channel_t CANAL = ADC_CHANNEL_6;  // GPIO 34, sur l'ADC1
static const int ECHANTILLONS = 8;                 // nombre de mesures moyennées
static const int ATTENTE_MS = 10;                  // pause entre deux mesures
static const int PERIODE_MS = 1000;                // un journal par seconde

static adc_oneshot_unit_handle_t adc;              // l'ADC1, créé dans app_main

// Lit ECHANTILLONS mesures brutes et renvoie leur moyenne, ou -1 si aucune lecture n'a réussi.
static int lire_moyenne(void) {
    int somme = 0;
    int lues = 0;
    for (int i = 0; i < ECHANTILLONS; i++) {
        int raw = 0;
        esp_err_t err = adc_oneshot_read(adc, CANAL, &raw);
        if (err == ESP_OK) {
            somme += raw;
            lues++;
        } else {
            ESP_LOGW(TAG, "lecture refusée : %s", esp_err_to_name(err));
        }
        vTaskDelay(pdMS_TO_TICKS(ATTENTE_MS));
    }
    return lues > 0 ? somme / lues : -1;
}

// Étalonnage du TP : 500 mV = 0 %, 3000 mV = 100 %, sur une plage de 0 à 3300 mV.
static int raw_vers_pourcent(int raw) {
    float mv = raw * 3300.0f / 4095.0f;            // brut -> millivolts
    float pct = (mv - 500.0f) * 100.0f / 2500.0f;  // millivolts -> pourcentage
    if (pct < 0.0f) pct = 0.0f;
    if (pct > 100.0f) pct = 100.0f;
    return (int)(pct + 0.5f);                      // arrondi au plus proche
}

extern "C" void app_main(void) {
    adc_oneshot_unit_init_cfg_t unit_cfg = {};
    unit_cfg.unit_id = ADC_UNIT_1;
    ESP_ERROR_CHECK(adc_oneshot_new_unit(&unit_cfg, &adc));

    adc_oneshot_chan_cfg_t chan_cfg = {};
    chan_cfg.atten = ADC_ATTEN_DB_12;
    chan_cfg.bitwidth = ADC_BITWIDTH_12;
    ESP_ERROR_CHECK(adc_oneshot_config_channel(adc, CANAL, &chan_cfg));

    for (;;) {
        int raw = lire_moyenne();
        if (raw < 0) {
            ESP_LOGE(TAG, "aucune mesure valide");
        } else {
            int pct = raw_vers_pourcent(raw);
            ESP_LOGI(TAG, "level=%d%%", pct);
        }
        // Les mesures ont déjà pris ECHANTILLONS * ATTENTE_MS : on complète pour tomber sur 1000 ms.
        vTaskDelay(pdMS_TO_TICKS(PERIODE_MS - ECHANTILLONS * ATTENTE_MS));
    }
}
EOF
