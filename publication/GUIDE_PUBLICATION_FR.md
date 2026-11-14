# Publier ComfyUI True APNG — version 1.8.2

Guide vérifié avec la documentation officielle le 14 novembre 2026.
L’archive contient l’extension mise à jour et les documents à utiliser pour sa publication. Rien n’a encore été publié sur GitHub ou sur Comfy Registry.

## 1. Informations à utiliser

| Champ | Valeur proposée |
| --- | --- |
| Nom affiché | ComfyUI True APNG |
| Nom du dépôt GitHub | ComfyUI-True-APNG |
| Identifiant Registry proposé | true-apng |
| Version | 1.8.2 |
| Catégorie descriptive | Image / Animation / Export |
| Mots-clés suggérés | comfyui, custom-nodes, apng, animation, transparency, video, png |
| Présentation en anglais | PRESENTATION_EN.md, à la racine de l’extension |
| Documentation GitHub | README.md et README_FR.md |
| Notes de version en anglais | publication/RELEASE_NOTES_EN.md |
| Dépendances | Pillow>=9.1.0 ; numpy>=1.23.0 |

Description courte anglaise à copier :

> Export genuine animated APNG files from ComfyUI videos and image batches, with transparency, resizing, trimming and optimization.

`true-apng` est une proposition : sa disponibilité n’a pas été vérifiée. L’identifiant du nœud et le Publisher ID deviennent permanents après création. Le nom affiché peut ensuite changer. Aucun compte, nom d’éditeur ou dépôt n’est supposé être déjà créé.

## 2. Créer le dépôt GitHub

1. Connecte-toi à GitHub, puis crée un dépôt public nommé **ComfyUI-True-APNG**.
2. Clone ce dépôt avec GitHub Desktop (ou Git si tu l’utilises déjà).
3. Copie le **contenu** du dossier extrait `ComfyUI-True-APNG` à la racine du dépôt local. N’ajoute pas un deuxième dossier `ComfyUI-True-APNG` à l’intérieur du dépôt.
4. À la racine du dépôt, tu dois voir directement `__init__.py`, `nodes.py`, `apng_encoder.py`, `requirements.txt`, `web/`, `locales/`, `README.md` et les autres documents.
5. Choisis une licence de diffusion et ajoute son texte dans `LICENSE`. Pour une diffusion permissive, MIT est une option courante ; ce choix reste à toi. Le modèle de métadonnées n’attribue aucune licence automatiquement.
6. Enregistre les changements avec un commit, puis pousse-les sur GitHub.

Ne publie aucun modèle IA ni dossier ComfyUI complet : seul le contenu de cette extension est nécessaire. Le dépôt inclut des règles pour écarter les caches Python et les archives ZIP. Le fichier `.comfyignore` allège le paquet Registry en excluant les tests, le kit de publication et les vidéos/APNG d’exemple ; `web/` et `locales/` restent inclus.

## 3. Créer ton éditeur sur Comfy Registry

1. Ouvre https://registry.comfy.org et connecte-toi.
2. Crée un **Publisher**. Son identifiant est personnel à ton éditeur ; copie exactement le Publisher ID indiqué sur ton profil, après `@`.
3. Depuis les paramètres de ce Publisher, crée une **Registry Publishing API Key**.
4. Conserve cette clé pour l’étape de publication. Elle ne doit pas être ajoutée au dépôt et tu n’as pas besoin de me l’envoyer.

Cette clé sert à publier l’extension ; ce n’est pas une clé de consommation de modèles ou de Partner Nodes.

## 4. Compléter les métadonnées

1. Copie `publication/pyproject.toml.example` à la racine du dépôt et renomme la copie **pyproject.toml**.
2. Remplace `YOUR_GITHUB_NAME` par ton nom de compte GitHub dans les URL.
3. Remplace `YOUR_PUBLISHER_ID` par l’identifiant exact de ton Publisher.
4. Vérifie `name = "true-apng"` : change-le avant la première publication si cet identifiant est déjà pris ou si tu préfères un autre nom.
5. Garde `version = "1.8.2"` pour cette version.
6. Si tu as ajouté `LICENSE`, active la ligne `license = { file = "LICENSE" }` en retirant le `#`.
7. L’icône est facultative. Si tu en ajoutes une, utilise une URL publique et une image carrée au plus 400 × 400 pixels, conformément à la spécification du Registry.
8. Enregistre ce fichier dans Git et pousse les changements avant publication.

Le modèle fournit explicitement les dépendances : il n’est pas nécessaire de relancer `comfy node init`, qui sert à générer un nouveau fichier de métadonnées. Aucun fichier de licence n’est référencé tant qu’il n’a pas été ajouté.

## 5. Publier avec Comfy CLI sous Windows

Le chemin ci-dessous est un exemple de **copie de développement**, distincte de ton installation ComfyUI Desktop. Adapte le chemin à celui de ton dépôt. Les commandes supposent Python et Git installés sur le PC.

Dans PowerShell :

```powershell
cd "C:\Users\TON_NOM\Documents\GitHub\ComfyUI-True-APNG"
py -m venv .venv
.\.venv\Scripts\python.exe -m pip install --upgrade comfy-cli
.\.venv\Scripts\comfy.exe node publish
```

La commande demande la clé API du Publisher : colle la **Registry Publishing API Key** créée à l’étape 3. Tu n’as pas à installer une deuxième copie de ComfyUI ou ses modèles pour publier ce paquet. Le CLI est installé dans un environnement local au dépôt.

Le Registry utilise les fichiers suivis par Git pour créer le paquet. Vérifie donc que le code, `pyproject.toml`, `web/`, `locales/` et `requirements.txt` sont bien enregistrés dans le dépôt. Les fichiers ignorés par Git ne sont pas publiés.

Après le succès de la commande, ouvre le lien retourné et vérifie le statut de la version. N’annonce sa disponibilité que lorsque le Registry l’indique disponible ; un délai ou des vérifications peuvent s’appliquer. Le Registry est la voie actuelle pour publier des versions destinées à ComfyUI-Manager.

L’ancienne documentation Manager décrit aussi une inscription par Pull Request sur `custom-node-list.json`. Il s’agit d’une autre voie de référencement ; ce n’est pas une étape à imposer systématiquement après une publication Registry. Si ton paquet ne s’affiche pas, vérifie d’abord son statut Registry et l’actualisation du catalogue du Manager.

## 6. Créer la release GitHub

Dans ton dépôt GitHub : **Releases → Draft a new release**.

- Tag : `v1.8.2`.
- Titre : `ComfyUI True APNG 1.8.2`.
- Texte : copie `publication/RELEASE_NOTES_EN.md`.
- Facultatif : joins l’archive installable `ComfyUI-True-APNG-1.8.2.zip` pour les installations manuelles.

L’archive fournie ici comprend un dossier racine `ComfyUI-True-APNG`, prêt à placer dans `custom_nodes`. La publication d’une release GitHub et la publication Registry sont deux actions distinctes.

Pour présenter l’extension sur un forum ou dans une annonce, utilise `PRESENTATION_EN.md`. Pour illustrer sa fiche, une capture des deux nœuds et un exemple animé montrant la transparence seront utiles. Aucun visuel supplémentaire n’est obligatoire dans le modèle fourni.

## 7. Mises à jour suivantes

1. Modifie le code et vérifie le fonctionnement.
2. Augmente la version dans `__init__.py` et `pyproject.toml`, puis mets à jour les documents et notes de version.
3. Enregistre et pousse les changements sur GitHub.
4. Relance `.\.venv\Scripts\comfy.exe node publish` depuis le dépôt.
5. Crée une release GitHub correspondant à la même version.

Utilise un numéro de version supérieur pour chaque nouvelle publication.

## Publication automatique facultative

La documentation officielle décrit aussi GitHub Actions. Dans les paramètres du dépôt, crée un secret Actions nommé `REGISTRY_ACCESS_TOKEN` contenant la clé de publication, puis suis le modèle officiel : https://docs.comfy.org/registry/publishing#option-2-github-actions.

Aucun workflow de publication automatique n’est activé dans cette archive. La commande manuelle ci-dessus suffit pour commencer.

## Vérifications incluses pour 1.8.2

- 82 tests Python réussis.
- Tests JavaScript d’import APNG, d’aperçu et de migration réussis.
- Tolérance : curseur natif entier, 0–100, pas de 1.
- Les anciens seuils décimaux restent acceptés en interne pour la compatibilité.
- Le moteur APNG n’a pas changé depuis 1.8.1.
- L’intégration graphique complète de ComfyUI n’a pas été exécutée dans l’environnement de tests automatisés.

Le paquet exporte de l’APNG RGB/RGBA 8 bits, sans audio. La réduction de poids dépend du contenu. Pour préserver exactement les couleurs après un redimensionnement éventuellement demandé, utiliser qualité 100 et tolérance 0. La tolérance est une limite par canal RGB, pas une mesure perceptuelle de dégradation. L’alpha reste exact.

## Sources officielles

- Publication, compte Publisher, clé et CLI : https://docs.comfy.org/registry/publishing
- Métadonnées, identifiant et icône : https://docs.comfy.org/registry/specifications
- Installation du CLI : https://docs.comfy.org/comfy-cli/getting-started
- Ancienne voie Manager : https://docs.comfy.org/custom-nodes/backend/manager
