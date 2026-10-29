// TP 8 : MQTT. Publier la télémétrie de la piscine, annoncer le statut (avec testament) et exécuter les commandes
// sans jamais dépasser la limite de sécurité de 80 % du TP 6. Le contrôle compile ce fichier et simule, en temps virtuel,
// trois situations : niveau normal (commandes acceptées), niveau à 85 % (commande refusée), coupure du courtier.
// Fourni (ne le modifiez pas) : le Wi-Fi du TP 7 en version minimale, le relais GPIO 5, le capteur de niveau. Le TP 8 ne
// refait pas le TP 7 : il commence quand le réseau est là. Suivez les étapes TODO dans l'ordre.
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

// ---- À ÉCRIRE : suivez les étapes dans l'ordre ----

// TODO étape 1 : écrire dans buf (taille octets) le JSON {"level": 72.5, "relay": false} avec un seul snprintf :
// le niveau avec UNE décimale (%.1f), le relais en toutes lettres true ou false (sans guillemets). Renvoyer le résultat de snprintf.
static int construire_json(char *buf, size_t taille, double niveau, bool relais_actif) {
    return 0;
}

// TODO étape 2 : lire le niveau (lire_niveau), construire le JSON dans un tampon local (char json[64]) avec l'état
// du relais, le publier sur TOPIC_TELEMETRIE avec esp_mqtt_client_publish(client, topic, json, 0, 0, 0)
// (len 0 = strlen, QoS 0, retain 0). Si le résultat est négatif (client déconnecté) : un ESP_LOGI et on passe.
static void publier_telemetrie(void) {
}

// TODO étape 3 : exécuter (ou refuser) la commande. data n'est PAS terminée par un NUL : seule len dit sa taille.
//  - copier au plus 63 octets de data dans un tampon local msg[64] terminé par un NUL (memcpy puis msg[n] = '\0') ;
//  - chercher "relay" (avec ses guillemets) avec strstr ; absent : ce n'est pas une commande, on ignore ;
//  - sauter les espaces et les « : » qui suivent, puis lire true ou false (strncmp) ; autre chose : on ignore ;
//  - si la commande est « allumer » : lire le niveau ; au-dessus de LIMITE_PCT, refuser avec exactement
//      ESP_LOGW(TAG, "command refused: level=%d%%", (int)niveau);   et ne rien changer ;
//  - sinon, regler_relais(voulu).
static void traiter_commande(const char *data, int len) {
}

// TODO étape 4 : le gestionnaire des événements MQTT (il s'exécute dans la tâche mqtt_task). Récupérer
// ev = (esp_mqtt_event_handle_t)data, puis selon (esp_mqtt_event_id_t)id :
//  - MQTT_EVENT_CONNECTED : publier « online » sur TOPIC_STATUT en QoS 1, retenu (retain 1), puis s'abonner à
//    TOPIC_COMMANDE en QoS 1 avec esp_mqtt_client_subscribe_single. À CHAQUE connexion : la session est propre.
//  - MQTT_EVENT_DATA : si le topic reçu est TOPIC_COMMANDE (comparer avec ev->topic_len : strlen et strncmp, pas
//    strcmp), appeler traiter_commande(ev->data, ev->data_len).
static void gestionnaire_mqtt(void *arg, esp_event_base_t base, int32_t id, void *data) {
}

// TODO étape 5 : configurer le client, l'enregistrer, le démarrer. Un esp_mqtt_client_config_t cfg = {}; avec
// broker.address.uri = URI_COURTIER, credentials.client_id = "pool-ctl", et le testament :
// session.last_will.topic = TOPIC_STATUT, .msg = "offline", .qos = 1, .retain = true. Puis, dans la variable
// globale client : esp_mqtt_client_init(&cfg), esp_mqtt_client_register_event(client, (esp_mqtt_event_id_t)ESP_EVENT_ANY_ID,
// gestionnaire_mqtt, NULL), esp_mqtt_client_start(client), les deux derniers dans ESP_ERROR_CHECK.
static void demarrer_mqtt(void) {
}

extern "C" void app_main(void) {
    init_relais();
    init_adc();
    wifi_connecter();
    demarrer_mqtt();
    // TODO étape 6 : boucle sans fin : publier_telemetrie(), puis attendre PERIODE_MS avec vTaskDelay(pdMS_TO_TICKS(...)).
}
