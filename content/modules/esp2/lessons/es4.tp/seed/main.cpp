// TP 4 : lire un capteur analogique avec l'ADC et journaliser son niveau en pourcentage.
// Le capteur est branché sur l'ADC1, canal 6 (GPIO 34). Suivez les étapes TODO dans l'ordre.
// Le contrôle compile ce fichier et simule 20 secondes pendant lesquelles la tension du capteur
// monte lentement, avec du bruit.
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
    // TODO étape 3 : dans une boucle de ECHANTILLONS tours, appeler adc_oneshot_read(adc, CANAL, &raw),
    // additionner raw si le retour vaut ESP_OK (sinon ESP_LOGW), puis attendre ATTENTE_MS avec vTaskDelay.
    // Renvoyer la somme divisée par le nombre de lectures réussies, ou -1 s'il n'y en a aucune.
    return -1;
}

// Étalonnage du TP : 500 mV = 0 %, 3000 mV = 100 %, sur une plage de 0 à 3300 mV.
static int raw_vers_pourcent(int raw) {
    // TODO étape 4 : brut -> millivolts (raw * 3300 / 4095), millivolts -> pourcentage
    // ((mv - 500) * 100 / 2500), borné entre 0 et 100, arrondi à l'entier le plus proche.
    return 0;
}

extern "C" void app_main(void) {
    // TODO étape 1 : créer l'unité ADC1 : un adc_oneshot_unit_init_cfg_t (unit_id = ADC_UNIT_1), puis
    // adc_oneshot_new_unit(&unit_cfg, &adc), dans ESP_ERROR_CHECK.

    // TODO étape 2 : configurer le canal : un adc_oneshot_chan_cfg_t (atten = ADC_ATTEN_DB_12,
    // bitwidth = ADC_BITWIDTH_12), puis adc_oneshot_config_channel(adc, CANAL, &chan_cfg), dans ESP_ERROR_CHECK.

    for (;;) {
        // TODO étape 5 : appeler lire_moyenne(). Si elle renvoie -1, ESP_LOGE(TAG, ...). Sinon convertir avec
        // raw_vers_pourcent puis écrire ESP_LOGI(TAG, "level=%d%%", pct).

        // Les mesures prennent déjà ECHANTILLONS * ATTENTE_MS : on complète pour tomber sur 1000 ms par tour.
        vTaskDelay(pdMS_TO_TICKS(PERIODE_MS - ECHANTILLONS * ATTENTE_MS));
    }
}
