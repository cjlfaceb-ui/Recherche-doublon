# -*- coding: utf-8 -*-
"""Tests hors interface pour la logique de détection de doublons."""

import os
import queue
import shutil
import tempfile
import unittest

import doublon_noyau as doublons


class TestLogic(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.mkdtemp()

    def tearDown(self):
        shutil.rmtree(self.tmp, ignore_errors=True)

    def _write(self, rel, content):
        path = os.path.join(self.tmp, rel)
        os.makedirs(os.path.dirname(path), exist_ok=True)
        with open(path, "wb") as f:
            f.write(content)
        return path

    def _paths_of(self, groups):
        return sorted(sorted(f["path"] for f in g) for g in groups)

    def test_list_drives_returns_root(self):
        drives = doublons.list_drives()
        self.assertTrue(len(drives) >= 1)

    def test_exact_duplicates_detected(self):
        data = os.urandom(40 * 1024)  # > PARTIAL_CHUNK/2 pour tester le hash complet
        a = self._write("photos/a.jpg", data)
        b = self._write("sauvegarde/a.jpg", data)
        c = self._write("photos/autre.jpg", os.urandom(40 * 1024))
        groups = doublons.group_duplicates([a, b, c])
        self.assertEqual(len(groups), 1)
        self.assertEqual(len(groups[0]), 2)
        self.assertEqual(self._paths_of(groups), [[a, b]])

    def test_same_prefix_but_different_content_not_duplicate(self):
        head = os.urandom(70 * 1024)
        a = self._write("x1.bin", head + b"AAAA")
        b = self._write("x2.bin", head + b"BBBB")  # même préfixe de 64 Ko
        groups = doublons.group_duplicates([a, b])
        self.assertEqual(groups, [])

    def test_different_sizes_not_duplicates(self):
        a = self._write("s1.txt", b"salut" * 100)
        b = self._write("s2.txt", b"salut" * 99)
        self.assertEqual(doublons.group_duplicates([a, b]), [])

    def test_group_of_three(self):
        data = b"V" * 100 * 1024
        paths = [self._write(f"g{x}/v.bin", data) for x in range(3)]
        groups = doublons.group_duplicates(paths)
        self.assertEqual(len(groups), 1)
        self.assertEqual(len(groups[0]), 3)

    def test_zero_byte_files_ignored(self):
        a = self._write("z1.tmp", b"")
        b = self._write("z2.tmp", b"")
        self.assertEqual(doublons.group_duplicates([a, b]), [])

    def test_scan_thread_end_to_end(self):
        data = os.urandom(40 * 1024)
        a = self._write("d1/img.png", data)
        b = self._write("d2/Dossier Recyclage/img.png", data)
        c = self._write("d1/unique.png", os.urandom(40 * 1024))
        q = queue.Queue()
        t = doublons.ScanThread([self.tmp], q, ignore_system=True)
        t.start()
        t.join(timeout=30)
        self.assertFalse(t.is_alive())
        kinds = []
        groups = None
        while True:
            try:
                kind, payload = q.get_nowait()
            except queue.Empty:
                break
            kinds.append(kind)
            if kind == "done":
                groups = payload
        self.assertIn("done", kinds)
        self.assertEqual(len(groups), 1)
        self.assertEqual(self._paths_of(groups), [[a, b]])

    def test_human_size(self):
        self.assertEqual(doublons.human_size(512), "512 o")
        self.assertEqual(doublons.human_size(2048), "2.0 Ko")
        self.assertEqual(doublons.human_size(3 * 1024 ** 2), "3.0 Mo")


class TestDelete(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.mkdtemp()

    def tearDown(self):
        shutil.rmtree(self.tmp, ignore_errors=True)

    def test_delete_file_removes_it(self):
        p = os.path.join(self.tmp, "a.txt")
        open(p, "wb").close()
        self.assertEqual(doublons.delete_file(p), None)
        self.assertFalse(os.path.exists(p))


if __name__ == "__main__":
    unittest.main(verbosity=2)
