// TP 5 : lire une température sur le bus I2C, commander un relais et survivre à une panne du capteur.
// Le capteur est à l'adresse 0x44 et renvoie 2 octets. Le relais est sur la GPIO 5 (actif haut : niveau 1 = allumé).
// Le contrôle compile ce fichier et simule 80 secondes de montée en température, avec deux pannes du capteur.
#include "freertos/FreeRTOS.h"
#include "freertos/task.h"
#include "driver/gpio.h"
#include "driver/i2c_master.h"
#include "esp_log.h"

static const char *TAG = "ventilo";

static const gpio_num_t RELAIS_GPIO = GPIO_NUM_5;  // relais actif haut : niveau 1 = allumé
static const gpio_num_t SDA_GPIO = GPIO_NUM_21;
static const gpio_num_t SCL_GPIO = GPIO_NUM_22;
static const int ADRESSE_CAPTEUR = 0x44;           // adresse I2C sur 7 bits
static const int TIMEOUT_I2C_MS = 100;             // attente maximale d'un transfert
static const int PERIODE_MS = 5000;                // une mesure toutes les 5 s
static const int SEUIL_DIXIEMES = 280;             // 28,0 °C, en dixièmes de degré

static i2c_master_dev_handle_t capteur;            // le capteur, créé dans app_main

// Lit la température en dixièmes de °C : ESP_OK et *dixiemes rempli, sinon le code d'erreur (rien n'est écrit).
static esp_err_t lire_temperature(int *dixiemes) {
    // TODO étape 3 : lire 2 octets avec i2c_master_receive(capteur, octets, sizeof octets, TIMEOUT_I2C_MS).
    // Si le retour n'est pas ESP_OK, le renvoyer tel quel. Sinon : brut = (octets[0] << 8) | octets[1],
    // puis *dixiemes = brut - 400, et renvoyer ESP_OK.
    (void)dixiemes;
    return ESP_FAIL;
}

extern "C" void app_main(void) {
    // TODO étape 1 : configurer la GPIO 5 en sortie (gpio_config avec mode = GPIO_MODE_OUTPUT) et éteindre le relais
    // au départ (gpio_set_level(RELAIS_GPIO, 0)), le tout dans ESP_ERROR_CHECK : ce sont des erreurs de démarrage.

    // TODO étape 2 : créer le bus (i2c_master_bus_config_t : i2c_port = I2C_NUM_0, sda_io_num, scl_io_num,
    // clk_source = I2C_CLK_SRC_DEFAULT, glitch_ignore_cnt = 7, flags.enable_internal_pullup = 1) avec
    // i2c_new_master_bus, puis ajouter le capteur (i2c_device_config_t : dev_addr_length = I2C_ADDR_BIT_LEN_7,
    // device_address = ADRESSE_CAPTEUR, scl_speed_hz = 100000) avec i2c_master_bus_add_device(bus, &dev_cfg, &capteur).
    // Les deux appels vont dans ESP_ERROR_CHECK.

    bool relais_allume = false;  // dernier état décidé sur une mesure valide
    bool en_panne = false;       // vrai tant que la panne en cours a déjà été journalisée
    (void)relais_allume;
    (void)en_panne;
    for (;;) {
        // TODO étape 4 : appeler lire_temperature(&dixiemes) (avec int dixiemes = 0;) et mettre le retour dans un esp_err_t.
        //  - si ESP_OK : si en_panne, ESP_LOGI « capteur de nouveau disponible » et en_panne = false ; puis
        //    relais_allume = dixiemes > SEUIL_DIXIEMES ; gpio_set_level(RELAIS_GPIO, relais_allume ? 1 : 0) ; ESP_LOGI de la mesure.
        //  - sinon, si !en_panne : ESP_LOGE avec esp_err_to_name(err), puis en_panne = true. Ne touchez PAS au relais.
        //  Jamais d'ESP_ERROR_CHECK sur la lecture : une panne du capteur ne doit pas arrêter le programme.

        vTaskDelay(pdMS_TO_TICKS(PERIODE_MS));
    }
}
