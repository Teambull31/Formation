# Lire un capteur analogique avec l'ADC

**Le problème concret :** un capteur de niveau (par exemple une sonde dans un bassin) envoie à l'ESP32 une **tension** qui varie en continu ; le programme doit la mesurer, la transformer en **pourcentage** et écrire `level=NN%` chaque seconde, malgré le bruit électrique qui fait trembler la mesure.

Cette leçon contient toute la théorie du TP. Lisez-la dans l'ordre : les messages du contrôle vous disent quelle section relire. Elle suppose les leçons précédentes (tâches, `vTaskDelay`, journaux avec `ESP_LOGI`).

## Analogique, numérique et ADC

Une broche d'entrée comme celle du bouton (leçon 2) ne connaît que **deux** états : 0 ou 1. Un capteur, lui, donne une valeur qui change **progressivement** : 0,8 V, puis 0,81 V, puis 0,83 V... On dit que le signal est **analogique**.

Un microcontrôleur ne manipule que des nombres entiers. Le composant qui transforme une tension en nombre s'appelle un **convertisseur analogique-numérique**, en anglais **ADC** (*Analog to Digital Converter*). L'ESP32 en contient deux, nommés **ADC1** et **ADC2**. Chacun mesure la tension présente sur certaines broches (voir la section sur les canaux plus bas) et répond par un nombre : la **valeur brute** (*raw*).

## Résolution : 12 bits et valeurs brutes de 0 à 4095

La **résolution** d'un ADC est le nombre de bits du résultat. Avec 12 bits, on peut écrire 2^12 = **4096 valeurs différentes**, de **0 à 4095**. Le 0 correspond à la tension la plus basse que l'ADC sait mesurer, le 4095 à la plus haute. Entre les deux, la valeur brute est **proportionnelle** à la tension.

La documentation d'ESP-IDF donne la relation générale (pour un ADC non étalonné) : `Vout = Dout × Vmax / Dmax`, où `Dout` est la valeur brute, `Vmax` la tension maximale mesurable et `Dmax` vaut 2 puissance le nombre de bits. Dans ce TP nous prenons `Vmax = 3,3 V` et la valeur brute maximale 4095 : la documentation écrit `Dmax = 2^bits`, soit 4096, l'écart est de 0,02 %, sans importance ici.

Le réglage de la résolution se donne en choisissant `ADC_BITWIDTH_12`. La constante `ADC_BITWIDTH_DEFAULT` signifie « la largeur maximale prise en charge » : 12 bits sur l'ESP32 (il existe aussi 9, 10 et 11 bits). Le TP écrit `ADC_BITWIDTH_12` pour que ce soit explicite.

## Du capteur à la tension : le pont diviseur

Beaucoup de capteurs ne produisent pas directement une tension : une thermistance (température), une photorésistance (lumière) ou un potentiomètre changent leur **résistance**. Pour mesurer une résistance avec un ADC, on la monte avec une résistance fixe en **pont diviseur** entre l'alimentation (3,3 V) et la masse. La tension au point de jonction vaut :

`Vsortie = Valimentation × R2 / (R1 + R2)`

Quand la résistance du capteur change, `Vsortie` change, et c'est cette tension que l'ADC lit. Dans le TP, on suppose le montage déjà fait : le capteur délivre une tension entre 0 et 3,3 V sur la broche **GPIO 34** et vous n'avez qu'à la lire.

Un pont diviseur sert aussi à **réduire** une tension trop forte. Exemple : une batterie qui monte à 4,2 V ne doit pas être branchée telle quelle sur une entrée limitée à 3,3 V ; deux résistances égales divisent la tension par deux.

## L'atténuation et la plage de mesure

L'ADC de l'ESP32 compare la tension d'entrée à une référence interne. Pour pouvoir mesurer des tensions plus grandes que cette référence, on **atténue** l'entrée : plus l'atténuation est forte, plus la **plage de mesure** s'étend. ESP-IDF propose quatre réglages (type `adc_atten_t`) :

| Constante | Sens (d'après la documentation) |
| --- | --- |
| `ADC_ATTEN_DB_0` | aucune atténuation |
| `ADC_ATTEN_DB_2_5` | la plage s'étend d'environ 2,5 dB |
| `ADC_ATTEN_DB_6` | la plage s'étend d'environ 6 dB |
| `ADC_ATTEN_DB_12` | la plage s'étend d'environ 12 dB (la plus large) |

`ADC_ATTEN_DB_11` existe encore mais la documentation le déclare **obsolète** : il se comporte comme `ADC_ATTEN_DB_12`. Cette leçon ne donne **pas** les tensions exactes mesurables avec chaque réglage : elles dépendent de la puce et se lisent dans sa fiche technique. Retenez la règle : pour un signal qui monte jusqu'à environ 3 V, on choisit le réglage le plus atténué, `ADC_ATTEN_DB_12`, ce que fait le TP.

## L'étalonnage : du brut au pourcentage

La valeur brute n'est pas parlante. Trois conversions, dans l'ordre :

1. **Brut vers millivolts** : `mv = raw × 3300 / 4095` (le simulateur suppose 0 à 3300 mV pour 0 à 4095).
2. **Millivolts vers pourcentage**, selon la **droite d'étalonnage** du capteur : **0 %** correspond à **0,5 V** (500 mV) et **100 %** à **3,0 V** (3000 mV). Le capteur couvre donc 2500 mV : `pct = (mv - 500) × 100 / 2500`.
3. **Borner** le résultat entre 0 et 100 : sous 0,5 V le niveau est 0 %, au-dessus de 3,0 V il est 100 %. On dit qu'on **écrête** (*clamp*) : `if (pct < 0) pct = 0; if (pct > 100) pct = 100;`.

Repères pour le TP : 1 point de pourcentage vaut 25 mV, soit environ **31** unités de valeur brute ; 0 % se lit vers 620 et 100 % vers 3723.

Le calcul peut se faire en flottants (`float`, plus simple à lire) ou en entiers (plus léger, mais la division entière **tronque** : 99,9 devient 99). Pour arrondir au plus proche, on ajoute 0,5 avant de convertir en entier : `(int)(pct + 0.5f)`. Au TP, l'écart toléré est de ± 2 points, donc une troncature seule passe, mais l'arrondi laisse plus de marge.

**Et sur la vraie puce ?** La documentation d'ESP-IDF explique que la tension de référence de l'ADC de l'ESP32 vaut **1100 mV** « par conception », mais que la vraie valeur varie de **1000 à 1200 mV** d'une puce à l'autre, et elle fournit un **pilote d'étalonnage** (`esp_adc/adc_cali.h`, par exemple `adc_cali_create_scheme_line_fitting` puis `adc_cali_raw_to_voltage`) pour corriger cet écart et obtenir des millivolts plus exacts. Le simulateur de ce TP **n'a pas** ce pilote : il suppose une droite parfaite, `raw = tension / 3,3 × 4095`. C'est une **simplification** de la réalité, pour que le calcul reste simple. Ne la prenez pas pour une propriété de la vraie puce.

## Un exemple pas à pas : la tension d'une batterie

Ce n'est pas le TP, c'est un cas voisin pour s'entraîner. On mesure une batterie dont la tension va de 3,0 V à 4,2 V. Par convention de cet exemple, 3,0 V vaut 0 % et 4,2 V vaut 100 %. Deux résistances égales divisent la tension par 2 avant l'ADC : l'ADC voit donc entre 1,5 V et 2,1 V.

Supposons une valeur brute de **2600** :

1. Millivolts vus par l'ADC : `2600 × 3300 / 4095 ≈ 2095 mV`.
2. Tension de la batterie : `2095 × 2 ≈ 4190 mV` (on remonte la division par 2).
3. Pourcentage : `(4190 - 3000) × 100 / 1200 ≈ 99,2`, soit **99 %** une fois arrondi.

Autres valeurs brutes : **2000** donne 1612 mV, soit 3223 mV pour la batterie et `(3223 - 3000) × 100 / 1200 ≈ 18,6`, donc **19 %**. **1000** donne 806 mV, soit 1612 mV pour la batterie : le calcul donnerait un nombre négatif, qu'on écrête à **0 %**. Un résultat supérieur à 100 % se ramène de la même façon à **100 %**.

Pour la mise en forme, on écrirait `ESP_LOGI(TAG, "batterie=%d%%", pct)` : dans le texte de `ESP_LOGI`, comme pour `printf`, le signe pourcent s'écrit **deux fois** (`%%`) pour s'afficher une fois.

## Le bruit et la moyenne de 8 échantillons

Sur une vraie carte, la valeur brute **tremble** même si la tension ne bouge pas : ce parasite s'appelle le **bruit**. La documentation d'ESP-IDF le dit : l'ADC de l'ESP32 est sensible au bruit, ce qui peut donner de grands écarts entre les lectures ; elle conseille un petit condensateur de découplage (par exemple 100 nF) entre l'entrée et la masse, et le **multi-échantillonnage** (*multisampling*), c'est-à-dire **moyenner plusieurs lectures**.

Le principe : le bruit est tantôt positif, tantôt négatif ; en additionnant plusieurs lectures puis en divisant par leur nombre, les écarts se compensent en grande partie. Exemple avec 8 lectures brutes autour d'une vraie valeur de 2015 :

`2010, 2050, 1990, 2030, 2020, 1980, 2040, 2000`

La somme vaut 16120 et la moyenne `16120 / 8 = 2015`, alors que la lecture 2050 prise seule se serait trompée de 35 unités. Plus on moyenne de lectures, plus le résultat est stable ; en contrepartie, on met plus de temps à mesurer.

Dans le TP, le bruit vaut environ ± 75 unités, avec des pointes à ± 90, soit plus de ± 2 points : **une seule lecture** peut donc sortir de la tolérance de ± 2 points, alors que la **moyenne de 8** reste en moyenne à environ 1 point de la vraie valeur.

Deux règles de calcul : **additionnez d'abord, divisez ensuite** (`somme / nombre`), et divisez par le nombre de lectures **réussies**.

## Pourquoi une mesure par seconde ne suffit pas

Le journal ne s'écrit qu'**une fois par seconde**, mais il ne faut pas pour autant ne **mesurer** qu'une fois par seconde. Une seule lecture, c'est le bruit tel quel dans le journal : la valeur affichée saute d'une seconde à l'autre. Les deux rythmes sont indépendants : on **mesure souvent** (8 fois) et on **annonce rarement** (1 fois par seconde).

Dans le TP, chaque tour de boucle fait donc : 8 lectures espacées de 10 ms (80 ms au total), la moyenne, la conversion, **un** journal, puis une attente pour compléter la seconde : `1000 - 8 × 10 = 920 ms`. Le contrôle compte les événements de lecture `adc_read` entre deux journaux : il en faut **au moins 8**. Calculer une « moyenne » sur des valeurs inventées ou relues dans une variable ne passe donc pas.

## Pourquoi 10 ms entre deux lectures ?

C'est une particularité du **simulateur** : le temps n'y avance que pendant `vTaskDelay`, et son bruit change toutes les 10 ms. Huit lectures à la suite sans pause donneraient huit fois la même valeur, donc pas de moyenne ; le contrôle le détecte : il exige que les lectures entre deux journaux tombent à au moins 4 instants différents. La pause de 10 ms (`vTaskDelay(pdMS_TO_TICKS(10))`) rend chaque lecture indépendante.

## Les quatre étapes de l'API oneshot

ESP-IDF propose le mode « oneshot » (une lecture à la fois, à la demande) dans `esp_adc/adc_oneshot.h`. Quatre étapes :

1. **Créer l'unité** (ADC1 ou ADC2) avec `adc_oneshot_new_unit`.
2. **Configurer le canal** (atténuation et largeur) avec `adc_oneshot_config_channel`.
3. **Lire** autant de fois que nécessaire avec `adc_oneshot_read`.
4. **Libérer** l'unité avec `adc_oneshot_del_unit` quand on n'en a plus besoin (le TP ne la libère pas, il tourne sans fin).

```cpp
esp_err_t adc_oneshot_new_unit(const adc_oneshot_unit_init_cfg_t *init_config,
                               adc_oneshot_unit_handle_t *ret_unit);
esp_err_t adc_oneshot_config_channel(adc_oneshot_unit_handle_t handle, adc_channel_t channel,
                                     const adc_oneshot_chan_cfg_t *config);
esp_err_t adc_oneshot_read(adc_oneshot_unit_handle_t handle, adc_channel_t chan, int *out_raw);
esp_err_t adc_oneshot_del_unit(adc_oneshot_unit_handle_t handle);
```

| Fonction | Rôle | Retours possibles (documentation) |
| --- | --- | --- |
| `adc_oneshot_new_unit` | crée l'unité ; la **poignée** (`handle`) est écrite dans `*ret_unit` | `ESP_OK` ; `ESP_ERR_INVALID_ARG` ; `ESP_ERR_NO_MEM` ; `ESP_ERR_NOT_FOUND` (cette unité est déjà prise) ; `ESP_FAIL` |
| `adc_oneshot_config_channel` | règle l'atténuation et la largeur d'un canal | `ESP_OK` ; `ESP_ERR_INVALID_ARG` |
| `adc_oneshot_read` | lit la valeur brute, rangée dans `*out_raw` | `ESP_OK` ; `ESP_ERR_INVALID_ARG` ; `ESP_ERR_TIMEOUT` (résultat invalide) |
| `adc_oneshot_del_unit` | libère l'unité | `ESP_OK` ; `ESP_ERR_INVALID_ARG` ; `ESP_ERR_NOT_FOUND` |

Le code de l'étape 1 et 2, tel que le TP l'utilise :

```cpp
adc_oneshot_unit_handle_t adc;                       // la poignée de l'unité
adc_oneshot_unit_init_cfg_t unit_cfg = {};           // tout à zéro, sauf :
unit_cfg.unit_id = ADC_UNIT_1;                       // l'ADC1
ESP_ERROR_CHECK(adc_oneshot_new_unit(&unit_cfg, &adc));

adc_oneshot_chan_cfg_t chan_cfg = {};
chan_cfg.atten = ADC_ATTEN_DB_12;                    // plage la plus large
chan_cfg.bitwidth = ADC_BITWIDTH_12;                 // valeurs de 0 à 4095
ESP_ERROR_CHECK(adc_oneshot_config_channel(adc, ADC_CHANNEL_6, &chan_cfg));
```

Et une lecture (étape 3) : on passe l'**adresse** d'un entier, que la fonction remplit.

```cpp
int raw = 0;
esp_err_t err = adc_oneshot_read(adc, ADC_CHANNEL_6, &raw);
if (err != ESP_OK) {
    ESP_LOGW(TAG, "lecture refusée : %s", esp_err_to_name(err));   // ne pas utiliser raw
}
```

`esp_err_to_name` renvoie le nom d'un code d'erreur sous forme de texte (par exemple `ESP_ERR_INVALID_ARG`), pratique pour un journal. Les fonctions `adc_oneshot_*` sont déclarées sûres entre tâches (sauf `adc_oneshot_del_unit`), et `adc_oneshot_read` ne doit jamais être appelée depuis une interruption.

!!Lire un canal que l'on n'a pas configuré avec adc_oneshot_config_channel ne donne pas une mesure : la lecture échoue et le contrôle ne voit aucune lecture!!

## Canaux, broches, ADC1 et ADC2

Un **canal** est une entrée de l'ADC, reliée à une broche précise. Pour l'ESP32, les fichiers d'ESP-IDF donnent par exemple : ADC1 canal 0 = GPIO 36, canal 3 = GPIO 39, canal 4 = GPIO 32, canal 5 = GPIO 33, **canal 6 = GPIO 34**, canal 7 = GPIO 35 ; ADC2 canal 0 = GPIO 4, canal 2 = GPIO 2. Notre capteur est sur `ADC_CHANNEL_6` de l'**ADC1**, c'est-à-dire le GPIO 34.

**ADC1 ou ADC2 ?** La documentation précise que l'ADC2 est **aussi utilisé par le Wi-Fi** ; elle indique que `adc_oneshot_read` gère le partage entre le pilote Wi-Fi et le pilote oneshot, et la documentation de `adc_oneshot_read` prévoit le code `ESP_ERR_TIMEOUT` (« résultat invalide »). Le plus simple, dès que le Wi-Fi entre en jeu, est de brancher les capteurs sur l'**ADC1**, comme dans ce TP. Les constantes `ADC_CHANNEL_0`, `ADC_CHANNEL_1`... sont les mêmes pour les deux unités : c'est l'**unité** choisie qui dit de quel ADC on parle.

!!Une unité ne se crée pas deux fois : un deuxième adc_oneshot_new_unit sur la même unité renvoie ESP_ERR_NOT_FOUND, car cette unité est déjà prise!!

## Ce que le simulateur simplifie

- La valeur brute vaut `tension / 3,3 × 4095`, **linéaire** et sans écart de puce à puce ; le pilote d'étalonnage n'existe pas dans le simulateur.
- La plage est la même quel que soit le réglage d'atténuation.
- Le temps n'avance que pendant `vTaskDelay` ; le bruit change toutes les 10 ms.
- Une lecture sur un canal non configuré renvoie `ESP_ERR_INVALID_ARG` et n'est pas notée dans la trace.

## Le programme du TP en un coup d'œil

```text
app_main :
  1. créer l'unité ADC1                       (adc_oneshot_new_unit)
  2. configurer le canal 6 : DB_12, 12 bits   (adc_oneshot_config_channel)
  boucle sans fin :
     3. lire_moyenne : 8 × (adc_oneshot_read + pause de 10 ms), puis la moyenne
     4. raw_vers_pourcent : brut, millivolts, pourcentage, borné de 0 à 100
     5. ESP_LOGI(TAG, "level=%d%%", pct)       (tag « niveau »)
     6. attendre 1000 - 8 × 10 = 920 ms
```

Le journal doit avoir **exactement** la forme `level=42%` (le mot `level`, le signe égal, un nombre entier, le signe pourcent), avec le tag `niveau`. Le contrôle simule **20 secondes** d'une tension qui monte lentement avec du bruit, et vérifie à chaque journal que le niveau est à ± 2 points de la vraie valeur.

!!Un journal sans la moyenne, ou une conversion qui divise simplement par 4095 ou prend 3,3 V pour 100 %, s'écarte de plus de 2 points : le message du contrôle nomme la formule qui correspond à vos valeurs!!

## Pièges

!!Diviser la valeur brute par 4095 donne un pourcentage de la plage de l'ADC, pas du capteur : le capteur ne vaut 0 % qu'à 0,5 V et 100 % qu'à 3,0 V!!

!!Dans ESP_LOGI, le signe pourcent s'écrit deux fois : level=%d%% affiche level=42%, alors que level=%d% ne s'afficherait pas correctement!!

!!Avec des entiers, multipliez avant de diviser : raw * 3300 / 4095 garde la précision, raw / 4095 * 3300 donne presque toujours 0!!

!!Ne remplacez pas les 8 lectures par une seule lecture multipliée ou recopiée : le contrôle compte les événements adc_read!!

## À retenir

- Un **ADC** transforme une tension en **valeur brute** ; sur 12 bits, de **0 à 4095**.
- Le capteur se règle avec l'**atténuation** (`ADC_ATTEN_DB_12` pour environ 3 V) et la **largeur** (`ADC_BITWIDTH_12`).
- L'**étalonnage** du TP : `mv = raw × 3300 / 4095`, puis `pct = (mv - 500) × 100 / 2500`, **borné** entre 0 et 100.
- Le **bruit** fait trembler la valeur : on **moyenne 8 lectures** espacées de 10 ms, on additionne avant de diviser.
- On **mesure souvent** et on **journalise une fois par seconde** : `level=NN%`.
- API oneshot : `adc_oneshot_new_unit`, puis `adc_oneshot_config_channel`, puis `adc_oneshot_read` ; on teste toujours le retour.
- Le simulateur est **linéaire** par simplification ; la vraie puce demande le pilote d'étalonnage `esp_adc/adc_cali.h`.
