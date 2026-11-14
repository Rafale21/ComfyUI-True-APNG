# ComfyUI True APNG — version 1.8.2

Deux nœuds pour exporter des vidéos ou des séquences d’images en véritables
fichiers APNG animés, avec transparence, redimensionnement et optimisation.

## Correctifs 1.8.2

La tolérance utilise un **curseur natif entier de 0 à 100**, par pas de 1,
comme la qualité. La couleur suit le thème de ComfyUI. Les anciens seuils
décimaux restent acceptés en interne pour préserver les workflows existants ;
les nouveaux réglages utilisent des pourcentages entiers.

Le dossier `publication/` contient un guide français de publication, un modèle
de métadonnées Registry et des notes de version anglaises. La présentation
anglaise à copier est dans `PRESENTATION_EN.md`.

L’encodeur évite les essais de tolérance sous un niveau entier de couleur,
et ne réencode pas une candidate identique à l’image exacte. Cette réduction
de calcul ne change ni les pixels ni les données exportées. Les infobulles
ont aussi été corrigées pour parler de tolérance 0 plutôt que de précision 100.

## Tolérance et coupe des images

- Le curseur indique maintenant la **tolérance** : `0` = aucune perte,
  `100` = jusqu’à 100 % d’écart RGB par canal.
- Deux compteurs, à `0` par défaut, retirent des images au début et à la fin.
- Les anciens workflows conservent leur seuil réel : une tolérance 1.7 de
  100 devient 10. Pour les versions à curseur de précision, la nouvelle valeur
  est (100 − ancienne précision) / 10. Les coupes sont conservées ou mises à
  zéro si elles n’existaient pas. Le curseur accepte les décimales pour cette
  migration. Les nouveaux exports utilisent l’échelle directe en pourcentage.

## Installation et mise à jour

1. Fermez ComfyUI.
2. Décompressez l’archive et placez le dossier `ComfyUI-True-APNG` dans
   `ComfyUI/custom_nodes/`. Pour une mise à jour, remplacez l’ancien dossier.
3. Redémarrez ComfyUI puis rechargez l’interface avec Ctrl+F5.
4. Cherchez **APNG** pour ajouter un nœud. Si un ancien nœud conserve des
   contrôles incohérents, retirez-le puis ajoutez-le de nouveau.

Pillow et NumPy sont normalement déjà présents. Si besoin, installez
`requirements.txt` avec le Python de ComfyUI. L’encodage APNG ne nécessite pas
d’installation supplémentaire de FFmpeg, de Node.js ou de npm.

## Nœuds et branchements

- **Save APNG (Video)** reçoit une sortie VIDEO native et récupère ses FPS.
  Pour un MP4, utilisez d’abord **Load Video**.
- **Save APNG (Images)** reçoit un batch IMAGE ; choisissez sa cadence en FPS.

Le type VIDEO natif est distinct d’un chemin de fichier ou de VHS_FILENAMES.
Avec VideoHelperSuite, utilisez les images en amont de Video Combine.

## Retirer les images au début et à la fin

**Images à retirer au début** (`trim_start`) et **Images à retirer à la fin**
(`trim_end`) sont des nombres d’images, pas des durées en secondes.

Exemple : début = 2, fin = 3 retire les deux premières et les trois dernières
images. Les masques par image sont coupés aux mêmes indices. Les masques fixes
restent inchangés. Les coupes précèdent le redimensionnement et l’optimisation.

La cadence ne change pas et la durée diminue. Il doit rester au moins deux
images ; sinon un message empêche la création d’un fichier incomplet.
Cette coupe est manuelle : elle peut éliminer des images répétées qui créent
une pause dans une boucle, sans fabriquer de transition entre fin et début.

## Réglages

| Réglage | Rôle |
| --- | --- |
| `filename_prefix` | Nom et sous-dossier relatifs à output. Défaut : APNG/ComfyUI. Sans extension. |
| `loop` | Lectures totales : 0 = infini, 1 = une lecture, 2 = deux lectures. |
| `trim_start`, `trim_end` | Nombre d’images à retirer à chaque extrémité, défaut 0. |
| `compress_level` | Effort de compression PNG de 0 à 9, sans modifier les pixels. Défaut 6. |
| `max_side` | 0 = résolution originale ; sinon limite le plus grand côté, sans agrandir, proportions conservées. |
| `resize_method` | Placé sous côté maximal : lanczos, lanczos_progressive, box, bicubic, bilinear, hamming ou nearest. |
| `quality` | 100 conserve les pixels 8 bits ; une valeur inférieure réduit la précision des couleurs. Alpha conservé. |
| `optimize_frames` | Recherche de rectangles modifiés et de stratégies PNG plus compactes. Activé par défaut. |
| `optimization_tolerance` | 0 = comparaison exacte ; 50 = 50 % par canal ; 100 = 100 %. Défaut 0. |
| `verify_file` | Vérifie les blocs, durées et images décodées avant publication. Activé par défaut. |
| `include_metadata` | Inclut le workflow et le prompt ; respecte aussi --disable-metadata. |
| `preview` | Aperçu APNG animé via une image sur damier, sans lecteur vidéo. Désactivable. |
| `mask` | Masque facultatif : 1 transparent, 0 opaque. Fixe ou animé, à la résolution source. |

Les trois sorties donnent le chemin du fichier, le nombre d’images exportées
après les coupes et les FPS encodés. Les fichiers vont par défaut dans
`ComfyUI/output/APNG/`. Le compteur évite d’écraser les exports existants.

## Optimisation et qualité

À tolérance 0, l’optimisation reste exacte : elle cherche une compression plus
efficace sans changer les pixels. Une tolérance supérieure autorise la
conservation de couleurs précédentes, seulement si les données compressées de
l’image sont au moins 1 % plus petites que la meilleure représentation exacte.
Sinon l’image exacte est utilisée.

Le seuil vaut `255 × tolérance / 100`. Les écarts étant entiers sur 8 bits,
ils sont arrondis vers le bas : par exemple 25/255 à 10 %, et 255/255 à 100 %.
À 100 %, toutes les différences RGB sont admissibles ; les couleurs peuvent
rester figées si l’alpha ne change pas et que cela réduit le poids. Les trois
canaux RGB doivent respecter le seuil ; l’alpha doit être exactement identique.
La comparaison se fait avec l’image effectivement reconstruite, pour éviter
une dérive cumulative. Les images répétées et les durées sont conservées.

Pour des dégradés et des images réalistes, commencez avec **quality = 100**,
**tolérance = 0**, **optimisation activée**, et éventuellement **compression 9**.
La tolérance et la qualité sont des mécanismes différents et peuvent chacun
introduire des artefacts. Le gain dépend du contenu ; le calcul peut être plus
long et conserve une image précédente en mémoire.

Pour une forte réduction, essayez lanczos_progressive ou box. Nearest convient
au pixel art, pas au lissage. Comparez les filtres à quality 100 et tolérance 0.

## Transparence, aperçu et workflow

Si ComfyUI sépare la transparence en une sortie MASK, branchez-la sur mask.
L’extension ne retire pas automatiquement les fonds. Les images RGBA sont
également acceptées ; le masque se combine avec leur alpha.

L’aperçu affiche l’APNG original sur un damier ; cliquez sur le nom du fichier
pour l’ouvrir. L’adaptateur frontend doit être activé dans ComfyUI. Les anciens
résultats en cache ne sont pas réécrits par une mise à jour.

Pour récupérer le workflow, déposez un APNG contenant les métadonnées sur une
zone vide du canvas. L’adaptateur transmet un fichier virtuel de type PNG au
lecteur de ComfyUI sans modifier l’original. Sans cet adaptateur, une copie
renommée de .apng en .png peut servir au même import. Le workflow référence
ses modèles et fichiers d’entrée ; ils ne sont pas inclus dans l’animation.

## Langues et exemples

Titres, descriptions, champs et infobulles suivent la langue de ComfyUI :
anglais, français, allemand, espagnol, italien et japonais. Les messages
techniques peuvent conserver leur langue d’origine.

Copiez `examples/test_video.mp4` dans `ComfyUI/input/` et chargez
`examples/workflow_video_apng.json`. À coupes zéro : 45 images à 15 FPS,
256 × 256, soit 3 secondes. Un APNG de test est également fourni.

## Limites et validation

L’APNG n’a pas de son et peut être plus lourd qu’un MP4. L’export est en
RGB/RGBA 8 bits, sans HDR. Le chargement VIDEO natif peut décoder tout le clip
en mémoire même si vous retirez ensuite des images. Modifier les FPS change
la vitesse, sans interpolation.

Consultez VALIDATION.md pour les tests. `check_apng.py` vérifie les variantes
APNG de cette extension. Les développeurs peuvent lancer les tests Python et
JavaScript fournis ; ces outils de développement ne sont pas requis pour utiliser
les nœuds.

Pour les clients API : le réglage public est désormais optimization_tolerance,
et remplace optimization_accuracy. Convertissez une ancienne précision avec
`tolérance = (100 − précision) / 10`. Pour des valeurs de tolérance de la 1.7,
divisez-les par 10 pour conserver le même seuil. Les workflows visuels sont
migrés automatiquement.
