// TP 6 : réguler le niveau d'une piscine avec une pompe commandée par un relais (GPIO 5, actif haut : niveau 1 = pompe en marche).
// Le capteur de niveau est sur l'ADC1, canal 6 (GPIO 34), avec l'étalonnage du TP 4 : valeur brute 620 = 0 %, 3723 = 100 %.
// Le contrôle compile ce fichier et simule, en temps virtuel, plusieurs situations : un cycle normal de 2 heures, un capteur
// bloqué, un capteur figé, une pompe qui ne remplit plus. Suivez les étapes TODO dans l'ordre.
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
static const int SEUIL_BAS = 60;                   // on démarre la pompe sous 60 %
static const int SEUIL_HAUT = 80;                  // on l'arrête au-dessus de 80 %
static const int PERIODE_MS = 5000;                // une mesure toutes les 5 s
static const int64_t DELAI_MAX_MS = 10 * 60 * 1000;  // 10 minutes de pompe sans hausse du niveau : alarme
static const int HAUSSE_MIN = 1;                   // « le niveau monte » = au moins 1 point de plus
static const int64_t FIGE_MS = 10 * 60 * 1000;     // 10 minutes de valeur brute identique : capteur figé

enum class Etat { IDLE, FILLING, ALARM };          // pompe arrêtée, pompe en marche, alarme verrouillée

static adc_oneshot_unit_handle_t adc;              // l'ADC1, créé dans app_main
static Etat etat = Etat::IDLE;                     // l'état de la régulation (c'est aussi l'état de la pompe)

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

// Étalonnage du TP 4, repris ici : 620 = 0 %, 3723 = 100 %, calcul en entiers, borné entre 0 et 100.
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

// Allume (true) ou éteint (false) la pompe : relais actif haut.
static void pompe(bool allumee) {
    ESP_ERROR_CHECK(gpio_set_level(POMPE_GPIO, allumee ? 1 : 0));
}

// Passe en alarme : pompe coupée d'abord, puis état verrouillé, puis UNE ligne d'erreur.
static void alarme(const char *raison) {
    // TODO étape 1 : couper la pompe avec pompe(false), passer etat à Etat::ALARM, puis écrire UN
    // ESP_LOGE(TAG, "ALARME : %s, pompe coupée jusqu'au redémarrage", raison).
    (void)raison;
}

extern "C" void app_main(void) {
    // L'ADC est déjà configuré, comme au TP 4 (unité ADC1, canal 6, atténuation 12 dB, 12 bits).
    adc_oneshot_unit_init_cfg_t unit_cfg = {};
    unit_cfg.unit_id = ADC_UNIT_1;
    ESP_ERROR_CHECK(adc_oneshot_new_unit(&unit_cfg, &adc));
    adc_oneshot_chan_cfg_t chan_cfg = {};
    chan_cfg.atten = ADC_ATTEN_DB_12;
    chan_cfg.bitwidth = ADC_BITWIDTH_12;
    ESP_ERROR_CHECK(adc_oneshot_config_channel(adc, CANAL, &chan_cfg));

    // TODO étape 2 : configurer la GPIO 5 en sortie (gpio_config avec mode = GPIO_MODE_OUTPUT) dans ESP_ERROR_CHECK,
    // puis mettre la pompe à l'état sûr avec pompe(false), AVANT la première lecture.

    int64_t debut_ms = 0;        // instant de référence du délai maximal
    int niveau_debut = 0;        // niveau à cet instant
    int dernier_brut = -1;       // dernière valeur brute lue
    int64_t brut_change_ms = 0;  // instant où la valeur brute a changé pour la dernière fois
    (void)debut_ms;
    (void)niveau_debut;
    (void)dernier_brut;
    (void)brut_change_ms;
    for (;;) {
        int64_t t = maintenant_ms();
        int brut = lire_brut();
        if (etat == Etat::ALARM) {
            pompe(false);  // verrouillé : rien d'autre à faire jusqu'au redémarrage
        } else if (brut < 0) {
            alarme("lecture du capteur impossible");  // sans mesure, on ne régule pas à l'aveugle
        } else {
            int niveau = brut_vers_pourcent(brut);
            (void)t;
            (void)niveau;
            // TODO étape 3 : détecter le capteur figé. Si brut != dernier_brut : dernier_brut = brut et
            // brut_change_ms = t. Si t - brut_change_ms >= FIGE_MS : alarme("capteur figé ...") et rien d'autre ce tour-ci.
            //
            // Sinon, selon l'état :
            // TODO étape 4 (etat == Etat::IDLE) : si niveau < SEUIL_BAS : debut_ms = t, niveau_debut = niveau,
            // etat = Etat::FILLING, pompe(true), et un ESP_LOGI.
            // TODO étape 5 (etat == Etat::FILLING) : si niveau > SEUIL_HAUT : pompe(false), etat = Etat::IDLE.
            // Sinon, si niveau >= niveau_debut + HAUSSE_MIN : le niveau monte, debut_ms = t et niveau_debut = niveau.
            // Sinon, si t - debut_ms >= DELAI_MAX_MS : alarme("pompe en marche depuis 10 min sans hausse du niveau").
        }
        vTaskDelay(pdMS_TO_TICKS(PERIODE_MS));
    }
}
