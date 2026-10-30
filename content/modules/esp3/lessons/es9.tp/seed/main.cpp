// TP 9 : robustesse. La consigne de niveau haut du contrôleur de piscine se règle par MQTT ({"high": 75}), survit aux
// redémarrages (NVS), le programme se réabonne après une coupure du courtier et un watchdog de tâche surveille la boucle.
// Fourni (ne le modifiez pas) : le Wi-Fi minimal du TP 7, l'initialisation de la NVS, le relais GPIO 5, le capteur de niveau,
// le JSON de télémétrie et le démarrage du client MQTT. Suivez les étapes TODO dans l'ordre.
#include <atomic>
#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include "freertos/FreeRTOS.h"
#include "freertos/task.h"
#include "freertos/event_groups.h"
#include "driver/gpio.h"
#include "esp_adc/adc_oneshot.h"
#include "esp_log.h"
#include "esp_event.h"
#include "esp_netif.h"
#include "esp_system.h"
#include "esp_task_wdt.h"
#include "esp_wifi.h"
#include "nvs.h"
#include "nvs_flash.h"
#include "mqtt_client.h"
#include "sdkconfig.h"

static const char *TAG = "robust";

static const char *URI_COURTIER = "mqtt://192.168.1.10:1883";  // le courtier de la maison (simulé)
static const char *TOPIC_TELEMETRIE = "home/devices/pool-ctl/telemetry";
static const char *TOPIC_COMMANDE = "home/devices/pool-ctl/command";  // reçoit {"high": 75}
static const int PAS_MS = 1000;          // un tour de la boucle principale par seconde
static const int TOURS_TELEMETRIE = 10;  // une télémétrie tous les 10 tours, donc toutes les 10 s

static const int HAUT_DEFAUT = 60;  // consigne de niveau haut tant qu'aucune n'est enregistrée (en %)
static const int HAUT_MIN = 10;     // consigne la plus basse acceptée (en %)
static const int HAUT_MAX = 80;     // limite de sécurité du TP 6 : jamais de consigne au-dessus (en %)
static const char *NVS_ESPACE = "pool";  // espace de noms NVS (15 caractères au plus)
static const char *NVS_CLE = "haut";     // clé NVS de la consigne (15 caractères au plus)
static const uint32_t WDT_DELAI_MS = 15000;  // délai du watchdog de tâche : bien plus long qu'un tour de boucle

static const gpio_num_t RELAIS_GPIO = GPIO_NUM_5;  // relais de la pompe, actif haut (TP 6)
static const adc_channel_t CANAL = ADC_CHANNEL_6;  // capteur de niveau : ADC1, canal 6 (TP 4 et TP 6)
static const int RAW_0_PCT = 620;                  // valeur brute pour 0 %
static const int RAW_100_PCT = 3723;               // valeur brute pour 100 %

static const EventBits_t BIT_IP = 1 << 0;  // drapeau : l'adresse IP est obtenue

static EventGroupHandle_t groupe_wifi;
static adc_oneshot_unit_handle_t adc;
static esp_mqtt_client_handle_t client;
static std::atomic<bool> relais{false};     // état du relais : lu et écrit par app_main
static std::atomic<int> haut{HAUT_DEFAUT};  // consigne de niveau haut : écrite par mqtt_task (commande) et par app_main (démarrage)

// ---- Fourni : le Wi-Fi (version minimale du TP 7), la NVS, le relais, le capteur et le JSON de télémétrie ----

static void gestionnaire_wifi(void *arg, esp_event_base_t base, int32_t id, void *data) {
    if (base == WIFI_EVENT && (id == WIFI_EVENT_STA_START || id == WIFI_EVENT_STA_DISCONNECTED)) {
        esp_wifi_connect();
    } else if (base == IP_EVENT && id == IP_EVENT_STA_GOT_IP) {
        xEventGroupSetBits(groupe_wifi, BIT_IP);
    }
}

// Bloque jusqu'à l'obtention d'une adresse IP : MQTT a besoin du réseau. (La NVS est déjà initialisée par init_nvs.)
static void wifi_connecter(void) {
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

// Initialise la NVS (idiome officiel : si la partition est pleine ou d'une autre version, on l'efface).
static void init_nvs(void) {
    esp_err_t ret = nvs_flash_init();
    if (ret == ESP_ERR_NVS_NO_FREE_PAGES || ret == ESP_ERR_NVS_NEW_VERSION_FOUND) {
        ESP_ERROR_CHECK(nvs_flash_erase());
        ret = nvs_flash_init();
    }
    ESP_ERROR_CHECK(ret);
}

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

// Écrit dans buf le JSON de télémétrie {"level": 72.5, "relay": false, "high": 75} (comme au TP 8, plus la consigne).
static int construire_json(char *buf, size_t taille, double niveau, bool relais_actif, int haut_pct) {
    return snprintf(buf, taille, "{\"level\": %.1f, \"relay\": %s, \"high\": %d}", niveau, relais_actif ? "true" : "false", haut_pct);
}

// ---- À ÉCRIRE : suivez les étapes dans l'ordre ----

// TODO étape 1 : enregistrer la consigne en NVS : nvs_open(NVS_ESPACE, NVS_READWRITE, &h), nvs_set_i32(h, NVS_CLE, valeur),
// nvs_commit(h) (SANS lui, rien n'est garanti après un redémarrage), nvs_close(h). Vérifier chaque code de retour : en cas
// d'erreur, un ESP_LOGE avec esp_err_to_name et on continue (pas d'ESP_ERROR_CHECK : une NVS en panne ne doit pas arrêter la pompe).
static void sauver_consigne(int valeur) {
}

// TODO étape 2 : relire la consigne. nvs_open(NVS_ESPACE, NVS_READONLY, &h) échoue s'il n'y a encore rien d'enregistré :
// renvoyer HAUT_DEFAUT. Sinon nvs_get_i32(h, NVS_CLE, &valeur), puis nvs_close(h) ; ESP_ERR_NVS_NOT_FOUND : HAUT_DEFAUT ;
// autre erreur, ou valeur hors de HAUT_MIN..HAUT_MAX : un ESP_LOGW et HAUT_DEFAUT. Sinon la valeur lue.
static int charger_consigne(void) {
    return HAUT_DEFAUT;
}

// TODO étape 3 : exécuter une commande {"high": N}. data n'est PAS terminée par un NUL : seule len dit sa taille.
//  - copier au plus 63 octets dans msg[64] terminé par un NUL (memcpy puis msg[n] = '\0') ;
//  - chercher "high" (avec ses guillemets) avec strstr ; absent : on ignore ; sauter les espaces et les « : » ;
//  - lire le nombre avec strtol(p, &fin, 10) ; fin == p (aucun chiffre) : on ignore ;
//  - hors de HAUT_MIN..HAUT_MAX : refuser avec exactement ESP_LOGW(TAG, "setpoint refused: high=%ld", valeur); et ne rien changer ;
//  - sinon : haut = valeur, puis sauver_consigne(valeur).
static void traiter_commande(const char *data, int len) {
}

// TODO étape 4 : le gestionnaire des événements MQTT (tâche mqtt_task, il ne bloque jamais). ev = (esp_mqtt_event_handle_t)data ;
//  - MQTT_EVENT_CONNECTED : s'abonner à TOPIC_COMMANDE en QoS 1 (esp_mqtt_client_subscribe_single). À CHAQUE connexion.
//  - MQTT_EVENT_DATA : si le sujet reçu est TOPIC_COMMANDE (avec ev->topic_len : strlen et strncmp), traiter_commande(ev->data, ev->data_len).
static void gestionnaire_mqtt(void *arg, esp_event_base_t base, int32_t id, void *data) {
}

// Fourni : démarre le client MQTT (TP 8). La reconnexion automatique reste activée, la session est propre (par défaut).
static void demarrer_mqtt(void) {
    esp_mqtt_client_config_t cfg = {};
    cfg.broker.address.uri = URI_COURTIER;
    cfg.credentials.client_id = "pool-ctl";
    client = esp_mqtt_client_init(&cfg);
    ESP_ERROR_CHECK(esp_mqtt_client_register_event(client, (esp_mqtt_event_id_t)ESP_EVENT_ANY_ID, gestionnaire_mqtt, NULL));
    ESP_ERROR_CHECK(esp_mqtt_client_start(client));
}

// TODO étape 5 : publier la télémétrie : construire_json(json, sizeof(json), lire_niveau(), relais, haut) dans un char json[96], puis
// esp_mqtt_client_publish(client, TOPIC_TELEMETRIE, json, 0, 0, 0). Si le résultat est négatif (hors connexion) : un ESP_LOGI et on
// continue. Surtout PAS d'ESP_ERROR_CHECK autour de la publication.
static void publier_telemetrie(void) {
}

// TODO étape 6 : piloter le relais d'après la consigne : voulu = (lire_niveau() < haut) ; si voulu diffère de relais, regler_relais(voulu).
static void appliquer_consigne(void) {
}

// TODO étape 7 : esp_task_wdt_config_t cfg = {} avec timeout_ms = WDT_DELAI_MS, idle_core_mask = (1 << 0) | (1 << 1), trigger_panic = true ;
// ESP_ERROR_CHECK(esp_task_wdt_reconfigure(&cfg)) puis ESP_ERROR_CHECK(esp_task_wdt_add(NULL)) (abonne la tâche courante).
static void configurer_watchdog(void) {
}

extern "C" void app_main(void) {
    init_relais();
    init_adc();
    init_nvs();
    // TODO étape 8 : dans cet ordre : relire la consigne (haut = charger_consigne()), appliquer_consigne() (le relais n'est
    // piloté qu'APRÈS la relecture), wifi_connecter(), demarrer_mqtt(), configurer_watchdog(), puis la boucle sans fin :
    // à chaque tour, ESP_ERROR_CHECK(esp_task_wdt_reset()), appliquer_consigne(), publier_telemetrie() tous les TOURS_TELEMETRIE
    // tours (tour % TOURS_TELEMETRIE == 0), puis vTaskDelay(pdMS_TO_TICKS(PAS_MS)).
}
