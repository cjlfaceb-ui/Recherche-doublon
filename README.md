# Recherche de Doublons (Windows 10)

Application permettant de rechercher les doublons dans tous les stockages du PC et de faire le tri.

## Description

Application qui parcourt **tous les disques et stockages connectés** (disque C:,
D:, clés USB, disques externes…), détecte les **fichiers en double** (photos,
vidéos, documents, musique, archives… tout type de fichier) et les affiche dans
**deux fenêtres parallèles** pour que vous puissiez les comparer, puis les
supprimer manuellement, en toute sécurité.

## Fonctionnalités

- Détection automatique de tous les disques connectés (cases à cocher pour choisir).
- Comparaison en 3 étapes (taille → 64 premiers Ko → empreinte complète SHA-256) :
  rapide, et sans faux positifs.
- Liste des groupes de doublons avec taille gaspillée.
- **Deux panneaux côte à côte** : nom du fichier, taille, date de modification,
  chemin complet ; boutons *Fichier précédent / suivant* pour naviguer dans un
  groupe de plus de 2 copies.
- Ouverture directe du fichier ou de son dossier.
- Suppression manuelle : cochez ce que vous voulez supprimer (case par case ou
  « Garder le 1er, cocher les autres du groupe »), puis
  **Supprimer les fichiers cochés**.
- Mise à la **corbeille** si le paquet `send2trash` est installé (recommandé),
  sinon suppression définitive après confirmation explicite.
- Ignorer les dossiers système (Windows, Corbeille…) — option décochable.
- Bouton « Interrompre » pour arrêter une analyse en cours.

## Installation

### Option A — exécutable unique (recommandé, pas besoin de Python à l'utilisation)

1. Installez [Python 3.8+](https://www.python.org/downloads/) sur un PC
   (cochez « Add python.exe to PATH » à l'installation).
2. Double-cliquez sur **`build_exe.bat`** : il crée `dist\RechercheDoublons.exe`.
3. Copiez ce `.exe` où vous voulez : il fonctionne seul, sans Python.

### Option B — installateur Windows

1. Générez d'abord le `.exe` (option A, étapes 1-2).
2. Installez [Inno Setup](https://jrsoftware.org/isdl.php), ouvrez
   `installer.iss` et cliquez sur *Compile*.
   Vous obtenez `installateur\Installer-RechercheDoublons-1.0.exe`,
   un installateur classique (menu Démarrer + raccourci bureau +
   désinstallation).

### Option C — lancer directement avec Python

Double-cliquez sur **`lancer_windows.bat`**.

## Utilisation

1. Lancez l'application : les disques détectés sont cochés par défaut.
2. Cliquez sur **Rechercher les doublons** et attendez la fin de l'analyse.
3. Dans la liste du haut, cliquez sur un groupe de doublons : il s'affiche
   dans les deux fenêtres parallèles du bas.
4. Comparez les deux fichiers (taille, date, ou ouvrez-les).
5. Cochez « Cocher pour suppression » sur la copie à supprimer, ou utilisez
   « Garder le 1er, cocher les autres du groupe ».
6. Cliquez sur **Supprimer les fichiers cochés** (confirmation demandée).

## Fichiers du projet

| Fichier | Rôle |
|---|---|
| `doublons.py` | Interface graphique (tkinter) |
| `doublon_noyau.py` | Noyau : détection des doublons, suppression |
| `test_doublons.py` | Tests de la logique (`python test_doublons.py`) |
| `build_exe.bat` | Construction du `.exe` autonome |
| `lancer_windows.bat` | Lancement direct avec Python |
| `installer.iss` | Script d'installation Inno Setup |

## Limites connues

- Les fichiers de moins de 2 octets et les fichiers vides sont ignorés.
- Les dossiers protégés par Windows provoquent des avertissements d'accès ;
  ils sont simplement ignorés par l'analyse (pas de plantage).
- Sur les très grands disques (des centaines de milliers de fichiers),
  l'analyse complète peut prendre plusieurs minutes : les barres de progression
  et le bouton « Interrompre » permettent de suivre/piloter l'opération.
