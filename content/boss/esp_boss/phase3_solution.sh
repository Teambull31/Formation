#!/usr/bin/env bash
# Solution de référence du boss ESP, phase 3 : la livraison : OTA valide ou corrompue, coupure de courant, certificat invalide, retour arrière (leçons es11 et es12).
# Elle écrit espboss/main.cpp en entier (les phases sont cumulatives : la phase 3 reprend tout ce qui précède).
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
#include "esp_app_desc.h"
#include "esp_http_client.h"
#include "esp_https_ota.h"
#include "esp_ota_ops.h"
#include "esp_system.h"
#include "sdkconfig.h"

static const char *TAG = "pool";
static const char *TAG_TLS = "tls";
static const char *TAG_OTA = "ota";
static const char *TAG_TEST = "autotest";

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
static const int DELAI_AUTOTEST_MS = 60000;        // durée maximale de l'auto-test, comptée depuis le démarrage : 60 s, jamais plus, jamais infinie

static const char *NVS_ESPACE_MQTT = "mqtt";   // espace de noms NVS des identifiants (15 caractères au plus)
static const char *NVS_CLE_USER = "user";      // clé NVS du nom d'utilisateur
static const char *NVS_CLE_MDP = "pass";       // clé NVS du mot de passe
static const char *NVS_ESPACE_POOL = "pool";   // espace de noms NVS de la consigne
static const char *NVS_CLE_HAUT = "haut";      // clé NVS de la consigne haute

static const EventBits_t BIT_IP = 1 << 0;         // drapeau du Wi-Fi : l'adresse IP est obtenue
static const EventBits_t BIT_CONNECTE = 1 << 0;  // drapeaux de groupe_liaison : le client MQTT est connecté
static const EventBits_t BIT_OTA = 1 << 1;       //   et : une commande {"ota": "<url>"} est arrivée (l'adresse est dans url_ota)

// Le certificat du courtier, en PEM terminé par un NUL. Dans un vrai projet, EMBED_TXTFILES "server_cert.pem" (ou
// target_add_binary_data(... TEXT)) le place dans le programme sous ce nom ; le simulateur le fournit sous le même nom.
extern "C" const char _binary_server_cert_pem_start[];

enum class Etat { IDLE, FILLING, ALARM };          // pompe arrêtée, pompe en marche, alarme verrouillée

static EventGroupHandle_t groupe_wifi;
static EventGroupHandle_t groupe_liaison;
static adc_oneshot_unit_handle_t adc;
static esp_mqtt_client_handle_t client;
static Etat etat = Etat::IDLE;                     // l'état de la régulation (seule app_main le modifie)
static std::atomic<bool> pompe_allumee{false};     // état réel de la pompe : écrit par app_main, lu par la télémétrie
static std::atomic<int> haut{HAUT_DEFAUT};         // consigne haute : écrite par mqtt_task (commande) et par app_main (démarrage)
static std::atomic<bool> liaison{false};           // vrai tant que le client MQTT est connecté : écrit par mqtt_task
static char utilisateur[32];                       // lus en NVS, jamais écrits dans le code
static char mot_de_passe[64];
static char url_ota[200];                          // l'adresse de la commande {"ota": "..."}, écrite par url_dans_commande
static std::atomic<bool> ota_demandee{false};      // vrai de la commande reçue jusqu'à la fin du traitement : une seule à la fois
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

// Pompe éteinte, régulation à zéro (jamais en alarme : une alarme reste verrouillée). Appelée avant une mise à jour.
static void mettre_en_securite(void) {
    pompe(false);
    if (etat == Etat::FILLING) {
        etat = Etat::IDLE;
    }
}

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

// Attend l'adresse IP au plus delai_ms (jamais sans limite : une image dont le Wi-Fi est cassé ne doit pas rester bloquée à l'essai).
// Renvoie true si l'adresse est obtenue. (La NVS est déjà initialisée par init_nvs.)
static bool wifi_connecter(int delai_ms) {
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
    EventBits_t bits = xEventGroupWaitBits(groupe_wifi, BIT_IP, pdFALSE, pdFALSE, pdMS_TO_TICKS(delai_ms));
    return (bits & BIT_IP) != 0;
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

// ---- Les mises à jour OTA ----

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

// La version de l'adresse est-elle strictement plus récente que la version courante ? Les versions s'écrivent « x.y.z » (trois entiers
// positifs ou nuls séparés par des points). On compare x, puis y, puis z, comme des NOMBRES (1.10.0 est plus récente que 1.9.0).
// Une version qui n'a pas cette forme n'est jamais « plus récente » : false.
static bool version_plus_recente(const char *nouvelle, const char *courante) {
    int n[3], c[3];
    char reste;
    if (sscanf(nouvelle, "%d.%d.%d%c", &n[0], &n[1], &n[2], &reste) != 3 || sscanf(courante, "%d.%d.%d%c", &c[0], &c[1], &c[2], &reste) != 3) {
        return false;
    }
    for (int i = 0; i < 3; i++) {
        if (n[i] < 0 || c[i] < 0) {
            return false;
        }
        if (n[i] != c[i]) {
            return n[i] > c[i];
        }
    }
    return false;  // identique : pas de mise à jour
}

// Traite une demande de mise à jour (appelée par app_main, jamais par le gestionnaire MQTT).
static void mettre_a_jour(const char *url) {
    if (strncmp(url, "https://", 8) != 0) {
        ESP_LOGW(TAG_OTA, "mise à jour refusée : %s n'est pas une adresse https://", url);
        return;
    }
    char version[32];
    const char *courante = esp_app_get_description()->version;
    if (!version_depuis_url(url, version, sizeof(version))) {
        ESP_LOGW(TAG_OTA, "mise à jour refusée : pas de version dans l'adresse %s (version courante %s)", url, courante);
        return;
    }
    if (!version_plus_recente(version, courante)) {
        ESP_LOGW(TAG_OTA, "mise à jour refusée : version proposée %s, version courante %s", version, courante);
        return;
    }
    mettre_en_securite();  // pompe éteinte pendant toute la mise à jour ; ensuite la régulation reprend d'elle-même
    ESP_LOGI(TAG_OTA, "mise à jour de %s vers %s", courante, version);
    esp_http_client_config_t http = {};
    http.url = url;
    http.cert_pem = _binary_server_cert_pem_start;  // le certificat du serveur : la vérification complète, comme pour MQTT
    esp_https_ota_config_t cfg = {};
    cfg.http_config = &http;
    esp_err_t err = esp_https_ota(&cfg);
    if (err != ESP_OK) {
        ESP_LOGE(TAG_OTA, "mise à jour échouée : %s", esp_err_to_name(err));
        return;
    }
    ESP_LOGI(TAG_OTA, "mise à jour réussie : version %s, redémarrage", version);
    esp_restart();
}

// ---- L'auto-test de la nouvelle image : valider ou revenir en arrière ----

// L'image qui tourne est-elle encore à confirmer ? Oui si son état est ESP_OTA_IMG_PENDING_VERIFY.
static bool image_a_confirmer(void) {
    esp_ota_img_states_t etat_image;
    esp_err_t err = esp_ota_get_state_partition(esp_ota_get_running_partition(), &etat_image);
    if (err != ESP_OK) {
        // L'appel échoue si l'image ne tourne pas depuis un emplacement OTA ou sans entrée dans otadata : rien à confirmer, ni à annuler.
        ESP_LOGI(TAG_TEST, "pas d'état d'image (%s) : pas d'auto-test", esp_err_to_name(err));
        return false;
    }
    return etat_image == ESP_OTA_IMG_PENDING_VERIFY;
}

// Ce qui reste des DELAI_AUTOTEST_MS, comptées depuis le démarrage de la carte (l'attente du Wi-Fi en a déjà consommé une partie).
static int delai_restant_ms(void) {
    int reste = DELAI_AUTOTEST_MS - (int)(esp_timer_get_time() / 1000);  // esp_timer_get_time : microsecondes depuis le démarrage
    return reste > 0 ? reste : 0;
}

// Le capteur est lisible : lecture sans erreur et valeur brute dans [RAW_MIN_OK, RAW_MAX_OK].
static bool capteur_lisible(void) {
    int raw = lire_brut();
    if (raw < 0) {
        ESP_LOGW(TAG_TEST, "auto-test : lecture du capteur impossible");
        return false;
    }
    if (raw < RAW_MIN_OK || raw > RAW_MAX_OK) {
        ESP_LOGW(TAG_TEST, "auto-test : valeur brute %d hors de [%d, %d]", raw, RAW_MIN_OK, RAW_MAX_OK);
        return false;
    }
    return true;
}

// L'auto-test : capteur lisible ET MQTT connecté, au plus DELAI_AUTOTEST_MS après le démarrage.
static bool autotest_reussi(void) {
    if (!capteur_lisible()) {
        return false;
    }
    EventBits_t bits = xEventGroupWaitBits(groupe_liaison, BIT_CONNECTE, pdFALSE, pdFALSE, pdMS_TO_TICKS(delai_restant_ms()));
    if ((bits & BIT_CONNECTE) == 0) {
        ESP_LOGW(TAG_TEST, "auto-test : MQTT non connecté après %d ms", DELAI_AUTOTEST_MS);
        return false;
    }
    return true;
}

// Conclure : auto-test réussi, confirmer l'image ; échoué, journaliser la cause, pompe éteinte, revenir à la version précédente.
// Jamais les deux appels.
static void conclure_autotest(bool reussi) {
    if (reussi) {
        esp_err_t err = esp_ota_mark_app_valid_cancel_rollback();
        if (err != ESP_OK) {
            ESP_LOGE(TAG_TEST, "confirmation de l'image impossible : %s", esp_err_to_name(err));
        } else {
            ESP_LOGI(TAG_TEST, "auto-test réussi : image confirmée");
        }
        return;
    }
    pompe(false);
    ESP_LOGE(TAG_TEST, "auto-test échoué : retour à la version précédente");
    esp_err_t err = esp_ota_mark_app_invalid_rollback_and_reboot();  // ne revient pas si le retour arrière réussit
    ESP_LOGE(TAG_TEST, "retour arrière impossible : %s", esp_err_to_name(err));
}

// Le gestionnaire des événements MQTT (tâche mqtt_task, il ne bloque jamais).
static void gestionnaire_mqtt(void *arg, esp_event_base_t base, int32_t id, void *data) {
    esp_mqtt_event_handle_t ev = (esp_mqtt_event_handle_t)data;
    switch ((esp_mqtt_event_id_t)id) {
    case MQTT_EVENT_CONNECTED:
        liaison = true;
        xEventGroupSetBits(groupe_liaison, BIT_CONNECTE);
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
        xEventGroupClearBits(groupe_liaison, BIT_CONNECTE);
        break;
    case MQTT_EVENT_DATA:
        if (ev->topic_len == (int)strlen(TOPIC_COMMANDE) && strncmp(ev->topic, TOPIC_COMMANDE, ev->topic_len) == 0) {
            traiter_commande(ev->data, ev->data_len);
            if (url_dans_commande(ev->data, ev->data_len)) {  // ne rien télécharger ici : lever le drapeau, app_main s'en charge
                xEventGroupSetBits(groupe_liaison, BIT_OTA);
            }
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
    groupe_liaison = xEventGroupCreate();
    haut = charger_consigne();  // la consigne enregistrée, relue avant toute régulation
    if (!wifi_connecter(DELAI_AUTOTEST_MS)) {
        ESP_LOGW(TAG, "pas d'adresse IP après %d ms : la suite continue sans réseau", DELAI_AUTOTEST_MS);
    }
    ESP_LOGI(TAG, "démarrage, version %s", esp_app_get_description()->version);
    if (charger_identifiants()) {
        demarrer_mqtt();
    } else {
        ESP_LOGE(TAG, "pas d'identifiants en NVS : MQTT n'est pas démarré, la pompe reste éteinte");
    }
    if (image_a_confirmer()) {
        conclure_autotest(autotest_reussi());
    }
    for (int tour = 0;; tour++) {
        EventBits_t bits = xEventGroupWaitBits(groupe_liaison, BIT_OTA, pdTRUE, pdFALSE, pdMS_TO_TICKS(PAS_MS));
        if (bits & BIT_OTA) {
            char url[sizeof(url_ota)];
            strcpy(url, url_ota);
            mettre_a_jour(url);
            ota_demandee = false;  // la prochaine commande est acceptée
        }
        reguler();
        if (tour % TOURS_TELEMETRIE == 0) {
            publier_telemetrie();
        }
    }
}
EOF
