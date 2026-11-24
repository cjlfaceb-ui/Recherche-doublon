# -*- coding: utf-8 -*-
"""
Recherche de Doublons — application Windows 10.

Analyse tous les disques / stockages connectés, détecte les fichiers en double
(photos, vidéos, documents, musique, etc.) et les présente dans deux fenêtres
parallèles pour comparaison et suppression manuelle.

Dépendance optionnelle : send2trash (corbeille) — pip install send2trash
Sans send2trash, la suppression est définitive (avec confirmation).
"""

import os
import shutil
import sys
import queue
import subprocess
import time
import traceback

import tkinter as tk
from tkinter import ttk, messagebox

import doublon_noyau
from doublon_noyau import (
    APP_TITLE,
    HAS_TRASH,
    ScanThread,
    delete_file,
    list_drives,
    human_size,
    win_long_path,
    short_path,
)

# ---------------------------------------------------------------------------
# Interface graphique
# ---------------------------------------------------------------------------

class Application(tk.Tk):
    def __init__(self):
        super().__init__()
        self.title(APP_TITLE)
        self.geometry("1150x720")
        self.minsize(950, 600)

        self.groups = []
        self.marked = set()          # paths cochés pour suppression
        self.current_group = None
        self.scan_thread = None
        self.q = queue.Queue()
        self.drive_vars = {}

        self._build_top()
        self._build_main()
        self._build_bottom()
        self._refresh_drive_list()
        self.after(120, self._poll_queue)

    # -- construction ------------------------------------------------------

    def _build_top(self):
        top = ttk.Frame(self, padding=(8, 8, 8, 4))
        top.pack(fill="x")

        ttk.Label(top, text="Disques et stockages à analyser :").pack(anchor="w")
        self.drives_frame = ttk.Frame(top)
        self.drives_frame.pack(fill="x", pady=(4, 2))

        btns = ttk.Frame(top)
        btns.pack(fill="x", pady=(4, 0))
        self.btn_refresh = ttk.Button(btns, text="Rafraîchir les disques",
                                      command=self._refresh_drive_list)
        self.btn_refresh.pack(side="left")
        self.btn_scan = ttk.Button(btns, text="🔍  Rechercher les doublons",
                                   command=self._start_scan)
        self.btn_scan.pack(side="left", padx=8)
        self.btn_cancel = ttk.Button(btns, text="Interrompre",
                                     command=self._cancel_scan, state="disabled")
        self.btn_cancel.pack(side="left")
        self.ignore_system_var = tk.BooleanVar(value=True)
        ttk.Checkbutton(btns, variable=self.ignore_system_var,
                        text="Ignorer les dossiers système (Windows, Corbeille…)"
                        ).pack(side="left", padx=16)

        row2 = ttk.Frame(top)
        row2.pack(fill="x", pady=(4, 0))
        self.progress = ttk.Progressbar(row2, mode="determinate")
        self.progress.pack(side="left", fill="x", expand=True)
        self.status = ttk.Label(row2, text="Prêt.")
        self.status.pack(side="right", padx=(10, 0))

    def _build_main(self):
        paned = ttk.Panedwindow(self, orient="vertical")
        paned.pack(fill="both", expand=True, padx=8, pady=4)

        # -- haut : liste des groupes --------------------------------------
        groups_wrap = ttk.LabelFrame(paned, text="Groupes de doublons détectés", padding=4)
        paned.add(groups_wrap, weight=1)

        self.groups_tree = ttk.Treeview(
            groups_wrap, columns=("nb", "nom", "taille", "gaspille"),
            show="headings", selectmode="browse", height=8,
        )
        for col, text, w, anchor in (
            ("nb", "N°", 50, "center"),
            ("nom", "Fichier", 380, "w"),
            ("taille", "Taille du fichier", 110, "e"),
            ("gaspille", "Espace en double", 130, "e"),
        ):
            self.groups_tree.heading(col, text=text)
            self.groups_tree.column(col, width=w, anchor=anchor)
        vsb = ttk.Scrollbar(groups_wrap, orient="vertical", command=self.groups_tree.yview)
        self.groups_tree.configure(yscrollcommand=vsb.set)
        self.groups_tree.pack(side="left", fill="both", expand=True)
        vsb.pack(side="left", fill="y")
        self.groups_tree.bind("<<TreeviewSelect>>", self._on_group_select)

        # -- bas : deux fenêtres parallèles --------------------------------
        compare = ttk.Frame(paned)
        paned.add(compare, weight=2)

        self.pane1 = self._make_compare_pane(compare, "Fichier 1", side="left")
        self.pane2 = self._make_compare_pane(compare, "Fichier 2", side="right")
        self.panels = [self.pane1, self.pane2]

    def _make_compare_pane(self, parent, title, side):
        pane = ttk.LabelFrame(parent, text=title + " (doublon)", padding=8)
        pane.pack(side=side, fill="both", expand=True, padx=(0, 4) if side == "left" else (0, 0))
        pane._title = title

        name_var = tk.StringVar(value="—")
        ttk.Label(pane, textvariable=name_var, font=("Segoe UI", 11, "bold"),
                  wraplength=430).pack(anchor="w")

        info_var = tk.StringVar(value="")
        ttk.Label(pane, textvariable=info_var, foreground="#555")\
            .pack(anchor="w", pady=(4, 2))

        path_var = tk.StringVar(value="")
        ttk.Label(pane, textvariable=path_var, wraplength=430,
                  foreground="#0a58ca").pack(anchor="w")

        btns = ttk.Frame(pane)
        btns.pack(anchor="w", pady=(8, 0))
        ttk.Button(btns, text="◆ Fichier précédent",
                   command=lambda: self._cycle_file(pane, -1)).pack(side="left")
        ttk.Button(btns, text="◆ Fichier suivant",
                   command=lambda: self._cycle_file(pane, 1)).pack(side="left", padx=4)
        ttk.Button(btns, text="Ouvrir le fichier",
                   command=lambda: self._open_file(pane)).pack(side="left")
        ttk.Button(btns, text="Ouvrir le dossier",
                   command=lambda: self._open_folder(pane)).pack(side="left", padx=4)

        check_row = ttk.Frame(pane)
        check_row.pack(anchor="w", pady=(8, 0))
        marked_var = tk.BooleanVar(value=False)
        cb = ttk.Checkbutton(check_row, variable=marked_var, text="Cocher pour suppression",
                             command=lambda: self._toggle_mark(pane))
        cb.pack(side="left")

        pane._vars = {"name": name_var, "info": info_var, "path": path_var,
                      "marked": marked_var, "cb": cb}
        pane._current = None
        return pane

    def _build_bottom(self):
        bottom = ttk.Frame(self, padding=(8, 4, 8, 8))
        bottom.pack(fill="x")

        self.marked_label = ttk.Label(bottom, text="Aucun fichier coché.")
        self.marked_label.pack(side="left")

        ttk.Button(bottom, text="Tout décocher",
                   command=self._unmark_all).pack(side="left", padx=10)
        self.btn_delete = ttk.Button(bottom, text="🗑  Supprimer les fichiers cochés",
                                     command=self._delete_marked, state="disabled")
        self.btn_delete.pack(side="right")
        self.btn_keep_first = ttk.Button(
            bottom, text="Garder le 1er, cocher les autres du groupe",
            command=self._mark_others, state="disabled")
        self.btn_keep_first.pack(side="right", padx=(0, 10))

    # -- disques -----------------------------------------------------------

    def _refresh_drive_list(self):
        for w in self.drives_frame.winfo_children():
            w.destroy()
        self.drive_vars.clear()
        for drive in list_drives():
            var = tk.BooleanVar(value=True)
            self.drive_vars[drive] = var
            label = drive
            try:
                usage = shutil.disk_usage(drive)
                label = f"{drive}  ({human_size(usage.free)} libres sur {human_size(usage.total)})"
            except OSError:
                pass
            ttk.Checkbutton(self.drives_frame, text=label, variable=var).pack(
                side="left", padx=(0, 12))

    # -- analyse -----------------------------------------------------------

    def _start_scan(self):
        roots = [d for d, v in self.drive_vars.items() if v.get()]
        if not roots:
            messagebox.showwarning(APP_TITLE, "Sélectionnez au moins un disque ou dossier.")
            return
        if self.current_group is not None or self.scan_thread:
            if self.scan_thread and self.scan_thread.is_alive():
                messagebox.showinfo(APP_TITLE, "Une analyse est déjà en cours.")
                return

        self._clear_results()
        self.btn_scan.config(state="disabled")
        self.btn_cancel.config(state="normal")
        self.progress.config(value=0, mode="indeterminate")
        self.progress.start(60)
        self.status.config(text="Préparation…")
        self.marked.clear()

        self.scan_thread = ScanThread(roots, self.q,
                                      ignore_system=self.ignore_system_var.get())
        self.scan_thread.start()

    def _cancel_scan(self):
        if self.scan_thread:
            self.scan_thread.stop()
            self.status.config(text="Interruption demandée…")

    def _poll_queue(self):
        try:
            while True:
                kind, payload = self.q.get_nowait()
                if kind == "status":
                    self.status.config(text=payload)
                elif kind == "progress":
                    done, total = payload
                    if total:
                        self.progress.config(mode="determinate", maximum=total)
                        self.progress.stop()
                        self.progress.config(value=done)
                elif kind == "done":
                    self._load_groups(payload)
                elif kind == "cancelled":
                    self.status.config(text="Analyse interrompue.")
                    self._scan_finished()
                elif kind == "error":
                    self.status.config(text="Erreur pendant l'analyse.")
                    self.progress.stop()
                    messagebox.showerror(APP_TITLE, "Erreur pendant l'analyse :\n" + payload[:2000])
                    self._scan_finished()
        except queue.Empty:
            pass
        self.after(120, self._poll_queue)

    def _scan_finished(self):
        self.progress.stop()
        self.progress.config(value=0)
        self.btn_scan.config(state="normal")
        self.btn_cancel.config(state="disabled")
        self.scan_thread = None

    def _clear_results(self):
        for i in self.groups_tree.get_children():
            self.groups_tree.delete(i)
        self.groups = []
        self.current_group = None
        for pane in self.panels:
            pane._current = None
            pane._vars["name"].set("—")
            pane._vars["info"].set("")
            pane._vars["path"].set("")
            pane._vars["marked"].set(False)

    def _load_groups(self, groups):
        self.groups = groups
        self._scan_finished()
        self.status.config(
            text=f"Analyse terminée : {len(groups)} groupe(s) de doublons trouvés."
        )
        for i, files in enumerate(self.groups, 1):
            wasted = files[0]["size"] * (len(files) - 1)
            name = os.path.basename(short_path(files[0]["path"]))
            self.groups_tree.insert("", "end", iid=str(i - 1), values=(
                i, name, human_size(files[0]["size"]), human_size(wasted)))
        if groups:
            self._select_group(0)

    def _select_group(self, index):
        children = self.groups_tree.get_children()
        if 0 <= index < len(children):
            self.groups_tree.selection_set(children[index])
            self.groups_tree.see(children[index])

    # -- affichage d'un groupe ---------------------------------------------

    def _on_group_select(self, _event=None):
        sel = self.groups_tree.selection()
        if not sel:
            return
        index = int(sel[0])
        self.current_group = index
        files = self.groups[index]
        self.pane1._current = 0
        self.pane2._current = min(1, len(files) - 1)
        self._refresh_panes()
        self._refresh_pane_title()

    def _refresh_pane_title(self):
        files = self.groups[self.current_group]
        for pane in self.panels:
            pane.configure(
                text=f"{pane._title}  —  fichier {pane._current + 1}/{len(files)}"
            )

    def _refresh_panes(self):
        if self.current_group is None:
            return
        files = self.groups[self.current_group]
        self._refresh_pane_title()
        for pane in self.panels:
            f = files[pane._current]
            pane._vars["name"].set(os.path.basename(short_path(f["path"])))
            pane._vars["info"].set(
                f"{human_size(f['size'])}   •   modifié le "
                f"{time.strftime('%d/%m/%Y %H:%M', time.localtime(f['mtime']))}"
            )
            pane._vars["path"].set(short_path(f["path"]))
            pane._vars["marked"].set(f["path"] in self.marked)
            pane._file = f
        self.btn_keep_first.config(state="normal")
        self._update_marked_label()

    def _cycle_file(self, pane, direction):
        if self.current_group is None:
            return
        files = self.groups[self.current_group]
        pane._current = (pane._current + direction) % len(files)
        self._refresh_panes()
        self._refresh_pane_title()

    # -- ouverture de fichiers ---------------------------------------------

    def _open_file(self, pane):
        self._open_path(pane._vars["path"].get(), file=True)

    def _open_folder(self, pane):
        self._open_path(pane._vars["path"].get(), file=False)

    def _open_path(self, path, file=True):
        if not path:
            return
        target = path if file else os.path.dirname(short_path(path))
        try:
            if os.name == "nt":
                os.startfile(target)
            elif sys.platform == "darwin":
                subprocess.Popen(["open", target])
            else:
                subprocess.Popen(["xdg-open", target])
        except OSError as e:
            messagebox.showerror(APP_TITLE, f"Impossible d'ouvrir :\n{e}")

    # -- marquage / suppression --------------------------------------------

    def _toggle_mark(self, pane):
        f = getattr(pane, "_file", None)
        if not f:
            return
        if pane._vars["marked"].get():
            self.marked.add(f["path"])
        else:
            self.marked.discard(f["path"])
        self._update_marked_label()

    def _mark_others(self):
        if self.current_group is None:
            return
        files = self.groups[self.current_group]
        for i, f in enumerate(files):
            if i > 0:
                self.marked.add(f["path"])
            else:
                self.marked.discard(f["path"])
        self._refresh_panes()
        self._update_marked_label()

    def _unmark_all(self):
        self.marked.clear()
        for pane in self.panels:
            pane._vars["marked"].set(False)
        self._update_marked_label()

    def _update_marked_label(self):
        n = len(self.marked)
        total = 0
        for path in self.marked:
            try:
                total += os.stat(path).st_size
            except OSError:
                pass
        self.marked_label.config(
            text=(f"{n} fichier(s) coché(s) — {human_size(total)} à supprimer."
                  if n else "Aucun fichier coché.")
        )
        self.btn_delete.config(state="normal" if n else "disabled")

    def _delete_marked(self):
        n = len(self.marked)
        if not n:
            return
        mode = ("dans la corbeille" if HAS_TRASH else "DÉFINITIVEMENT (sans corbeille !)")
        if not messagebox.askyesno(
                APP_TITLE,
                f"Supprimer {n} fichier(s) {mode} ?\n\n"
                "Cette action est irréversible."):
            return

        deleted = 0
        errors = []
        for path in list(self.marked):
            err = delete_file(path)
            if err is None:
                deleted += 1
                self.marked.discard(path)
            else:
                errors.append(f"{short_path(path)} : {err}")

        # purge des fichiers supprimés et des groupes devenus invalides
        self._prune_deleted()
        self._refresh_panes()

        if errors:
            messagebox.showwarning(APP_TITLE,
                                   f"{deleted} fichier(s) supprimé(s).\n\nErreurs :\n"
                                   + "\n".join(errors[:20]))
        else:
            messagebox.showinfo(APP_TITLE, f"{deleted} fichier(s) supprimé(s) avec succès.")

    def _prune_deleted(self):
        self.groups = [
            [f for f in files if os.path.exists(win_long_path(f["path"]))]
            for files in self.groups
        ]
        self.groups = [files for files in self.groups if len(files) > 1]
        for i in self.groups_tree.get_children():
            self.groups_tree.delete(i)
        for i, files in enumerate(self.groups, 1):
            wasted = files[0]["size"] * (len(files) - 1)
            name = os.path.basename(short_path(files[0]["path"]))
            self.groups_tree.insert("", "end", iid=str(i - 1), values=(
                i, name, human_size(files[0]["size"]), human_size(wasted)))
        self.current_group = None
        if self.groups:
            self._select_group(0)
        self._update_marked_label()
        self.status.config(text=f"{len(self.groups)} groupe(s) de doublons restants.")


def main():
    try:
        if hasattr(tk, "Tk") and os.name == "nt" and sys.version_info >= (3, 8):
            try:
                import ctypes
                ctypes.windll.shcore.SetProcessDpiAwareness(1)
            except Exception:
                pass
        app = Application()
        app.mainloop()
    except Exception:
        traceback.print_exc()
        try:
            messagebox.showerror(APP_TITLE, traceback.format_exc())
        except Exception:
            pass
        sys.exit(1)


if __name__ == "__main__":
    main()
