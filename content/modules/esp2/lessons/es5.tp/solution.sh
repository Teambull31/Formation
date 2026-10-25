#!/usr/bin/env bash
# Solution de référence du TP es5.
set -euo pipefail
cat > main.cpp <<'EOF'
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
    uint8_t octets[2] = {0, 0};
    esp_err_t err = i2c_master_receive(capteur, octets, sizeof octets, TIMEOUT_I2C_MS);
    if (err != ESP_OK) {
        return err;
    }
    int brut = (octets[0] << 8) | octets[1];       // octet de poids fort en premier
    *dixiemes = brut - 400;                        // le capteur ajoute 40,0 °C : 600 veut dire 20,0 °C
    return ESP_OK;
}

extern "C" void app_main(void) {
    gpio_config_t relais_cfg = {};
    relais_cfg.pin_bit_mask = 1ULL << RELAIS_GPIO;
    relais_cfg.mode = GPIO_MODE_OUTPUT;
    ESP_ERROR_CHECK(gpio_config(&relais_cfg));
    ESP_ERROR_CHECK(gpio_set_level(RELAIS_GPIO, 0));  // départ : relais éteint

    i2c_master_bus_config_t bus_cfg = {};
    bus_cfg.i2c_port = I2C_NUM_0;
    bus_cfg.sda_io_num = SDA_GPIO;
    bus_cfg.scl_io_num = SCL_GPIO;
    bus_cfg.clk_source = I2C_CLK_SRC_DEFAULT;
    bus_cfg.glitch_ignore_cnt = 7;
    bus_cfg.flags.enable_internal_pullup = 1;
    i2c_master_bus_handle_t bus;
    ESP_ERROR_CHECK(i2c_new_master_bus(&bus_cfg, &bus));

    i2c_device_config_t dev_cfg = {};
    dev_cfg.dev_addr_length = I2C_ADDR_BIT_LEN_7;
    dev_cfg.device_address = ADRESSE_CAPTEUR;
    dev_cfg.scl_speed_hz = 100000;
    ESP_ERROR_CHECK(i2c_master_bus_add_device(bus, &dev_cfg, &capteur));

    bool relais_allume = false;  // dernier état décidé sur une mesure valide
    bool en_panne = false;       // vrai tant que la panne en cours a déjà été journalisée
    for (;;) {
        int dixiemes = 0;
        esp_err_t err = lire_temperature(&dixiemes);
        if (err == ESP_OK) {
            if (en_panne) {
                ESP_LOGI(TAG, "capteur de nouveau disponible");
                en_panne = false;
            }
            relais_allume = dixiemes > SEUIL_DIXIEMES;
            ESP_ERROR_CHECK(gpio_set_level(RELAIS_GPIO, relais_allume ? 1 : 0));
            ESP_LOGI(TAG, "température %.1f °C, relais %s", dixiemes / 10.0f, relais_allume ? "allumé" : "éteint");
        } else if (!en_panne) {
            ESP_LOGE(TAG, "lecture du capteur échouée : %s", esp_err_to_name(err));
            en_panne = true;  // on ne touche pas au relais : il garde son dernier état
        }
        vTaskDelay(pdMS_TO_TICKS(PERIODE_MS));
    }
}
EOF
