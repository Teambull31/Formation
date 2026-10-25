# Réguler le niveau d'une piscine : hystérésis, délai maximal et état sûr

**Le problème concret :** une piscine perd un peu d'eau chaque jour (évaporation). Un capteur mesure son niveau, une pompe, commandée par un **relais**, la remplit. Le programme doit remplir quand le niveau est **trop bas**, s'arrêter quand il est **assez haut**, et surtout ne **jamais** laisser la pompe tourner sans fin : si le capteur est bloqué ou si la pompe ne remplit plus, une pompe oubliée finit par faire **déborder** la piscine.

Cette leçon contient toute la théorie du TP. Lisez-la dans l'ordre : les messages du contrôle vous disent quelle section relire. Elle suppose les leçons précédentes : l'ADC (TP 4 : valeur brute et pourcentage), le relais (TP 5), `vTaskDelay` et les journaux.

## La boucle de régulation : lire, décider, agir, recommencer

Un programme qui **régule** une grandeur (un niveau, une température) fait toujours la même chose, en boucle :

1. **lire** le capteur (ici le niveau) ;
2. **décider** : comparer la mesure à ce que l'on veut ;
3. **agir** sur l'actionneur (ici allumer ou éteindre la pompe) ;
4. **attendre** un moment, puis recommencer.

Le niveau change ensuite **à cause de** l'action (la pompe le fait monter), le capteur le montre à la mesure suivante, et la boucle continue : on appelle cela une **boucle fermée**. Tout le TP est cette boucle ; il reste à décider **bien** : avec quels seuils, avec quelle mémoire, et quoi faire quand quelque chose ne va pas.

Le TP simule un bassin dont la pompe est sur le **relais de la GPIO 5** (actif haut : niveau 1 = pompe en marche, comme au TP 5). Quand la pompe tourne, le niveau monte de 2,5 points de pourcentage par minute ; pompe éteinte, il baisse de 0,4 point par minute (évaporation). Ce sont les valeurs de la simulation, pas celles d'une vraie piscine.

## Du brut au pourcentage (l'étalonnage du TP 4)

Le capteur est lu avec l'ADC, exactement comme au TP 4 : **ADC1, canal 6 (GPIO 34)**, atténuation `ADC_ATTEN_DB_12`, 12 bits. Le fichier du TP fait déjà cette configuration ; si besoin, relisez la leçon 4 : on n'y revient pas ici.

La valeur brute n'est pas parlante : on la convertit en pourcentage. Ce TP reprend l'idée d'étalonnage du TP 4 (0 % à 0,5 V, 100 % à 3,0 V), qui donne ces repères : **0 % se lit 620** et **100 % se lit 3723**. La formule, **en entiers**, est :

`pct = (raw - 620) * 100 / 3103`

(3103 = 3723 - 620), puis on borne le résultat entre 0 et 100. Le fichier du TP la fournit déjà (`brut_vers_pourcent`).

Exemples, avec la division entière qui **tronque** (elle supprime les décimales, sans arrondir) :

- `raw = 2480` : (2480 - 620) × 100 / 3103 = 186000 / 3103 = 59,9 → **59 %** : sous 60, la pompe doit démarrer ;
- `raw = 2790` : 217000 / 3103 = 69,9 → **69 %** ;
- `raw = 3110` : 249000 / 3103 = 80,2 → **80 %**, ce qui **n'est pas** au-dessus de 80 ;
- `raw = 3140` : 252000 / 3103 = 81,2 → **81 %** : au-dessus de 80, la pompe doit s'arrêter.

Le niveau qui compte est donc un **entier**. Le contrôle tolère **1 point** de pourcentage sur chaque seuil, justement à cause de cette troncature.

Dans le simulateur, le niveau est projeté sur le capteur par une droite parfaite, sans bruit : c'est une simplification (un vrai capteur de niveau est bruité, voir le TP 4).

## L'hystérésis : deux seuils pour que le relais ne batte pas

La première idée est **un seul seuil** : « si le niveau est sous 70 %, la pompe tourne ; sinon, elle est arrêtée ». Regardez ce qui se passe quand le niveau touche 70 % : la pompe démarre, le niveau monte un peu, passe au-dessus de 70 %, la pompe s'arrête, l'évaporation le refait descendre sous 70 %, la pompe redémarre... Le relais **bat** (on dit aussi qu'il **claque**) : il s'allume et s'éteint sans cesse, parfois plusieurs fois par minute. Un relais est un composant mécanique qui s'use à chaque commutation, et une pompe n'aime pas être démarrée et arrêtée en permanence.

Le remède s'appelle l'**hystérésis** : **deux seuils**, un bas et un haut, et une **zone neutre** entre les deux où l'on **ne change rien**.

- sous le seuil **bas (60 %)**, la pompe **démarre** ;
- au-dessus du seuil **haut (80 %)**, la pompe **s'arrête** ;
- entre 60 % et 80 %, elle **garde son état** : si elle tournait, elle continue ; si elle était arrêtée, elle reste arrêtée.

Pour « garder son état », le programme a besoin d'une **mémoire** : la décision dépend de la mesure **et** de ce qui se passait avant. C'est le rôle de la section suivante. Avec les valeurs du TP, une fois la pompe démarrée à 60 %, elle tourne environ 8 minutes (de 60 % à 80 % à 2,5 points par minute), puis le niveau redescend lentement pendant près d'une heure avant le cycle suivant : deux commutations par cycle au lieu de centaines.

Le contrôle accepte une marge de **1 point** : la pompe peut démarrer jusqu'à 61 % et s'arrêter dès 79 %, mais pas ailleurs. Il accepte aussi **12 secondes** de réaction après le franchissement d'un seuil.

!!Avec un seul seuil, le relais claque dès que le niveau hésite autour de la limite : prévoyez toujours deux seuils et une zone où l'on ne change rien!!

## L'état de la régulation : IDLE, FILLING, ALARM

La mémoire de la régulation est une **variable d'état**, qui ne prend que quelques valeurs : un petit **automate** (on dit aussi *machine à états*). Ici trois états :

| État | Sens | Pompe |
| --- | --- | --- |
| `IDLE` | repos : on attend que le niveau soit bas | éteinte |
| `FILLING` | remplissage en cours | en marche |
| `ALARM` | un problème a été détecté | éteinte, **verrouillée** |

Un type énuméré le décrit :

```cpp
enum class Etat { IDLE, FILLING, ALARM };
Etat etat = Etat::IDLE;
```

Les **transitions** (les changements d'état) :

- `IDLE` → `FILLING` : le niveau est **sous 60 %** ; on allume la pompe ;
- `FILLING` → `IDLE` : le niveau est **au-dessus de 80 %** ; on éteint la pompe ;
- `IDLE` ou `FILLING` → `ALARM` : le délai maximal est dépassé, ou le capteur est figé (sections suivantes) ; on éteint la pompe et on écrit **une** ligne d'erreur.

Il n'y a **aucune** transition qui **sort** de `ALARM` : voir la section sur l'état sûr. Dans la boucle, on regarde d'abord l'état, puis on applique la règle de **cet** état : en `IDLE`, seule la condition « sous 60 % » compte ; en `FILLING`, seule la condition « au-dessus de 80 % » compte. C'est exactement ce qui crée la zone neutre : entre 60 % et 80 %, aucune des deux conditions n'est vraie, l'état ne change pas.

Pour avertir sans noyer le journal, on écrit un message **quand on entre** dans un état d'alarme, pas à chaque tour de boucle : l'alarme est un **état**, pas un événement répété.

!!Ne relisez pas la pompe avec gpio_get_level pour connaître son état : gardez-le dans la variable etat, comme au TP 5 (la documentation de gpio_get_level dit que la valeur lue est toujours 0 si la broche n'est pas configurée en entrée)!!

## Le délai maximal : surveiller le procédé, pas seulement le capteur

Un capteur peut mentir, ou une pompe peut ne plus remplir (filtre bouché, eau coupée, tuyau percé). Dans les deux cas, la pompe tourne **sans que le niveau monte**, et personne ne s'en aperçoit. On ajoute donc une surveillance du **procédé** physique lui-même, un **chien de garde** (*watchdog*) :

> si la pompe tourne depuis **10 minutes** sans que le niveau ait **monté**, on la coupe et on lève l'alarme.

**Ce que « monter » veut dire**, définition du TP : le niveau (entier, en %) a gagné **au moins 1 point** par rapport à un niveau de **référence**. Le programme garde deux variables : l'instant de référence et le niveau de référence. À chaque mesure, pendant `FILLING` :

1. si `niveau >= niveau_reference + 1` : le niveau monte ; on prend le niveau actuel et l'instant actuel comme **nouvelle référence** (le compte de 10 minutes repart de zéro) ;
2. sinon, si `maintenant - instant_reference >= 10 minutes` : alarme.

Au démarrage de la pompe, la référence est le niveau et l'instant du démarrage. Quand le remplissage se passe bien, le niveau gagne un point toutes les 24 secondes environ : la référence est renouvelée sans cesse et l'alarme ne se déclenche jamais. Si le capteur est bloqué ou la pompe sans effet, la référence ne change plus, et 10 minutes plus tard la pompe est coupée.

Une variante plus simple est acceptée : **10 minutes de marche au total** par démarrage, sans renouveler la référence. Elle convient ici, car un remplissage normal dure environ 8 minutes ; mais il faut alors **repartir de zéro à chaque démarrage** de la pompe.

Pourquoi 10 minutes ? C'est le **délai maximal de remplissage** : un remplissage normal prend 8 minutes, donc 10 minutes laissent une marge ; au-delà, il se passe quelque chose d'anormal. Un délai trop court (5 minutes, par exemple) coupe parfois pour rien ; trop long (15 minutes), la piscine déborde avant que l'on réagisse. Le contrôle attend la coupure **entre 9 min 30 s et 10 min 15 s** après le démarrage de la pompe.

!!Une alarme à 10 minutes de marche cumulée sur toute la durée du programme finit par couper à tort : le délai se compte depuis le démarrage de CE remplissage!!

## Le capteur figé

Le délai maximal ne voit rien dans un cas : le capteur bloqué **pendant que la pompe est éteinte**. Le programme croit que le niveau est à 70 %, il ne démarre jamais la pompe, et la piscine se vide sans que personne le sache. D'où une seconde surveillance : le **capteur figé**.

Définition du TP : le capteur est **figé** quand sa **valeur brute** (celle de l'ADC, avant la conversion en pourcentage) est **exactement la même** à chaque lecture pendant **10 minutes** de suite. Le programme garde la dernière valeur brute et l'instant où elle a changé pour la dernière fois ; à chaque mesure, si elle diffère de la précédente, on met à jour les deux ; si `maintenant - instant_du_dernier_changement >= 10 minutes`, alarme.

Pourquoi la valeur **brute** ? Le pourcentage est entier : il reste identique pendant plusieurs minutes même quand le capteur fonctionne (le niveau baisse de 0,4 point par minute). La valeur brute, plus fine, change environ toutes les 5 secondes même à l'arrêt. **Dans le simulateur**, le capteur n'a aucun bruit : « identique » est exact. **Sur du vrai matériel**, un capteur bruité ne renvoie presque jamais deux fois la même valeur, même bloqué : on juge alors que la valeur « varie de moins de quelques unités » sur la fenêtre. Ce n'est pas le cas dans ce TP.

Les deux surveillances se **complètent** : le délai maximal attrape une pompe sans effet (capteur sain, niveau qui ne monte pas) ; le capteur figé attrape un capteur bloqué, **même pompe éteinte**. Le contrôle les distingue par des situations différentes : un capteur figé à 70 % pompe arrêtée, et une pompe presque sans effet dont le niveau lu bouge à peine mais bouge.

!!Sans détection du capteur figé, un capteur bloqué à 70 % laisse la pompe éteinte pour toujours et la piscine se vider sans alarme!!

## L'état sûr : pompe éteinte au démarrage, sur alarme, à la fin

Une régulation doit savoir ce qu'elle fait quand tout va mal. On définit un **état sûr** : celui où le procédé ne peut pas faire de dégât. Ici : **la pompe est éteinte** (une piscine un peu trop basse est un petit problème ; une piscine qui déborde en est un grand). Le programme met la pompe dans cet état à trois moments :

1. **Au démarrage, avant la première lecture** : juste après avoir configuré la GPIO 5 en sortie, on écrit `gpio_set_level(POMPE_GPIO, 0)`. Le contrôle exige que le **premier** niveau écrit sur la broche soit 0. Le TP 5 faisait déjà ainsi.
2. **Sur alarme** : on **coupe la pompe d'abord**, puis on change d'état et on écrit le message. Un `ESP_LOGE` n'écrit qu'une ligne de journal : la documentation d'ESP-IDF le décrit comme une macro qui écrit au niveau « erreur », rien de plus. **Il ne coupe rien** : c'est à vous d'éteindre la pompe.
3. **À la fin**, quel que soit le scénario : le contrôle regarde l'état de la broche à la fin de la simulation ; elle doit être éteinte.

**Après une alarme, la pompe reste éteinte jusqu'au redémarrage de la carte** : l'état `ALARM` est **verrouillé**, il n'existe aucune transition pour en sortir. Même si le capteur se remet à répondre normalement, un humain doit d'abord regarder. Le contrôle impose cette règle : une pompe rallumée après l'alarme est refusée. Dans la boucle, l'état `ALARM` ne fait qu'une chose : remettre la pompe à 0, par précaution.

**Une précision sur la GPIO 5.** La documentation d'ESP-IDF indique que **GPIO5 est une broche de strapping** : l'ESP32 lit son niveau au démarrage pour se configurer (la fiche technique précise le rôle de chaque broche de strapping). Elle ne donne **pas** le niveau d'une sortie pendant ou juste après le démarrage, et recommande de ne pas se fier aux valeurs par défaut du manuel de référence, que le chargeur d'amorçage ou le code de démarrage peuvent modifier. Le TP utilise la GPIO 5 parce que c'est le choix du sujet ; sur une vraie carte, choisissez plutôt une broche sans rôle particulier au démarrage, ou lisez la fiche technique avant de câbler un relais de pompe dessus.

**Sécurité électrique.** Un relais de pompe commute souvent le **secteur** (230 V) : confiez le câblage à une personne qualifiée, avec un module relais prévu pour cette tension et cette charge ; ce cours ne parle que du programme. Un relais de pompe doit être câblé de façon à être **éteint par défaut**, sans signal. Et **le logiciel seul ne suffit jamais** : une vraie installation a aussi une **sécurité matérielle**, par exemple un **interrupteur à flotteur** qui coupe la pompe au niveau haut, ou un arrêt mécanique, qui fonctionnent même si le programme plante.

!!Un programme qui plante, une carte qui redémarre ou un fil coupé laissent la pompe dans un état imprévisible : sans flotteur ou arrêt mécanique, le logiciel seul ne protège pas la piscine!!

## Choisir la période d'échantillonnage

La **période d'échantillonnage** est le temps entre deux lectures du capteur. Pour la choisir, comparez-la à la vitesse du procédé : le niveau monte de 2,5 points par minute, soit 0,4 point en 10 secondes. Lire toutes les 5 secondes suffit largement. Trop lent (20 secondes, ou une minute), on dépasse le seuil de plusieurs points avant de réagir : le contrôle exige **une lecture au moins toutes les 10 secondes**. Trop rapide (toutes les 10 ms), on lit pour rien, on use le processeur, et la trace du simulateur (limitée à environ 12 Mo pour ce TP : jusqu'à environ 16 lectures par seconde pendant 2 heures y tiennent) déborde si vous journalisez chaque mesure ou lisez sans pause.

Le TP prend **5 secondes**. Toute période entre 1 et 10 secondes convient : le contrôle l'accepte, que vous lisiez une fois ou plusieurs fois par tour. **Ne journalisez pas chaque mesure** : sur 2 heures, cela fait des milliers de lignes ; écrivez seulement les changements d'état (démarrage, arrêt, alarme).

## Mesurer le temps avec esp_timer_get_time

Pour compter 10 minutes, il faut une horloge. ESP-IDF fournit `esp_timer_get_time()` (en-tête `esp_timer.h`) :

```cpp
int64_t esp_timer_get_time(void);
```

D'après la documentation, elle renvoie le temps écoulé **en microsecondes** depuis l'initialisation du minuteur système, un peu avant `app_main` (c'est donc, pour nous, le temps depuis le démarrage) ; elle est rapide, sans verrou, et utilisable depuis une tâche. Le résultat est un entier **64 bits** : divisez par 1000 pour des millisecondes, `esp_timer_get_time() / 1000`. Dix minutes valent `10 * 60 * 1000` = 600000 ms.

**Comptez le temps réel, pas des tours de boucle.** Écrire « 120 tours de 5 secondes » semble équivalent, mais chaque tour dure un peu plus que son attente (le travail du tour s'y ajoute) : le compte dérive. Comparez plutôt `maintenant_ms() - instant_reference` à la durée voulue, avec des entiers 64 bits (`int64_t`) pour ne jamais déborder.

Dans le simulateur, le temps est **virtuel** : il n'avance que pendant `vTaskDelay`, et deux heures de simulation s'exécutent en moins d'une seconde réelle.

## Un exemple pas à pas : un chauffe-eau

Ce n'est pas le TP, c'est un cas voisin pour s'entraîner. Un chauffe-eau a une résistance commandée par un relais. Règle : **chauffer sous 50 °C**, **arrêter au-dessus de 60 °C**, et couper avec alarme si la résistance chauffe depuis **2 heures** sans que la température gagne **2 °C**.

- Les états : `ARRET`, `CHAUFFE`, `ALARME`.
- Température 48 °C, état `ARRET` : sous 50 → on passe en `CHAUFFE`, relais allumé, référence = (48 °C, maintenant).
- Température 53 °C, état `CHAUFFE` : entre 50 et 60, on ne change rien ; la température a gagné plus de 2 °C depuis la référence : nouvelle référence (53 °C, maintenant).
- Température 61 °C, état `CHAUFFE` : au-dessus de 60 → relais éteint, état `ARRET`.
- Température 55 °C, état `ARRET` : entre 50 et 60, on ne change rien : le relais reste éteint.
- 2 heures de chauffe sans gagner 2 °C (résistance entartrée, thermomètre décollé) : relais éteint, état `ALARME`, une ligne `ESP_LOGE`, et plus rien jusqu'au redémarrage.

```cpp
if (etat == Etat::ARRET) {
    if (temperature < 50) {
        etat = Etat::CHAUFFE;
        ref_temp = temperature;
        ref_ms = maintenant_ms();
        relais(true);
    }
} else if (etat == Etat::CHAUFFE) {
    if (temperature > 60) {
        relais(false);
        etat = Etat::ARRET;
    } else if (temperature >= ref_temp + 2) {
        ref_temp = temperature;                     // ça chauffe : on repart de zéro
        ref_ms = maintenant_ms();
    } else if (maintenant_ms() - ref_ms >= 2LL * 60 * 60 * 1000) {
        relais(false);                              // d'abord couper
        etat = Etat::ALARME;
        ESP_LOGE("chauffe", "ALARME : 2 h sans hausse de température");
    }
}
```

Vous retrouvez les deux seuils, la mémoire dans l'état, la référence qui repart quand ça monte, la coupure avant le message.

## Ce que le simulateur simplifie

- Le bassin est un **modèle linéaire** : remplissage de 2,5 points par minute pompe allumée, évaporation de 0,4 point par minute pompe éteinte, niveau borné entre 0 et 100. Une vraie piscine est plus lente et moins régulière.
- Le capteur est **parfait** : la valeur brute suit exactement le niveau, sans bruit. Un capteur « bloqué » garde exactement la dernière valeur.
- Le relais est un simple niveau de broche : on observe ses changements, il ne s'use pas et ne chauffe pas. Le simulateur ne dit rien de l'état de la broche au démarrage d'une vraie puce.
- `ESP_LOGE` écrit seulement une ligne dans la trace.
- Le temps est virtuel et n'avance que pendant `vTaskDelay`.
- Le simulateur ne modélise pas la sécurité matérielle (flotteur) : ne la remplacez pas par du logiciel dans une vraie installation.

## Le programme du TP en un coup d'œil

```text
app_main :
  ADC configuré (fourni)
  1. configurer la GPIO 5 en sortie, puis pompe(false)      (état sûr, avant la première lecture)
  boucle sans fin, toutes les 5 s :
     lire le brut ; si la lecture échoue : alarme
     si etat == ALARM : pompe(false), rien d'autre
     sinon : convertir en %, mettre à jour « valeur brute inchangée depuis »
        a. brut identique depuis 10 min            -> alarme (capteur figé)
        b. IDLE et niveau < 60                     -> pompe(true), référence, FILLING
        c. FILLING et niveau > 80                  -> pompe(false), IDLE
        d. FILLING et niveau >= référence + 1      -> nouvelle référence
        e. FILLING et 10 min sans hausse           -> alarme (délai maximal)
  alarme(raison) : pompe(false), etat = ALARM, UN ESP_LOGE de tag « pool »
```

Le contrôle fait tourner le programme **quatre fois** :

- **a, cycle normal de 2 heures** : départ à 72 % (zone neutre : la pompe doit rester éteinte), évaporation jusqu'à 60 % (démarrage vers 30 min), remplissage jusqu'à 80 %, deux cycles complets, pompe éteinte à la fin, **aucune alarme** ;
- **b, capteur bloqué à 40 % pendant 15 minutes** : la pompe démarre ; elle doit être coupée **10 minutes** après (9 min 30 s à 10 min 15 s), avec **une** alarme `ESP_LOGE` de tag `pool`, puis rester éteinte jusqu'à la fin (30 minutes), même quand le capteur revient ;
- **c, capteur figé à 70 %, pompe arrêtée** : une alarme à 10 minutes, pompe jamais allumée ;
- **d, capteur sain, pompe presque sans effet** : coupure et alarme 10 minutes après le démarrage de la pompe.

## Pièges

!!La pompe doit être éteinte à la fin de chaque scénario, y compris après une alarme : coupez toujours avant de changer d'état ou d'écrire le message!!

!!Un ESP_LOGE ne coupe rien : une alarme qui se contente de journaliser laisse la pompe tourner jusqu'au débordement!!

!!Une alarme écrite à chaque tour de boucle noie le journal : écrivez UNE ligne en entrant dans l'état ALARM, puis ne touchez plus qu'à la pompe!!

!!Comptez le temps avec esp_timer_get_time, pas en comptant des tours de boucle, et repartez de zéro à chaque démarrage de la pompe!!

## À retenir

- Une **régulation** est une boucle : **lire, décider, agir, attendre**.
- L'**hystérésis** : deux seuils (**60 %** et **80 %**) et une zone neutre où l'on garde l'état ; un seul seuil fait **battre** le relais.
- L'état de la régulation est une variable : **IDLE, FILLING, ALARM**. `ALARM` est **verrouillé** jusqu'au redémarrage.
- **Délai maximal** : pompe en marche depuis **10 minutes** sans que le niveau gagne **1 point** : couper et alarmer. **Capteur figé** : valeur brute identique pendant 10 minutes : alarme. Les deux se complètent.
- **État sûr** : pompe éteinte au démarrage (avant la première lecture), sur alarme (coupée **avant** le message) et à la fin. `ESP_LOGE` ne coupe rien.
- Une pompe se commande par un relais **éteint par défaut**, et **le logiciel seul ne suffit pas** : prévoir un flotteur ou un arrêt mécanique. La GPIO 5 est une broche de strapping : vérifiez la fiche technique avant de câbler.
- En entiers : `pct = (raw - 620) * 100 / 3103`, bornée entre 0 et 100.
- Le temps se mesure avec `esp_timer_get_time() / 1000` (millisecondes, `int64_t`), jamais en comptant des tours de boucle.
- La période d'échantillonnage (ici 5 s, au plus 10 s) se règle sur la vitesse du procédé ; on ne journalise pas chaque mesure.
