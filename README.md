# Catalogue Cuisinier — miroir GitHub Pages

Miroir **public en lecture seule** des recettes admissibles (notées 3, 4 ou 5) de la bibliothèque Synology.

Source : `https://lesmenusduchat.synology.me/menus2/catalogue-public.php`

## Mise en service
1. Dans **Settings > Pages > Build and deployment**, sélectionner **GitHub Actions**.
2. Dans **Actions > Publier le catalogue Cuisinier**, lancer **Run workflow** sur `main`.
3. Après le succès de **build** et **deploy**, ouvrir `https://nicolasjung.github.io/cuisinier-catalogue/catalogue.json`.

## Données publiées
- `catalogue.json` : index des recettes de 3 à 5 étoiles, notes et favoris.
- `recettes/RF-XXXXXXXXXXXX.json` : fiches détaillées avec ingrédients et étapes.
- `index.html` : liste lisible.

Aucun compte, commentaire personnel, mot de passe, jeton ni chemin de données privé n'est publié. Le code applique une liste stricte de champs autorisés.

Le workflow s'exécute quatre fois par jour (UTC) et sur déclenchement manuel. Si une page ou une fiche est inaccessible ou incohérente, la génération échoue sans déployer un catalogue partiel. GitHub peut retarder les horaires programmés et désactiver les tâches planifiées sur les dépôts inactifs.

Les recettes, notes et favoris copiés deviennent accessibles à tous. Le dépôt n'a pas d'accès en écriture au Synology.