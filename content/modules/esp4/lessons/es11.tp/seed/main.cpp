// TP 11 : mises à jour OTA. Le contrôleur de piscine (client MQTT/TLS du TP 10) reçoit {"ota": "<url>"} sur le sujet de commande et
// met son micrologiciel à jour par esp_https_ota : seulement vers une version strictement plus récente, relais éteint pendant la
// mise à jour, redémarrage uniquement après un succès. Fourni (ne le modifiez pas) : tout le client du TP 10, l'extraction de l'adresse
// (url_dans_commande), celle de la version (version_depuis_url) et app_main. Suivez les étapes TODO dans l'ordre.
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
#include "esp_wifi.h"
#include "nvs.h"
#include "nvs_flash.h"
#include "mqtt_client.h"
#include "esp_app_desc.h"
#include "esp_http_client.h"
#include "esp_https_ota.h"
#include "esp_system.h"
#include "sdkconfig.h"

static const char *TAG = "ota";

static const char *URI_COURTIER = "mqtts://broker.local:8883";  // MQTT sur TLS : le courtier de la maison (simulé)
static const char *TOPIC_TELEMETRIE = "home/devices/pool-ctl/telemetry";
static const char *TOPIC_COMMANDE = "home/devices/pool-ctl/command";
static const int PAS_MS = 1000;          // un tour de la boucle principale par seconde
static const int TOURS_TELEMETRIE = 10;  // une télémétrie tous les 10 tours, donc toutes les 10 s
static const double LIMITE_PCT = 80.0;   // limite de sécurité du TP 6 : jamais de remplissage au-dessus

static const char *NVS_ESPACE = "mqtt";   // espace de noms NVS des identifiants (15 caractères au plus)
static const char *NVS_CLE_USER = "user";  // clé NVS du nom d'utilisateur
static const char *NVS_CLE_MDP = "pass";   // clé NVS du mot de passe

static const gpio_num_t RELAIS_GPIO = GPIO_NUM_5;  // relais de la pompe, actif haut (TP 6)
static const adc_channel_t CANAL = ADC_CHANNEL_6;  // capteur de niveau : ADC1, canal 6 (TP 4 et TP 6)
static const int RAW_0_PCT = 620;                  // valeur brute pour 0 %
static const int RAW_100_PCT = 3723;               // valeur brute pour 100 %

static const EventBits_t BIT_IP = 1 << 0;     // drapeau du Wi-Fi : l'adresse IP est obtenue
static const EventBits_t BIT_PERDU = 1 << 0;  // drapeaux de app_main : une connexion MQTT a échoué ou a été perdue
static const EventBits_t BIT_OTA = 1 << 1;    //   et : une commande {"ota": "<url>"} est arrivée (l'adresse est dans url_ota)

// Le certificat du courtier, en PEM terminé par un NUL. Dans un vrai projet, EMBED_TXTFILES "server_cert.pem" (ou
// target_add_binary_data(... TEXT)) le place dans le programme sous ce nom ; le simulateur le fournit sous le même nom.
extern "C" const char _binary_server_cert_pem_start[];

static EventGroupHandle_t groupe_wifi;
static EventGroupHandle_t groupe_liaison;
static adc_oneshot_unit_handle_t adc;
static esp_mqtt_client_handle_t client;
static std::atomic<bool> relais{false};  // état du relais : écrit par app_main et par la tâche mqtt_task
static std::atomic<int> echecs{0};       // échecs de connexion de suite : mis à 0 à chaque connexion réussie
static char utilisateur[32];             // lus en NVS (étape 1), jamais écrits dans le code
static char mot_de_passe[64];
static char url_ota[200];                 // l'adresse de la commande {"ota": "..."}, écrite par url_dans_commande
static std::atomic<bool> ota_demandee{false};  // vrai de la commande reçue jusqu'à la fin du traitement : une seule à la fois

// ---- Fourni : le Wi-Fi (version minimale du TP 7), la NVS, le relais, le capteur, le JSON, la télémétrie, les commandes ----

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

// Lit le niveau, écrit le JSON {"level": 72.5, "relay": false} (TP 8) et le publie (QoS 0). Hors connexion : -1, on continue.
static void publier_telemetrie(void) {
    char json[64];
    snprintf(json, sizeof(json), "{\"level\": %.1f, \"relay\": %s}", lire_niveau(), relais ? "true" : "false");
    if (esp_mqtt_client_publish(client, TOPIC_TELEMETRIE, json, 0, 0, 0) < 0) {
        ESP_LOGI(TAG, "télémétrie non envoyée : client déconnecté");
    }
}

// Exécute (ou refuse) la commande {"relay": true} / {"relay": false} (TP 8). data n'est PAS terminée par un NUL.
static void traiter_commande(const char *data, int len) {
    char msg[64];
    int n = len < (int)sizeof(msg) - 1 ? len : (int)sizeof(msg) - 1;
    memcpy(msg, data, n);
    msg[n] = '\0';
    const char *p = strstr(msg, "\"relay\"");
    if (p == NULL) {
        return;  // pas une commande : on ignore
    }
    p += strlen("\"relay\"");
    while (*p == ' ' || *p == ':') {
        p++;
    }
    bool voulu;
    if (strncmp(p, "true", 4) == 0) {
        voulu = true;
    } else if (strncmp(p, "false", 5) == 0) {
        voulu = false;
    } else {
        return;  // la valeur n'est ni true ni false : on ignore
    }
    if (voulu && ota_demandee) {
        ESP_LOGW(TAG, "commande refusée : mise à jour en cours");  // pompe à l'arrêt tant qu'une mise à jour est demandée ou en cours
        return;
    }
    if (voulu) {
        double niveau = lire_niveau();
        if (niveau > LIMITE_PCT) {
            ESP_LOGW(TAG, "command refused: level=%d%%", (int)niveau);
            return;
        }
    }
    regler_relais(voulu);
}

// Attente avant la tentative suivante, après n échecs de suite (n >= 1) : 1 s, 2 s, 4 s, 8 s, puis 8 s (plafond). Comme au TP 7.
static int attente_ms(int n) {
    int ms = 1000;
    for (int i = 1; i < n && ms < 8000; i++) {
        ms *= 2;
    }
    return ms;
}

// Extrait l'adresse de la commande {"ota": "<url>"} (data n'est PAS terminée par un NUL) et la copie dans url_ota. Renvoie false si ce
// n'est pas une commande de mise à jour, si l'adresse est vide ou trop longue, ou si une mise à jour est déjà demandée.
static bool url_dans_commande(const char *data, int len) {
    char msg[256];
    int n = len < (int)sizeof(msg) - 1 ? len : (int)sizeof(msg) - 1;
    memcpy(msg, data, n);
    msg[n] = '\0';
    const char *p = strstr(msg, "\"ota\"");
    if (p == NULL) {
        return false;
    }
    p = strchr(p + strlen("\"ota\""), '"');
    if (p == NULL) {
        return false;
    }
    p++;
    const char *fin = strchr(p, '"');
    if (fin == NULL || fin == p || (size_t)(fin - p) >= sizeof(url_ota)) {
        return false;
    }
    if (ota_demandee.exchange(true)) {
        return false;  // une mise à jour est déjà en cours de traitement
    }
    memcpy(url_ota, p, fin - p);
    url_ota[fin - p] = '\0';
    return true;
}

// La version annoncée par l'adresse : le nom du fichier est « <nom>-<version>.bin », par exemple pool-ctl-1.10.0.bin donne 1.10.0.
// Renvoie false si le nom n'a pas cette forme.
static bool version_depuis_url(const char *url, char *version, size_t taille) {
    const char *tiret = strrchr(url, '-');
    const char *fin = strrchr(url, '.');
    if (tiret == NULL || fin == NULL || fin <= tiret + 1 || strcmp(fin, ".bin") != 0 || strchr(tiret, '/') != NULL) {
        return false;
    }
    size_t n = fin - (tiret + 1);
    if (n >= taille) {
        return false;
    }
    memcpy(version, tiret + 1, n);
    version[n] = '\0';
    return true;
}

// ---- À ÉCRIRE : suivez les étapes dans l'ordre ----

// TODO étape 1 : la version proposée est-elle strictement plus récente que la courante ? Chaque version s'écrit « x.y.z » (trois entiers
// positifs ou nuls séparés par des points) : comparer x, puis y, puis z, comme des NOMBRES (1.10.0 est plus récente que 1.9.0 ; pas de
// strcmp). Renvoyer false si l'une des deux n'a pas cette forme exacte (par exemple « 1.2 » ou « 1.2.3a »), et si elles sont égales.
static bool version_plus_recente(const char *nouvelle, const char *courante) {
    (void)nouvelle;
    (void)courante;
    return false;
}

// Fourni : lire le nom d'utilisateur et le mot de passe en NVS, jamais dans le code.
static bool charger_identifiants(void) {
    nvs_handle_t h;
    esp_err_t err = nvs_open(NVS_ESPACE, NVS_READONLY, &h);
    if (err != ESP_OK) {
        ESP_LOGE(TAG, "identifiants introuvables (nvs_open : %s)", esp_err_to_name(err));
        return false;
    }
    size_t taille_user = sizeof(utilisateur);
    size_t taille_mdp = sizeof(mot_de_passe);
    esp_err_t e_user = nvs_get_str(h, NVS_CLE_USER, utilisateur, &taille_user);
    esp_err_t e_mdp = nvs_get_str(h, NVS_CLE_MDP, mot_de_passe, &taille_mdp);
    nvs_close(h);
    if (e_user != ESP_OK || e_mdp != ESP_OK) {
        ESP_LOGE(TAG, "identifiants illisibles (%s, %s)", esp_err_to_name(e_user), esp_err_to_name(e_mdp));
        return false;
    }
    return true;
}

// Fourni : le gestionnaire des événements MQTT (tâche mqtt_task, il ne bloque jamais).
static void gestionnaire_mqtt(void *arg, esp_event_base_t base, int32_t id, void *data) {
    esp_mqtt_event_handle_t ev = (esp_mqtt_event_handle_t)data;
    switch ((esp_mqtt_event_id_t)id) {
    case MQTT_EVENT_CONNECTED:
        echecs = 0;
        ESP_LOGI(TAG, "connexion sécurisée établie");
        esp_mqtt_client_subscribe_single(ev->client, TOPIC_COMMANDE, 1);
        break;
    case MQTT_EVENT_ERROR:
        if (ev->error_handle->error_type == MQTT_ERROR_TYPE_TCP_TRANSPORT) {
            ESP_LOGW(TAG, "échec TLS : esp_err 0x%x, pile TLS 0x%x, drapeaux du certificat 0x%x",
                     (unsigned)ev->error_handle->esp_tls_last_esp_err, (unsigned)ev->error_handle->esp_tls_stack_err,
                     (unsigned)ev->error_handle->esp_tls_cert_verify_flags);
        }
        break;
    case MQTT_EVENT_DISCONNECTED:
        xEventGroupSetBits(groupe_liaison, BIT_PERDU);
        break;
    case MQTT_EVENT_DATA:
        if (ev->topic_len == (int)strlen(TOPIC_COMMANDE) && strncmp(ev->topic, TOPIC_COMMANDE, ev->topic_len) == 0) {
            traiter_commande(ev->data, ev->data_len);
        // TODO étape 2 : si url_dans_commande(ev->data, ev->data_len) renvoie true, lever BIT_OTA dans groupe_liaison (xEventGroupSetBits) ;
        // surtout ne rien télécharger ici : ce gestionnaire s'exécute dans la tâche mqtt_task, qui ne doit jamais attendre.
        }
        break;
    default:
        break;
    }
}

// Fourni : configurer le client en mqtts:// avec vérification du certificat du courtier, puis le démarrer.
static void demarrer_mqtt(void) {
    esp_mqtt_client_config_t cfg = {};
    cfg.broker.address.uri = URI_COURTIER;
    cfg.broker.verification.certificate = _binary_server_cert_pem_start;
    cfg.credentials.client_id = "pool-ctl";
    cfg.credentials.username = utilisateur;
    cfg.credentials.authentication.password = mot_de_passe;
    cfg.network.disable_auto_reconnect = true;  // c'est le programme qui décide quand réessayer (reagir_a_la_perte)
    client = esp_mqtt_client_init(&cfg);
    ESP_ERROR_CHECK(esp_mqtt_client_register_event(client, (esp_mqtt_event_id_t)ESP_EVENT_ANY_ID, gestionnaire_mqtt, NULL));
    ESP_ERROR_CHECK(esp_mqtt_client_start(client));
}

// Fourni : la liaison est perdue (ou n'a pas pu s'établir) : relais en état sûr, attente croissante, nouvelle tentative.
static void reagir_a_la_perte(void) {
    if (relais) {
        regler_relais(false);
        ESP_LOGW(TAG, "liaison perdue : relais éteint (état sûr)");
    }
    int n = ++echecs;
    int attente = attente_ms(n);
    ESP_LOGW(TAG, "échec n° %d : nouvelle tentative dans %d ms", n, attente);
    vTaskDelay(pdMS_TO_TICKS(attente));
    esp_err_t err = esp_mqtt_client_reconnect(client);
    if (err != ESP_OK) {
        ESP_LOGE(TAG, "esp_mqtt_client_reconnect : %s", esp_err_to_name(err));
    }
}

// TODO étape 3 : traiter une demande de mise à jour (appelée par app_main avec l'adresse reçue). Dans cet ordre :
//  1. si l'adresse ne commence pas par "https://" : ESP_LOGW de refus qui contient l'adresse, puis return ;
//  2. version proposée : version_depuis_url(url, version, sizeof(version)) ; version courante : esp_app_get_description()->version ;
//     si la proposée n'est pas strictement plus récente (version_plus_recente) : ESP_LOGW de refus qui contient les deux versions, return ;
//  3. regler_relais(false) : état sûr pendant la mise à jour ;
//  4. esp_http_client_config_t avec .url et .cert_pem = _binary_server_cert_pem_start, esp_https_ota_config_t avec .http_config,
//     puis esp_err_t err = esp_https_ota(&cfg) (surtout pas dans ESP_ERROR_CHECK) ;
//  5. si err != ESP_OK : ESP_LOGE qui contient esp_err_to_name(err), return (pas de redémarrage) ;
//  6. sinon : ESP_LOGI de succès puis esp_restart().
static void mettre_a_jour(const char *url) {
    (void)url;
}

extern "C" void app_main(void) {
    init_relais();
    init_adc();
    init_nvs();
    groupe_liaison = xEventGroupCreate();
    wifi_connecter();
    ESP_LOGI(TAG, "démarrage, version %s", esp_app_get_description()->version);
    if (charger_identifiants()) {
        demarrer_mqtt();
    } else {
        ESP_LOGE(TAG, "pas d'identifiants en NVS : MQTT n'est pas démarré");
    }
    for (int tour = 0;; tour++) {
        EventBits_t bits = xEventGroupWaitBits(groupe_liaison, BIT_PERDU | BIT_OTA, pdTRUE, pdFALSE, pdMS_TO_TICKS(PAS_MS));
        if (bits & BIT_PERDU) {
            reagir_a_la_perte();
        }
        if (bits & BIT_OTA) {
            char url[sizeof(url_ota)];
            strcpy(url, url_ota);
            mettre_a_jour(url);
            ota_demandee = false;  // la prochaine commande est acceptée
        }
        if (tour % TOURS_TELEMETRIE == 0) {
            publier_telemetrie();
        }
    }
}
