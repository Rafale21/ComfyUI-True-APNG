# Validation de la version 1.8.2

Contrôles réalisés le 14 novembre 2026, avec Python 3.12 et Pillow 13.

## Tests automatisés

**82 tests Python réussis**, ainsi que les tests JavaScript de l’adaptateur d’import avec :

```bash
python -m unittest discover -s tests -v
```

Ils couvrent notamment :

- L'enregistrement et la relecture des pixels RGB et RGBA sans perte.
- L'ordre des images et la conservation des images consécutives identiques.
- La transparence sans traînées entre images.
- Les FPS entiers et rationnels, dont `30000/1001` et `60000/1001`.
- Les nombres de lectures infini et finis.
- Les différents niveaux de compression et les images découpées en plusieurs blocs PNG.
- La détection des fichiers tronqués, CRC incorrects et séquences APNG invalides.
- Les deux interfaces de nœuds, leurs entrées/sorties et leur résultat de prévisualisation.
- Le choix automatique ou manuel des FPS du nœud vidéo.
- Le redimensionnement avec conservation des proportions et sans agrandissement.
- Les masques fixes ou animés et leur combinaison avec un canal alpha existant.
- Le stockage du workflow, sa désactivation locale et le respect de `--disable-metadata`.
- L'absence d'écrasement des exports précédents.
- Le nettoyage des fichiers incomplets après erreur, interruption ou échec de vérification.

## Contrôles supplémentaires du réglage quality

- À `100`, le fichier exporté est identique octet par octet au réglage par défaut.
- À `25`, le test sur une séquence RGBA bruitée produit un fichier plus petit,
  avec un nombre de niveaux RGB réduit et un canal alpha identique à l'original.
- Les FPS, le nombre d'images et les répétitions sont conservés.
- La conversion des mêmes pixels reste identique d'une image à l'autre.
- L'option fonctionne aussi sur l'entrée VIDEO ; les valeurs invalides sont rejetées.

## Lecture par un second décodeur

Lors de la validation initiale de l’encodeur (inchangé en 1.1), les animations ont aussi été décodées avec **FFmpeg**, indépendamment de Pillow.
Les octets RGBA de toutes les images décodées ont été comparés aux images sources :

| Cas | Résultat |
| --- | --- |
| Exemple de 45 images, 256 × 256, 15 FPS | Toutes les images reconnues ; pixels identiques aux sources. |
| Séquence RGBA avec transparence partielle et images répétées, à 30000/1001 FPS | Toutes les images conservées ; pixels RGBA identiques ; cadence reconnue. |
| MP4 fourni pour le workflow d'exemple | 45 images, 256 × 256, 15 FPS et durée 3 secondes confirmées avec FFprobe. |

L'outil `check_apng.py` confirme également que `test_animation.apng` est valide :
45 images, 256 × 256, 15 FPS, 3 secondes, boucle infinie.

Les fichiers Python ont été compilés et le JSON du workflow d'exemple a été contrôlé.

## Limite de ces contrôles

L'hôte ComfyUI et PyTorch ne sont pas installés dans l'environnement de validation.
Les tests des nœuds utilisent donc une simulation minimale de leurs services
(dossiers de sortie, métadonnées, progression, interruption et protocole de tenseurs).
L'extension s'appuie sur l'API V1 documentée de ComfyUI et le protocole VIDEO
`get_components()`, mais le chargement du workflow et l'affichage de l'aperçu
restent à essayer dans une installation ComfyUI réelle.

## Traductions en 1.2

Les six fichiers de traduction JSON ont été chargés et contrôlés : deux nœuds par langue, tous les champs et les trois sorties présents. Les infobulles anglaises du backend correspondent aux traductions anglaises. Les identifiants et paramètres des workflows sont inchangés. L’affichage natif des traductions reste à vérifier dans une installation ComfyUI réelle.

## Redimensionnement en 1.3

Les sept filtres ont été testés sur des exports RGB et RGBA, avec vérification
des dimensions et de la conservation du nombre d’images. Le défaut Lanczos
reproduit les pixels de la version précédente. Sur un damier synthétique à
haute fréquence réduit de 128 à 8 pixels, BOX et le mode progressif produisent
un gris moyen plutôt qu’un motif parasite. Un sujet rouge sur un fond blanc
invisible permet de vérifier que les pixels transparents ne créent pas de
franges blanches. Les valeurs invalides sont rejetées et l’entrée VIDEO
accepte aussi le filtre. Les six traductions couvrent le nouveau paramètre.
Ces tests ne garantissent pas l’absence de tout aliasing sur toute source.

## Import et optimisation en 1.4

Le lecteur PNG et le sélecteur de formats TypeScript du dépôt officiel
ComfyUI_frontend ont été récupérés et exécutés sous Node 24 avec un adaptateur
FileReader. Le sélecteur ignore une entrée image/apng. Après normalisation en
image/png par notre adaptateur, le lecteur officiel récupère le workflow dans
un nouvel export et dans le fichier utilisateur ComfyUI_00031_.apng. Les textes
Unicode français et japonais sont récupérés à l’identique dans le nouvel export.
Les tests unitaires JavaScript vérifient aussi le passage des arguments, le
contexte d’appel, l’absence de double installation, les fichiers sans workflow
et le repli après erreur. Cela ne remplace pas un essai de dépôt dans l’interface
ComfyUI complète, qui n’est pas installée ici.

Les rectangles modifiés ont été décodés avec Pillow et FFmpeg, en RGB et RGBA,
y compris les déplacements d’objets semi-transparents, les images répétées et
les changements RGB sans changement d’alpha. Tous les pixels reconstruits
correspondent aux images complètes d’origine. Un fond fixe bruité avec un petit
objet mobile montre un gain de plus de moitié dans le test synthétique.
Sur l’ancienne animation utilisateur, l’encodage plein cadre et l’optimisation
produisent tous deux 864653 octets à compression 9, sans métadonnées : aucun
gain sur cet exemple. Les 22 images sont néanmoins identiques, alpha compris.

## Tolérance et aperçu en 1.5

Des tests vérifient les seuils entiers aux niveaux 0 et 50, l’identité du mode
100 avec le défaut exact, le respect de l’alpha, la désactivation de la
tolérance sans optimisation, les valeurs invalides et le passage des paramètres
par les deux nœuds. Une séquence de 61 couleurs changeant d’un niveau par image
vérifie que l’erreur ne dépasse pas 25 niveaux : les changements cumulatifs
sont correctement repris. Une vérification supplémentaire sur 40 images avec
FFmpeg confirme une erreur RGB maximale de 19/255, l’alpha exact et le nombre
d’images conservé.

Les tests JavaScript de preview.js vérifient la création d’un élément img
(et non video), l’URL de l’APNG original sans conversion, la réutilisation du
composant, sa désactivation et son nettoyage. Les tests d’import restent valides.
La tentative de test graphique Playwright n’a pas pu aboutir : le navigateur
système ne peut pas démarrer dans cet environnement. L’aperçu et son intégration
avec les widgets de ComfyUI restent donc à confirmer dans une installation
réelle ; les tests JavaScript utilisent une simulation minimale du DOM et du nœud.

## Compression et ordre des réglages en 1.6

Les tests ajoutés vérifient le refus de la tolérance sans gain de poids, la
conservation exacte des pixels avec la recherche de compression et l’absence
d’augmentation de la taille sur les séquences de contrôle RGB et RGBA. Un test
vérifie que resize_method suit immédiatement max_side dans les deux schémas.
Les tests JavaScript de migration couvrent les nœuds Video et Images, les
sous-graphes, les anciennes versions sans sélecteur de redimensionnement et
l’absence de seconde migration lors d’un rechargement. Les tests d’import et
d’aperçu sont conservés. Le module preview.js est identique à celui de la 1.5.

Sur l’ancienne animation de transparence (22 images), sans métadonnées, à
compression 9 : la version 1.5 produit 864653 octets à précision 100 et 962788
à précision 0. La version 1.6 produit 851201 octets dans les deux cas, en
refusant les modifications avec perte sans gain suffisant. Les pixels du
mode exact ont été comparés aux sources via FFmpeg.

## Régression sur la vidéo à dégradés fournie

La vidéo fournie (512 × 512, 124 images, 24 FPS) a été décodée une seule fois
avec FFmpeg. Les quatre exports utilisent les mêmes images RGB, sans
redimensionnement, sans réduction de qualité, sans métadonnées et avec un
niveau de compression 9. Les tailles sont donc directement comparables.

| Configuration | Taille en octets | Erreur RGB maximale |
| --- | ---: | ---: |
| 1.5 disabled | 7070847 | 0/255 |
| 1.5 accuracy 0 | 16866546 | 25/255 |
| 1.6 accuracy 100 | 6919712 | 0/255 |
| 1.6 accuracy 0 | 6818948 | 25/255 |

À précision 100, les 124 images de la version 1.6 sont identiques aux images
sources. À précision 0, la version 1.6 modifie 2635976 composantes RGB contre
66545148 dans la version 1.5, avec un maximum de 25/255 dans les deux cas.
Les pixels de l’export 1.6 à précision 0 ont aussi été vérifiés avec FFmpeg :
l’erreur reste bornée et le fichier reste inférieur au témoin sans optimisation.
Ce résultat ne garantit pas le même pourcentage de réduction sur d’autres vidéos.

## Curseur et coupes en 1.7

Les nouveaux tests couvrent la coupe simultanée des deux extrémités, les coupes
uniques, les zéros, la synchronisation des masques animés, les masques fixes
2D/3D, les tranches de tenseurs et les FPS rationnels du nœud Video. Les coupes
invalides ou laissant moins de deux images sont rejetées avant création de
fichier. Le slider public démarre à une tolérance de zéro ; les valeurs hors
limites sont rejetées.

Les tests JavaScript vérifient l’inversion des anciennes précisions 0 et 100,
les anciennes versions, les sous-graphes, les graphes récents sans marqueur,
la sauvegarde du marqueur de format et l’absence de double conversion. Les
nouveaux contrôles sont couverts par les six traductions. Les composants
fonctionnels d’aperçu et d’import APNG restent inchangés.

## Échelle directe en pourcentage en 1.8

Les tests ajoutés couvrent 0 % (identité avec le mode exact), 100 % (écart RGB
complet de 255 niveaux admissible), la limite 127/128 à 50 %, la conservation
de l’alpha même à 100 %, et la compatibilité d’un seuil décimal de 1,7 % avec
l’ancien calcul. Les nœuds acceptent les décimales et refusent les valeurs hors
limites, infinies et NaN. La migration divise par 10 les valeurs de tolérance
1.7 pour conserver le même effet ; les nouveaux graphes au format 8 ne sont
pas modifiés. Les tests d’import, d’aperçu et de coupe restent valides.

## Curseur et calculs redondants en 1.8.1

Les tests vérifient le type FLOAT, display=slider, les bornes 0 et 100,
et l’arrondi au dixième sur les deux nœuds. Les tolérances de 0,1 à 0,3 %
produisent exactement les mêmes octets que le mode exact, comme auparavant,
mais sans calcul inutile de candidates identiques.

Le constructeur useFloatWidget du dépôt officiel ComfyUI_frontend a également
été exécuté sous Node avec les paramètres du curseur : il crée un widget slider
et conserve correctement les valeurs 99,9 et 100. Le rendu graphique complet
n’a pas été testé dans une installation ComfyUI, et dépend de ses réglages globaux.

Sur une mesure synthétique de cinq images RGB bruitées de 256 × 256, à
compression 9 et tolérance 0,1, les versions 1.8 et 1.8.1 produisent exactement
985084 octets identiques. Les temps mesurés étaient respectivement 0,140 et
0,068 seconde. Ce résultat indicatif ne garantit pas le même gain sur d’autres
contenus ni sur une autre machine. Les tests JavaScript d’import, d’aperçu et
de migration restent valides ; leurs composants sont inchangés.

## Curseur entier en 1.8.2

Le schéma des deux nœuds utilise INT, display=slider, min=0, max=100 et step=1.
Les tests couvrent ce contrat ; le moteur continue d’accepter les décimales
pour la compatibilité des anciens workflows et des appels Python existants.
L’encodeur et la migration des workflows ne changent pas.
Le rendu graphique complet de ComfyUI n’a pas été exécuté ici.
