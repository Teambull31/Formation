// TP 7 : connecter l'ESP32 au Wi-Fi (station) avec des essais espacés de plus en plus longtemps, et journaliser l'adresse IP.
// Le contrôle compile ce fichier et simule, en temps virtuel, deux situations : un réseau qui refuse les 3 premières
// tentatives, puis un réseau absent. Suivez les étapes TODO dans l'ordre.
// Le SSID et le mot de passe viennent de CONFIG_ESP_WIFI_SSID et CONFIG_ESP_WIFI_PASSWORD (sdkconfig.h) : le simulateur
// les fournit avec des valeurs D'EXEMPLE. N'écrivez jamais de mot de passe dans ce fichier : le contrôle le refuse.
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

// TODO étape 1 : renvoyer l'attente, en millisecondes, avant la prochaine tentative après `n` échecs de suite (n >= 1) :
// 1000 pour n = 1, puis le double à chaque échec, sans jamais dépasser ATTENTE_MAX_MS (1 s, 2 s, 4 s, 8 s, 8 s...).
static int attente_ms(int n) {
    return 0;
}

// TODO étape 2 : initialiser la NVS avec le motif canonique : nvs_flash_init() ; si le résultat est
// ESP_ERR_NVS_NO_FREE_PAGES ou ESP_ERR_NVS_NEW_VERSION_FOUND, nvs_flash_erase() puis nvs_flash_init() de nouveau ;
// enfin ESP_ERROR_CHECK sur le dernier résultat.
static void init_nvs(void) {
}

// TODO étape 3 : le gestionnaire d'événements (il s'exécute dans la tâche sys_evt : il ne bloque JAMAIS).
//  - WIFI_EVENT / WIFI_EVENT_STA_START        : esp_wifi_connect()
//  - WIFI_EVENT / WIFI_EVENT_STA_DISCONNECTED : xEventGroupSetBits(groupe, BIT_PERDU)
//  - IP_EVENT   / IP_EVENT_STA_GOT_IP         : ESP_LOGI(TAG, "adresse IP : " IPSTR, IP2STR(&ev->ip_info.ip)) avec
//                                               ev = (ip_event_got_ip_t *)data, puis xEventGroupSetBits(groupe, BIT_CONNECTE)
static void gestionnaire(void *arg, esp_event_base_t base, int32_t id, void *data) {
}

// TODO étape 4 : créer le groupe d'événements, puis, dans l'ordre : esp_netif_init, esp_event_loop_create_default,
// esp_netif_create_default_wifi_sta, esp_wifi_init(WIFI_INIT_CONFIG_DEFAULT), enregistrer `gestionnaire` pour WIFI_EVENT
// (ESP_EVENT_ANY_ID) et pour IP_EVENT (IP_EVENT_STA_GOT_IP), esp_wifi_set_mode(WIFI_MODE_STA), esp_wifi_set_config avec
// CONFIG_ESP_WIFI_SSID et CONFIG_ESP_WIFI_PASSWORD, enfin esp_wifi_start. Les enregistrements se font AVANT esp_wifi_start.
static void demarrer_wifi(void) {
}

extern "C" void app_main(void) {
    init_nvs();
    demarrer_wifi();
    // TODO étape 5 : boucle sans fin. Attendre un des bits BIT_CONNECTE ou BIT_PERDU (xEventGroupWaitBits, effacement en
    // sortie, un seul bit suffit, attente sans limite).
    //  - BIT_CONNECTE : echecs = 0.
    //  - BIT_PERDU    : echecs++ ; si echecs >= MAX_TENTATIVES, UN SEUL ESP_LOGE(TAG, ...) puis return (plus aucune tentative) ;
    //                   sinon journaliser l'échec (ESP_LOGW), attendre attente_ms(echecs) avec vTaskDelay, puis esp_wifi_connect().
}
