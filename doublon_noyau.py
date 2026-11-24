# -*- coding: utf-8 -*-
"""
Noyau de la Recherche de Doublons : détection de fichiers identiques,
sans interface graphique. Testable indépendamment.
"""

import os
import string
import hashlib
import threading
import traceback

try:
    from send2trash import send2trash
    HAS_TRASH = True
except ImportError:
    HAS_TRASH = False


APP_TITLE = "Recherche de Doublons"
HASH_ALGO = "sha256"
PARTIAL_CHUNK = 64 * 1024

IGNORED_DIRS_WIN = {
    "$recycle.bin", "system volume information", "windows",
    "program files", "program files (x86)", "programdata",
    "appdata", "msocache",
}


# ---------------------------------------------------------------------------
# Géométrie (logic testable)
# ---------------------------------------------------------------------------

def list_drives():
    """Retourne la liste des racines de stockage disponibles."""
    drives = []
    if os.name == "nt":
        for letter in string.ascii_uppercase:
            path = letter + ":\\"
            if os.path.exists(path):
                drives.append(path)
    else:
        roots = ["/"]
        for base in ("/media", "/mnt", "/run/media"):
            if os.path.isdir(base):
                try:
                    for name in os.listdir(base):
                        p = os.path.join(base, name)
                        if os.path.isdir(p):
                            roots.append(p)
                except OSError:
                    pass
        drives = roots
    return drives


def human_size(nbytes):
    if nbytes is None:
        return "?"
    for unit in ("o", "Ko", "Mo", "Go", "To"):
        if nbytes < 1024 or unit == "To":
            if unit == "o":
                return f"{nbytes} o"
            return f"{nbytes:.1f} {unit}"
        nbytes /= 1024.0


def win_long_path(path):
    """Préfixe de chemin long pour dépasser la limite Windows de 260 caractères."""
    if os.name == "nt" and len(path) > 230 and not path.startswith("\\\\?\\"):
        if path.startswith("\\\\"):
            return "\\\\?\\UNC\\" + path.lstrip("\\")
        return "\\\\?\\" + path
    return path


def short_path(path):
    return path[4:] if path.startswith("\\\\?\\") else path


def group_duplicates(paths, ignore_system=True):
    """
    Regroupe les fichiers identiques.
    Étapes : taille -> empreinte partielle (64 Ko) -> empreinte complète.
    Retourne une liste de groupes, chaque groupe = liste de dicts
    {path, size, mtime}.
    """
    # 1) groupement par taille
    by_size = {}
    for path in paths:
        try:
            st = os.stat(path)
            if st.st_size == 0:
                continue
            by_size.setdefault(st.st_size, []).append(path)
        except OSError:
            continue

    candidates = {s: ps for s, ps in by_size.items() if len(ps) > 1}
    if not candidates:
        return []

    # 2) empreinte partielle
    by_partial = {}
    for size, ps in candidates.items():
        for p in ps:
            h = _hash_file(p, partial=True)
            if h is None:
                continue
            key = (size, h)
            by_partial.setdefault(key, []).append(p)
    candidates = {k: ps for k, ps in by_partial.items() if len(ps) > 1}
    if not candidates:
        return []

    # 3) empreinte complète
    groups = []
    for (size, _), ps in sorted(candidates.items(), key=lambda kv: -kv[0][0]):
        by_full = {}
        for p in ps:
            h = _hash_file(p, partial=False)
            if h is None:
                continue
            by_full.setdefault(h, []).append(p)
        for h, fps in by_full.items():
            if len(fps) > 1:
                files = []
                for p in fps:
                    try:
                        st = os.stat(p)
                        files.append({
                            "path": p,
                            "size": st.st_size,
                            "mtime": st.st_mtime,
                        })
                    except OSError:
                        pass
                if len(files) > 1:
                    files.sort(key=lambda f: len(f["path"]))
                    groups.append(files)
    groups.sort(key=lambda g: -g[0]["size"])
    return groups


def delete_file(path):
    """Supprime un fichier (corbeille si possible, sinon définitif).
    Renvoie None si succès, sinon le message d'erreur."""
    try:
        real = win_long_path(path)
        if HAS_TRASH:
            send2trash(real)
        else:
            os.remove(real)
        return None
    except Exception as e:
        return str(e)


def _hash_file(path, partial=False):
    h = hashlib.new(HASH_ALGO)
    real = win_long_path(path)
    try:
        with open(real, "rb") as f:
            if partial:
                data = f.read(PARTIAL_CHUNK)
                h.update(data)
            else:
                for chunk in iter(lambda: f.read(1024 * 1024), b""):
                    h.update(chunk)
        return h.hexdigest()
    except OSError:
        return None


def iter_all_files(roots, ignore_system=True):
    """Générateur de tous les chemins de fichiers sous les racines données."""
    for root in roots:
        if os.path.isfile(root):
            yield root
            continue
        for dirpath, dirnames, filenames in os.walk(root, onerror=lambda e: None):
            if ignore_system:
                dirnames[:] = [
                    d for d in dirnames if d.lower() not in IGNORED_DIRS_WIN
                ]
            for name in filenames:
                yield os.path.join(dirpath, name)


# ---------------------------------------------------------------------------
# Thread d'analyse
# ---------------------------------------------------------------------------

class ScanThread(threading.Thread):
    def __init__(self, roots, out_queue, ignore_system=True):
        super().__init__(daemon=True)
        self.roots = roots
        self.out_queue = out_queue
        self.ignore_system = ignore_system
        self.stop_event = threading.Event()

    def stop(self):
        self.stop_event.set()

    def run(self):
        try:
            out = self.out_queue
            out.put(("status", "Inventaire des fichiers…"))
            all_files = []
            for path in iter_all_files(self.roots, self.ignore_system):
                if self.stop_event.is_set():
                    out.put(("cancelled", None))
                    return
                all_files.append(path)
                if len(all_files) % 5000 == 0:
                    out.put(("status", f"Inventaire : {len(all_files):,} fichiers…".replace(",", " ")))

            by_size = {}
            for path in all_files:
                if self.stop_event.is_set():
                    out.put(("cancelled", None))
                    return
                try:
                    st = os.stat(path)
                    if st.st_size == 0:
                        continue
                    by_size.setdefault(st.st_size, []).append(path)
                except OSError:
                    continue

            candidates = [(s, ps) for s, ps in by_size.items() if len(ps) > 1]
            total_partial = sum(len(ps) for _, ps in candidates)

            out.put(("status", "Comparaison rapide des empreintes…"))
            by_partial = {}
            done = 0
            for size, ps in candidates:
                for p in ps:
                    if self.stop_event.is_set():
                        out.put(("cancelled", None))
                        return
                    h = _hash_file(p, partial=True)
                    done += 1
                    if done % 25 == 0:
                        out.put(("progress", (done, max(total_partial, 1))))
                    if h is None:
                        continue
                    by_partial.setdefault((size, h), []).append(p)
            by_partial = {k: ps for k, ps in by_partial.items() if len(ps) > 1}

            total_full = sum(len(ps) for ps in by_partial.values())
            out.put(("status", "Vérification complète des doublons probables…"))
            done = 0
            groups = []
            for (size, _), ps in by_partial.items():
                by_full = {}
                for p in ps:
                    if self.stop_event.is_set():
                        out.put(("cancelled", None))
                        return
                    fh = _hash_file(p)
                    done += 1
                    if done % 3 == 0:
                        out.put(("progress", (done, max(total_full, 1))))
                    if fh is None:
                        continue
                    by_full.setdefault(fh, []).append(p)
                for fh, fps in by_full.items():
                    if len(fps) > 1:
                        files = []
                        for p in fps:
                            try:
                                st = os.stat(p)
                                files.append({
                                    "path": p,
                                    "size": st.st_size,
                                    "mtime": st.st_mtime,
                                })
                            except OSError:
                                pass
                        if len(files) > 1:
                            files.sort(key=lambda f: len(f["path"]))
                            groups.append(files)

            groups.sort(key=lambda g: -g[0]["size"])
            out.put(("done", groups))
        except Exception:
            self.out_queue.put(("error", traceback.format_exc()))


