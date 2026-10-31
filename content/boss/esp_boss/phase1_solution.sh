#!/usr/bin/env bash
# Solution de référence du boss ESP, phase 1 : la régulation et la sécurité de la pompe avec un capteur qui ment (leçon es6).
# Elle écrit espboss/main.cpp en entier (les phases sont cumulatives : la phase 1 reprend tout ce qui précède).
set -euo pipefail
mkdir -p espboss
cat > espboss/main.cpp <<'EOF'
#include "freertos/FreeRTOS.h"
#include "freertos/task.h"
#include "driver/gpio.h"
#include "esp_adc/adc_oneshot.h"
#include "esp_timer.h"
#include "esp_log.h"

static const char *TAG = "pool";

static const gpio_num_t POMPE_GPIO = GPIO_NUM_5;   // relais de la pompe, actif haut : niveau 1 = pompe en marche
static const adc_channel_t CANAL = ADC_CHANNEL_6;  // capteur de niveau : ADC1, canal 6 (GPIO 34), comme au TP 4
static const int RAW_0_PCT = 620;                  // valeur brute pour 0 %
static const int RAW_100_PCT = 3723;               // valeur brute pour 100 %
static const int RAW_MIN_OK = 300;                 // en dessous : fil coupé ou court-circuit vers la masse (lecture proche de 0)
static const int RAW_MAX_OK = 3900;                // au-dessus : capteur saturé ou court-circuit vers l'alimentation (proche de 4095)
static const int SEUIL_BAS = 60;                   // on démarre la pompe sous 60 %
static const int SEUIL_HAUT = 80;                  // on l'arrête au-dessus de 80 %
static const int PAS_MS = 1000;                    // un tour de la boucle principale par seconde
static const int64_t DELAI_MAX_MS = 10 * 60 * 1000;  // 10 minutes de pompe sans hausse du niveau : alarme
static const int HAUSSE_MIN = 1;                   // « le niveau monte » = au moins 1 point de plus
static const int64_t FIGE_MS = 10 * 60 * 1000;     // 10 minutes de valeur brute identique : capteur figé

enum class Etat { IDLE, FILLING, ALARM };          // pompe arrêtée, pompe en marche, alarme verrouillée

static adc_oneshot_unit_handle_t adc;              // l'ADC1, créé dans app_main
static Etat etat = Etat::IDLE;                     // l'état de la régulation
static int64_t debut_ms = 0;                       // instant de référence du délai maximal
static int niveau_debut = 0;                       // niveau à cet instant
static int dernier_brut = -1;                      // dernière valeur brute lue
static int64_t brut_change_ms = 0;                 // instant où la valeur brute a changé pour la dernière fois

// Temps écoulé depuis le démarrage, en millisecondes.
static int64_t maintenant_ms(void) {
    return esp_timer_get_time() / 1000;
}

// Lit le capteur : la valeur brute (0 à 4095), ou -1 si la lecture a échoué.
static int lire_brut(void) {
    int raw = 0;
    if (adc_oneshot_read(adc, CANAL, &raw) != ESP_OK) {
        return -1;
    }
    return raw;
}

// Étalonnage du TP 4 : 620 = 0 %, 3723 = 100 %, calcul en entiers, borné entre 0 et 100.
static int brut_vers_pourcent(int raw) {
    int pct = (raw - RAW_0_PCT) * 100 / (RAW_100_PCT - RAW_0_PCT);
    if (pct < 0) {
        pct = 0;
    }
    if (pct > 100) {
        pct = 100;
    }
    return pct;
}

// Relais d'abord : sortie, pompe éteinte (état sûr). À appeler tout au début d'app_main.
static void init_pompe(void) {
    gpio_config_t cfg = {};
    cfg.pin_bit_mask = 1ULL << POMPE_GPIO;
    cfg.mode = GPIO_MODE_OUTPUT;
    ESP_ERROR_CHECK(gpio_config(&cfg));
    ESP_ERROR_CHECK(gpio_set_level(POMPE_GPIO, 0));
}

// Allume (true) ou éteint (false) la pompe : relais actif haut.
static void pompe(bool allumee) {
    ESP_ERROR_CHECK(gpio_set_level(POMPE_GPIO, allumee ? 1 : 0));
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

// Passe en alarme : pompe coupée d'abord, puis état verrouillé, puis UNE ligne d'erreur.
static void alarme(const char *raison) {
    pompe(false);
    etat = Etat::ALARM;
    ESP_LOGE(TAG, "ALARME : %s, pompe coupée jusqu'au redémarrage", raison);
}

// Un tour de régulation : lire, décider, agir.
static void reguler(void) {
    int64_t t = maintenant_ms();
    int brut = lire_brut();
    if (etat == Etat::ALARM) {
        pompe(false);  // verrouillé : rien d'autre à faire jusqu'au redémarrage
        return;
    }
    if (brut < 0) {
        alarme("lecture du capteur impossible");  // sans mesure, on ne régule pas à l'aveugle
        return;
    }
    if (brut < RAW_MIN_OK || brut > RAW_MAX_OK) {
        alarme("valeur brute invraisemblable (capteur coupé ou en court-circuit)");  // un fil coupé lit 0, soit « 0 % » : la pompe remplirait sans fin
        return;
    }
    int niveau = brut_vers_pourcent(brut);
    if (brut != dernier_brut) {
        dernier_brut = brut;
        brut_change_ms = t;
    }
    if (t - brut_change_ms >= FIGE_MS) {
        alarme("capteur figé (valeur brute identique depuis 10 min)");
    } else if (etat == Etat::IDLE) {
        if (niveau < SEUIL_BAS) {
            debut_ms = t;
            niveau_debut = niveau;
            etat = Etat::FILLING;
            pompe(true);
            ESP_LOGI(TAG, "pompe allumée à %d %%", niveau);
        }
    } else if (niveau > SEUIL_HAUT) {  // FILLING : niveau atteint
        pompe(false);
        etat = Etat::IDLE;
        ESP_LOGI(TAG, "pompe éteinte à %d %%", niveau);
    } else if (niveau >= niveau_debut + HAUSSE_MIN) {  // FILLING : le niveau monte, on repart de zéro
        debut_ms = t;
        niveau_debut = niveau;
    } else if (t - debut_ms >= DELAI_MAX_MS) {         // FILLING : 10 min sans hausse
        alarme("pompe en marche depuis 10 min sans hausse du niveau");
    }
}

extern "C" void app_main(void) {
    init_pompe();  // tout premier geste : pompe éteinte avant toute lecture
    init_adc();
    for (;;) {
        reguler();
        vTaskDelay(pdMS_TO_TICKS(PAS_MS));
    }
}
EOF
