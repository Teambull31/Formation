#!/usr/bin/env bash
# Solution de référence du boss ESP, phase 2 : la liaison : Wi-Fi, MQTT sur TLS, reprise après coupure, consigne en NVS (leçons es10 et es9).
# Elle écrit espboss/main.cpp en entier (les phases sont cumulatives : la phase 2 reprend tout ce qui précède).
set -euo pipefail
mkdir -p espboss
cat > espboss/main.cpp <<'EOF'
#include <atomic>
#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include "freertos/FreeRTOS.h"
#include "freertos/task.h"
#include "freertos/event_groups.h"
#include "driver/gpio.h"
#include "esp_adc/adc_oneshot.h"
#include "esp_timer.h"
#include "esp_log.h"
#include "esp_event.h"
#include "esp_netif.h"
#include "esp_wifi.h"
#include "nvs.h"
#include "nvs_flash.h"
#include "mqtt_client.h"
#include "sdkconfig.h"

static const char *TAG = "pool";
static const char *TAG_TLS = "tls";

static const char *URI_COURTIER = "mqtts://broker.local:8883";  // MQTT sur TLS : le courtier de la maison (simulé)
static const char *TOPIC_TELEMETRIE = "home/devices/pool-ctl/telemetry";
static const char *TOPIC_COMMANDE = "home/devices/pool-ctl/command";  // reçoit {"high": 75}
static const int TOURS_TELEMETRIE = 10;  // une télémétrie tous les 10 tours, donc toutes les 10 s

static const gpio_num_t POMPE_GPIO = GPIO_NUM_5;   // relais de la pompe, actif haut : niveau 1 = pompe en marche
static const adc_channel_t CANAL = ADC_CHANNEL_6;  // capteur de niveau : ADC1, canal 6 (GPIO 34), comme au TP 4
static const int RAW_0_PCT = 620;                  // valeur brute pour 0 %
static const int RAW_100_PCT = 3723;               // valeur brute pour 100 %
static const int RAW_MIN_OK = 300;                 // en dessous : fil coupé ou court-circuit vers la masse (lecture proche de 0)
static const int RAW_MAX_OK = 3900;                // au-dessus : capteur saturé ou court-circuit vers l'alimentation (proche de 4095)
static const int ECART = 20;                       // la pompe démarre 20 points sous la consigne haute
static const int HAUT_DEFAUT = 80;                 // consigne haute tant qu'aucune n'est enregistrée (en %)
static const int HAUT_MIN = 40;                    // consigne la plus basse acceptée (en %)
static const int HAUT_MAX = 80;                    // limite de sécurité : jamais de consigne au-dessus (en %)
static const int PAS_MS = 1000;                    // un tour de la boucle principale par seconde
static const int64_t DELAI_MAX_MS = 10 * 60 * 1000;  // 10 minutes de pompe sans hausse du niveau : alarme
static const int HAUSSE_MIN = 1;                   // « le niveau monte » = au moins 1 point de plus
static const int64_t FIGE_MS = 10 * 60 * 1000;     // 10 minutes de valeur brute identique : capteur figé

static const char *NVS_ESPACE_MQTT = "mqtt";   // espace de noms NVS des identifiants (15 caractères au plus)
static const char *NVS_CLE_USER = "user";      // clé NVS du nom d'utilisateur
static const char *NVS_CLE_MDP = "pass";       // clé NVS du mot de passe
static const char *NVS_ESPACE_POOL = "pool";   // espace de noms NVS de la consigne
static const char *NVS_CLE_HAUT = "haut";      // clé NVS de la consigne haute

static const EventBits_t BIT_IP = 1 << 0;      // drapeau du Wi-Fi : l'adresse IP est obtenue

// Le certificat du courtier, en PEM terminé par un NUL. Dans un vrai projet, EMBED_TXTFILES "server_cert.pem" (ou
// target_add_binary_data(... TEXT)) le place dans le programme sous ce nom ; le simulateur le fournit sous le même nom.
extern "C" const char _binary_server_cert_pem_start[];

enum class Etat { IDLE, FILLING, ALARM };          // pompe arrêtée, pompe en marche, alarme verrouillée

static EventGroupHandle_t groupe_wifi;
static adc_oneshot_unit_handle_t adc;
static esp_mqtt_client_handle_t client;
static Etat etat = Etat::IDLE;                     // l'état de la régulation (seule app_main le modifie)
static std::atomic<bool> pompe_allumee{false};     // état réel de la pompe : écrit par app_main, lu par la télémétrie
static std::atomic<int> haut{HAUT_DEFAUT};         // consigne haute : écrite par mqtt_task (commande) et par app_main (démarrage)
static std::atomic<bool> liaison{false};           // vrai tant que le client MQTT est connecté : écrit par mqtt_task
static char utilisateur[32];                       // lus en NVS, jamais écrits dans le code
static char mot_de_passe[64];
static int64_t debut_ms = 0;                       // instant de référence du délai maximal
static int niveau_debut = 0;                       // niveau à cet instant
static int dernier_brut = -1;                      // dernière valeur brute lue
static int64_t brut_change_ms = 0;                 // instant où la valeur brute a changé pour la dernière fois

// ---- Le capteur et la pompe ----

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

// Niveau de l'eau en pourcentage avec une décimale, pour la télémétrie. Lecture impossible ou invraisemblable : 100.0, le pire cas
// (sans mesure fiable, on ne remplit pas).
static double lire_niveau(void) {
    int raw = lire_brut();
    if (raw < RAW_MIN_OK || raw > RAW_MAX_OK) {
        return 100.0;
    }
    double pct = (raw - RAW_0_PCT) * 100.0 / (RAW_100_PCT - RAW_0_PCT);
    return pct < 0.0 ? 0.0 : pct > 100.0 ? 100.0 : pct;
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

// Relais d'abord : sortie, pompe éteinte (état sûr). À appeler tout au début d'app_main.
static void init_pompe(void) {
    gpio_config_t cfg = {};
    cfg.pin_bit_mask = 1ULL << POMPE_GPIO;
    cfg.mode = GPIO_MODE_OUTPUT;
    ESP_ERROR_CHECK(gpio_config(&cfg));
    ESP_ERROR_CHECK(gpio_set_level(POMPE_GPIO, 0));
    pompe_allumee = false;
}

// Allume (true) ou éteint (false) la pompe et retient son état.
static void pompe(bool allumee) {
    ESP_ERROR_CHECK(gpio_set_level(POMPE_GPIO, allumee ? 1 : 0));
    pompe_allumee = allumee;
}

// ---- La NVS : initialisation, identifiants, consigne ----

// Initialise la NVS (idiome officiel : si la partition est pleine ou d'une autre version, on l'efface).
static void init_nvs(void) {
    esp_err_t ret = nvs_flash_init();
    if (ret == ESP_ERR_NVS_NO_FREE_PAGES || ret == ESP_ERR_NVS_NEW_VERSION_FOUND) {
        ESP_ERROR_CHECK(nvs_flash_erase());
        ret = nvs_flash_init();
    }
    ESP_ERROR_CHECK(ret);
}

// Lire le nom d'utilisateur et le mot de passe en NVS, jamais dans le code.
static bool charger_identifiants(void) {
    nvs_handle_t h;
    esp_err_t err = nvs_open(NVS_ESPACE_MQTT, NVS_READONLY, &h);
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

// Enregistrer la consigne en NVS (ouvrir, écrire, VALIDER, fermer).
static void sauver_consigne(int valeur) {
    nvs_handle_t h;
    esp_err_t err = nvs_open(NVS_ESPACE_POOL, NVS_READWRITE, &h);
    if (err != ESP_OK) {
        ESP_LOGE(TAG, "nvs_open : %s", esp_err_to_name(err));
        return;
    }
    err = nvs_set_i32(h, NVS_CLE_HAUT, valeur);
    if (err == ESP_OK) {
        err = nvs_commit(h);
    }
    if (err != ESP_OK) {
        ESP_LOGE(TAG, "consigne non enregistrée : %s", esp_err_to_name(err));
    }
    nvs_close(h);
}

// Relire la consigne enregistrée, ou HAUT_DEFAUT s'il n'y en a pas (premier démarrage) ou si elle est invalide.
static int charger_consigne(void) {
    nvs_handle_t h;
    if (nvs_open(NVS_ESPACE_POOL, NVS_READONLY, &h) != ESP_OK) {
        return HAUT_DEFAUT;  // espace de noms pas encore créé : aucune consigne enregistrée
    }
    int32_t valeur = HAUT_DEFAUT;
    esp_err_t err = nvs_get_i32(h, NVS_CLE_HAUT, &valeur);
    nvs_close(h);
    if (err == ESP_ERR_NVS_NOT_FOUND) {
        return HAUT_DEFAUT;
    }
    if (err != ESP_OK || valeur < HAUT_MIN || valeur > HAUT_MAX) {
        ESP_LOGW(TAG, "consigne enregistrée inutilisable, valeur par défaut");
        return HAUT_DEFAUT;
    }
    return (int)valeur;
}

// ---- La régulation ----

// Passe en alarme : pompe coupée d'abord, puis état verrouillé, puis UNE ligne d'erreur.
static void alarme(const char *raison) {
    pompe(false);
    etat = Etat::ALARM;
    ESP_LOGE(TAG, "ALARME : %s, pompe coupée jusqu'au redémarrage", raison);
}

// Un tour de régulation : lire, décider, agir. La pompe ne tourne que tant que la liaison MQTT est établie.
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
    int consigne = haut;
    if (brut != dernier_brut) {
        dernier_brut = brut;
        brut_change_ms = t;
    }
    if (t - brut_change_ms >= FIGE_MS) {
        alarme("capteur figé (valeur brute identique depuis 10 min)");
    } else if (etat == Etat::IDLE) {
        if (liaison && niveau < consigne - ECART) {
            debut_ms = t;
            niveau_debut = niveau;
            etat = Etat::FILLING;
            pompe(true);
            ESP_LOGI(TAG, "pompe allumée à %d %%", niveau);
        }
    } else if (!liaison) {  // FILLING sans liaison : plus personne ne surveille, état sûr
        pompe(false);
        etat = Etat::IDLE;
        ESP_LOGW(TAG, "liaison perdue : pompe éteinte (état sûr)");
    } else if (niveau > consigne) {  // FILLING : niveau atteint
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

// ---- Le Wi-Fi ----

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

// ---- MQTT sur TLS : télémétrie et consigne ----

// Écrit dans buf le JSON de télémétrie {"level": 72.5, "relay": false, "high": 80}.
static int construire_json(char *buf, size_t taille, double niveau, bool relais_actif, int haut_pct) {
    return snprintf(buf, taille, "{\"level\": %.1f, \"relay\": %s, \"high\": %d}", niveau, relais_actif ? "true" : "false", haut_pct);
}

// Lit le niveau, écrit le JSON et le publie (QoS 0). Hors connexion : -1, on continue.
static void publier_telemetrie(void) {
    if (client == NULL) {
        return;  // MQTT n'est pas démarré (pas d'identifiants)
    }
    char json[96];
    construire_json(json, sizeof(json), lire_niveau(), pompe_allumee, haut);
    if (esp_mqtt_client_publish(client, TOPIC_TELEMETRIE, json, 0, 0, 0) < 0) {
        ESP_LOGI(TAG, "télémétrie non envoyée : client déconnecté");
    }
}

// Exécute une commande {"high": N}. data n'est PAS terminée par un NUL : seule len dit sa taille.
static void traiter_commande(const char *data, int len) {
    char msg[64];
    int n = len < (int)sizeof(msg) - 1 ? len : (int)sizeof(msg) - 1;
    memcpy(msg, data, n);
    msg[n] = '\0';
    const char *p = strstr(msg, "\"high\"");
    if (p == NULL) {
        return;  // pas une commande : on ignore
    }
    p += strlen("\"high\"");
    while (*p == ' ' || *p == ':') {
        p++;
    }
    char *fin;
    long valeur = strtol(p, &fin, 10);
    if (fin == p) {
        return;  // pas un nombre : on ignore
    }
    if (valeur < HAUT_MIN || valeur > HAUT_MAX) {
        ESP_LOGW(TAG, "setpoint refused: high=%ld", valeur);
        return;
    }
    haut = (int)valeur;
    sauver_consigne((int)valeur);
    ESP_LOGI(TAG, "consigne enregistrée : %ld %%", valeur);
}

// Le gestionnaire des événements MQTT (tâche mqtt_task, il ne bloque jamais).
static void gestionnaire_mqtt(void *arg, esp_event_base_t base, int32_t id, void *data) {
    esp_mqtt_event_handle_t ev = (esp_mqtt_event_handle_t)data;
    switch ((esp_mqtt_event_id_t)id) {
    case MQTT_EVENT_CONNECTED:
        liaison = true;
        ESP_LOGI(TAG, "connexion sécurisée établie");
        esp_mqtt_client_subscribe_single(ev->client, TOPIC_COMMANDE, 1);  // la session est propre : on se réabonne à chaque connexion
        break;
    case MQTT_EVENT_ERROR:
        if (ev->error_handle->error_type == MQTT_ERROR_TYPE_TCP_TRANSPORT) {
            ESP_LOGW(TAG_TLS, "échec TLS : esp_err 0x%x, pile TLS 0x%x, drapeaux du certificat 0x%x",
                     (unsigned)ev->error_handle->esp_tls_last_esp_err, (unsigned)ev->error_handle->esp_tls_stack_err,
                     (unsigned)ev->error_handle->esp_tls_cert_verify_flags);
        }
        break;
    case MQTT_EVENT_DISCONNECTED:
        liaison = false;  // app_main éteint la pompe au prochain tour (au plus 1 s)
        break;
    case MQTT_EVENT_DATA:
        if (ev->topic_len == (int)strlen(TOPIC_COMMANDE) && strncmp(ev->topic, TOPIC_COMMANDE, ev->topic_len) == 0) {
            traiter_commande(ev->data, ev->data_len);
        }
        break;
    default:
        break;
    }
}

// Configure le client en mqtts:// avec vérification du certificat du courtier, puis le démarre. La bibliothèque se reconnecte
// toute seule (toutes les 10 s par défaut) et n'abandonne jamais.
static void demarrer_mqtt(void) {
    esp_mqtt_client_config_t cfg = {};
    cfg.broker.address.uri = URI_COURTIER;
    cfg.broker.verification.certificate = _binary_server_cert_pem_start;
    cfg.credentials.client_id = "pool-ctl";
    cfg.credentials.username = utilisateur;
    cfg.credentials.authentication.password = mot_de_passe;
    client = esp_mqtt_client_init(&cfg);
    ESP_ERROR_CHECK(esp_mqtt_client_register_event(client, (esp_mqtt_event_id_t)ESP_EVENT_ANY_ID, gestionnaire_mqtt, NULL));
    ESP_ERROR_CHECK(esp_mqtt_client_start(client));
}

extern "C" void app_main(void) {
    init_pompe();  // tout premier geste : pompe éteinte avant la NVS, le Wi-Fi, le capteur et MQTT
    init_adc();
    init_nvs();
    haut = charger_consigne();  // la consigne enregistrée, relue avant toute régulation
    wifi_connecter();
    if (charger_identifiants()) {
        demarrer_mqtt();
    } else {
        ESP_LOGE(TAG, "pas d'identifiants en NVS : MQTT n'est pas démarré, la pompe reste éteinte");
    }
    for (int tour = 0;; tour++) {
        reguler();
        if (tour % TOURS_TELEMETRIE == 0) {
            publier_telemetrie();
        }
        vTaskDelay(pdMS_TO_TICKS(PAS_MS));
    }
}
EOF
