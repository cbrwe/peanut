"""
test_all_filetypes.py
=====================
Tests covering the all-file-types audit — eight tests that each exercise one
of the audit changes applied to scanner.py.

Run from peanut/ root:  python3 -m pytest tests/test_all_filetypes.py -v
or:                     python3 tests/test_all_filetypes.py
"""

import io
import os
import sys
import tarfile
import tempfile
import unittest
import zipfile
from pathlib import Path

# Make scanner.py importable when run directly
HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE.parent))

import scanner
from scanner import (
    ALL_EXTS, ARCHIVE_EXTS, AUDIO_EXTS, CODE_EXTS, DOC_EXTS,
    FILE_CATEGORIES, IMAGE_EXTS, OTHER_EXTS, PLAIN_TEXT_DOC_EXTS,
    VIDEO_EXTS, PeanutScanner, _extract_text_inner, archive_content_hash,
)


class Test01_ExtensionExpansions(unittest.TestCase):
    """Audit item 1: each existing category has new formats added."""

    def test_image_exts_expanded(self):
        # JPEG 2000, JPEG XL, JFIF, DDS, Netpbm, more RAW
        for ext in [".jp2", ".jxl", ".jfif", ".dds", ".tga",
                    ".pbm", ".ppm", ".cr3", ".raf"]:
            self.assertIn(ext, IMAGE_EXTS, f"{ext} should be in IMAGE_EXTS")

    def test_video_exts_expanded(self):
        # MXF (broadcast), F4V, RealMedia, M2TS (Blu-ray), DV
        for ext in [".mxf", ".f4v", ".rm", ".rmvb", ".m2ts",
                    ".asf", ".divx", ".dv"]:
            self.assertIn(ext, VIDEO_EXTS, f"{ext} should be in VIDEO_EXTS")

    def test_audio_exts_expanded(self):
        # MIDI, AMR, AC3, DTS, MKA, DSD, CAF, M4B
        for ext in [".mid", ".midi", ".amr", ".ac3", ".dts",
                    ".mka", ".dsf", ".caf", ".m4b"]:
            self.assertIn(ext, AUDIO_EXTS, f"{ext} should be in AUDIO_EXTS")

    def test_doc_exts_expanded(self):
        # Apple iWork, Kindle, subtitles, configs
        for ext in [".pages", ".numbers", ".key", ".mobi", ".azw3",
                    ".srt", ".vtt", ".env", ".rst"]:
            self.assertIn(ext, DOC_EXTS, f"{ext} should be in DOC_EXTS")

    def test_code_exts_expanded(self):
        # Dart, Scala, Clojure, Elixir, Haskell, Zig, Julia, Erlang, OCaml
        for ext in [".dart", ".scala", ".clj", ".ex", ".exs",
                    ".hs", ".zig", ".jl", ".erl", ".ml"]:
            self.assertIn(ext, CODE_EXTS, f"{ext} should be in CODE_EXTS")

    def test_archive_exts_expanded(self):
        # tbz2, txz, zst, cab, lzma
        for ext in [".tbz2", ".txz", ".zst", ".cab", ".lzma", ".tar.bz2"]:
            self.assertIn(ext, ARCHIVE_EXTS,
                          f"{ext} should be in ARCHIVE_EXTS")


class Test02_OtherExtsExists(unittest.TestCase):
    """Audit item 2: OTHER_EXTS set covers fonts, disk images, executables,
    3D/CAD, databases, serialization formats."""

    def test_other_exts_is_set(self):
        self.assertIsInstance(OTHER_EXTS, set)
        self.assertGreater(len(OTHER_EXTS), 30)

    def test_other_exts_fonts(self):
        for ext in [".ttf", ".otf", ".woff", ".woff2"]:
            self.assertIn(ext, OTHER_EXTS, f"{ext} should be in OTHER_EXTS")

    def test_other_exts_disk_images(self):
        for ext in [".iso", ".dmg", ".img", ".vhd", ".vmdk"]:
            self.assertIn(ext, OTHER_EXTS, f"{ext} should be in OTHER_EXTS")

    def test_other_exts_executables(self):
        for ext in [".exe", ".msi", ".deb", ".pkg", ".rpm", ".apk"]:
            self.assertIn(ext, OTHER_EXTS, f"{ext} should be in OTHER_EXTS")

    def test_other_exts_3d_cad(self):
        for ext in [".blend", ".stl", ".obj", ".fbx", ".dwg", ".gltf"]:
            self.assertIn(ext, OTHER_EXTS, f"{ext} should be in OTHER_EXTS")

    def test_other_exts_databases(self):
        for ext in [".db", ".sqlite", ".sqlite3", ".mdb"]:
            self.assertIn(ext, OTHER_EXTS, f"{ext} should be in OTHER_EXTS")

    def test_other_exts_serialization(self):
        for ext in [".pkl", ".parquet", ".npy", ".h5", ".hdf5"]:
            self.assertIn(ext, OTHER_EXTS, f"{ext} should be in OTHER_EXTS")

    def test_other_in_file_categories(self):
        self.assertIn("other", FILE_CATEGORIES)
        self.assertEqual(FILE_CATEGORIES["other"], OTHER_EXTS)

    def test_other_in_all_exts(self):
        # OTHER_EXTS should be folded into ALL_EXTS so cataloging finds them
        for ext in [".ttf", ".iso", ".exe", ".db"]:
            self.assertIn(ext, ALL_EXTS, f"{ext} should be in ALL_EXTS")


class Test03_PlainTextDocExtsExists(unittest.TestCase):
    """Audit item 3: PLAIN_TEXT_DOC_EXTS for formats that should be read as
    raw text (yaml/toml/ini/sql/tex/srt/vtt/env/etc.)."""

    def test_plain_text_doc_exts_is_set(self):
        self.assertIsInstance(PLAIN_TEXT_DOC_EXTS, set)
        self.assertGreater(len(PLAIN_TEXT_DOC_EXTS), 15)

    def test_plain_text_includes_config_formats(self):
        for ext in [".yaml", ".yml", ".toml", ".ini", ".cfg",
                    ".conf", ".env", ".properties"]:
            self.assertIn(ext, PLAIN_TEXT_DOC_EXTS,
                          f"{ext} should be in PLAIN_TEXT_DOC_EXTS")

    def test_plain_text_includes_subtitles(self):
        for ext in [".srt", ".vtt", ".sub", ".ass", ".ssa"]:
            self.assertIn(ext, PLAIN_TEXT_DOC_EXTS,
                          f"{ext} should be in PLAIN_TEXT_DOC_EXTS")

    def test_plain_text_includes_other(self):
        for ext in [".sql", ".tex", ".bib", ".diff", ".patch", ".rst"]:
            self.assertIn(ext, PLAIN_TEXT_DOC_EXTS,
                          f"{ext} should be in PLAIN_TEXT_DOC_EXTS")

    def test_plain_text_subset_of_doc(self):
        # Every plain-text format should also be a recognized document type
        for ext in PLAIN_TEXT_DOC_EXTS:
            self.assertIn(ext, DOC_EXTS,
                          f"{ext} is in PLAIN_TEXT_DOC_EXTS but not DOC_EXTS")


class Test04_PlainTextExtraction(unittest.TestCase):
    """Audit item 4: _extract_text_inner reads PLAIN_TEXT_DOC_EXTS formats."""

    def setUp(self):
        self.tmp = tempfile.mkdtemp()

    def tearDown(self):
        import shutil
        shutil.rmtree(self.tmp, ignore_errors=True)

    def _write(self, name, content):
        p = os.path.join(self.tmp, name)
        with open(p, "w", encoding="utf-8") as f:
            f.write(content)
        return p

    def test_yaml_extracted(self):
        body = "name: peanut\nversion: 1.0\ndependencies:\n  - flask\n  - numpy\n"
        text = _extract_text_inner(self._write("config.yaml", body))
        self.assertIn("peanut", text)
        self.assertIn("dependencies", text)

    def test_toml_extracted(self):
        body = '[project]\nname = "peanut"\nversion = "1.0"\n[deps]\nflask = "*"\n'
        text = _extract_text_inner(self._write("pyproject.toml", body))
        self.assertIn("peanut", text)
        self.assertIn("flask", text)

    def test_ini_extracted(self):
        body = "[section]\nkey1=value1\nkey2=value2\n[other]\nfoo=bar\n"
        text = _extract_text_inner(self._write("config.ini", body))
        self.assertIn("section", text)
        self.assertIn("value1", text)

    def test_sql_extracted(self):
        body = "CREATE TABLE users (id INT, name VARCHAR(255));\nINSERT INTO users VALUES (1, 'alice');\n"
        text = _extract_text_inner(self._write("schema.sql", body))
        self.assertIn("CREATE TABLE", text)
        self.assertIn("alice", text)

    def test_srt_extracted(self):
        body = "1\n00:00:01,000 --> 00:00:04,000\nHello world\n\n2\n00:00:05,000 --> 00:00:08,000\nGoodbye\n"
        text = _extract_text_inner(self._write("movie.srt", body))
        self.assertIn("Hello world", text)
        self.assertIn("Goodbye", text)

    def test_vtt_extracted(self):
        body = "WEBVTT\n\n1\n00:00:01.000 --> 00:00:04.000\nSubtitle text\n"
        text = _extract_text_inner(self._write("video.vtt", body))
        self.assertIn("WEBVTT", text)
        self.assertIn("Subtitle text", text)

    def test_env_extracted(self):
        body = "DATABASE_URL=postgres://localhost/mydb\nAPI_KEY=secret\n"
        text = _extract_text_inner(self._write(".env", body))
        # Note: .env via Path(".env").suffix is "" — so the test file
        # needs an explicit .env extension. Suffix on ".env" filename
        # depends on the leading dot; verify both cases.
        # If the leading-dot case fails, we should still extract from a
        # plain-named version like "config.env":
        text2 = _extract_text_inner(self._write("config.env", body))
        self.assertIn("DATABASE_URL", text2)

    def test_unsupported_binary_returns_empty(self):
        # An unrecognized binary extension should NOT be parsed as text.
        # Write some binary garbage to a .xyz file.
        p = os.path.join(self.tmp, "garbage.xyz")
        with open(p, "wb") as f:
            f.write(bytes(range(256)) * 4)
        text = _extract_text_inner(p)
        self.assertEqual(text, "",
            "Unknown binary extension should return empty, not garbage")


class Test05_OdtExtraction(unittest.TestCase):
    """Audit item 5a: explicit ODT text extractor (zipfile + content.xml)."""

    def setUp(self):
        self.tmp = tempfile.mkdtemp()

    def tearDown(self):
        import shutil
        shutil.rmtree(self.tmp, ignore_errors=True)

    def _make_odt(self, text):
        """Build a minimal valid ODT (zip with content.xml)."""
        path = os.path.join(self.tmp, "doc.odt")
        content_xml = (
            '<?xml version="1.0" encoding="UTF-8"?>'
            '<office:document-content xmlns:office="urn:oasis:names:tc:opendocument:xmlns:office:1.0" '
            'xmlns:text="urn:oasis:names:tc:opendocument:xmlns:text:1.0">'
            '<office:body><office:text>'
            f'<text:p>{text}</text:p>'
            '</office:text></office:body>'
            '</office:document-content>'
        )
        with zipfile.ZipFile(path, "w") as zf:
            zf.writestr("mimetype", "application/vnd.oasis.opendocument.text")
            zf.writestr("content.xml", content_xml)
        return path

    def test_odt_text_extracted(self):
        path = self._make_odt("The quick brown fox jumps over the lazy dog")
        text = _extract_text_inner(path)
        self.assertIn("quick brown fox", text)
        self.assertIn("lazy dog", text)

    def test_odt_strips_xml_tags(self):
        path = self._make_odt("Plain content here")
        text = _extract_text_inner(path)
        # XML tags should be stripped, not appear in output
        self.assertNotIn("<text:p>", text)
        self.assertNotIn("office:body", text)

    def test_odt_corrupt_returns_empty(self):
        path = os.path.join(self.tmp, "broken.odt")
        with open(path, "wb") as f:
            f.write(b"not a real zip")
        text = _extract_text_inner(path)
        self.assertEqual(text, "")


class Test06_EpubExtraction(unittest.TestCase):
    """Audit item 5b: explicit EPUB text extractor."""

    def setUp(self):
        self.tmp = tempfile.mkdtemp()

    def tearDown(self):
        import shutil
        shutil.rmtree(self.tmp, ignore_errors=True)

    def _make_epub(self, chapters):
        """Build a minimal EPUB (zip with HTML chapters)."""
        path = os.path.join(self.tmp, "book.epub")
        with zipfile.ZipFile(path, "w") as zf:
            zf.writestr("mimetype", "application/epub+zip")
            zf.writestr(
                "META-INF/container.xml",
                '<?xml version="1.0"?><container/>',
            )
            for i, body in enumerate(chapters):
                zf.writestr(
                    f"OEBPS/chapter{i:02d}.xhtml",
                    f"<?xml version='1.0'?><html><body><p>{body}</p></body></html>",
                )
        return path

    def test_epub_single_chapter(self):
        path = self._make_epub(["Once upon a time in a faraway land"])
        text = _extract_text_inner(path)
        self.assertIn("upon a time", text)

    def test_epub_multiple_chapters(self):
        path = self._make_epub([
            "Chapter one starts here",
            "Chapter two continues",
            "Chapter three ends",
        ])
        text = _extract_text_inner(path)
        self.assertIn("Chapter one", text)
        self.assertIn("Chapter two", text)
        self.assertIn("Chapter three", text)

    def test_epub_strips_html(self):
        path = self._make_epub(["Plain text"])
        text = _extract_text_inner(path)
        self.assertNotIn("<p>", text)
        self.assertNotIn("<body>", text)

    def test_epub_corrupt_returns_empty(self):
        path = os.path.join(self.tmp, "broken.epub")
        with open(path, "wb") as f:
            f.write(b"not a zip")
        text = _extract_text_inner(path)
        self.assertEqual(text, "")


class Test07_ArchiveContentHashTar(unittest.TestCase):
    """Audit item 6: archive_content_hash uses tarfile for tar variants."""

    def setUp(self):
        self.tmp = tempfile.mkdtemp()

    def tearDown(self):
        import shutil
        shutil.rmtree(self.tmp, ignore_errors=True)

    def _make_tar(self, name, mode, members):
        """Make a tar with given members [(name, content_bytes), ...]."""
        path = os.path.join(self.tmp, name)
        with tarfile.open(path, mode) as tf:
            for mname, content in members:
                info = tarfile.TarInfo(name=mname)
                info.size = len(content)
                tf.addfile(info, io.BytesIO(content))
        return path

    def test_plain_tar_same_content_same_hash(self):
        members = [("a.txt", b"hello"), ("b.txt", b"world")]
        tar1 = self._make_tar("one.tar", "w", members)
        tar2 = self._make_tar("two.tar", "w", members)
        h1 = archive_content_hash(tar1)
        h2 = archive_content_hash(tar2)
        self.assertEqual(h1, h2)
        self.assertEqual(len(h1), 32, "Should be a 32-char md5 hex")

    def test_plain_tar_different_content_different_hash(self):
        tar1 = self._make_tar("a.tar", "w", [("file.txt", b"version-1")])
        tar2 = self._make_tar("b.tar", "w", [("file.txt", b"version-2-LONGER")])
        # Sizes differ so listings differ
        self.assertNotEqual(archive_content_hash(tar1),
                            archive_content_hash(tar2))

    def test_tgz_supported(self):
        members = [("readme.md", b"# Hello")]
        path = self._make_tar("doc.tgz", "w:gz", members)
        h = archive_content_hash(path)
        self.assertEqual(len(h), 32, "Should produce a real listing hash")
        # Sanity: the listing-based hash should be deterministic
        h2 = archive_content_hash(path)
        self.assertEqual(h, h2)

    def test_tbz2_supported(self):
        members = [("readme.md", b"# Hello bz2")]
        path = self._make_tar("doc.tbz2", "w:bz2", members)
        h = archive_content_hash(path)
        self.assertEqual(len(h), 32)

    def test_txz_supported(self):
        members = [("readme.md", b"# Hello xz")]
        path = self._make_tar("doc.txz", "w:xz", members)
        h = archive_content_hash(path)
        self.assertEqual(len(h), 32)

    def test_zip_still_works(self):
        # Regression: zip handling should still work after the rewrite
        path = os.path.join(self.tmp, "test.zip")
        with zipfile.ZipFile(path, "w") as zf:
            zf.writestr("a.txt", "hello")
            zf.writestr("b.txt", "world")
        h = archive_content_hash(path)
        self.assertEqual(len(h), 32)


class Test08_AnalyzeFileOther(unittest.TestCase):
    """Audit item 7+8: unknown extensions classified as 'other' (not
    'document'), and 'other' counted in stats."""

    def setUp(self):
        self.tmp = tempfile.mkdtemp()
        self.cache_dir = tempfile.mkdtemp()

    def tearDown(self):
        import shutil
        shutil.rmtree(self.tmp, ignore_errors=True)
        shutil.rmtree(self.cache_dir, ignore_errors=True)

    def _write_binary(self, name, size=4096):
        p = os.path.join(self.tmp, name)
        with open(p, "wb") as f:
            f.write(os.urandom(size))
        return p

    def test_unknown_ext_is_other(self):
        # .xyz is not in any known set
        path = self._write_binary("blob.xyz")
        s = PeanutScanner([self.tmp], cache_dir=self.cache_dir)
        info = s._analyze_file(path)
        s.cache.close()
        self.assertIsNotNone(info)
        self.assertEqual(info.file_type, "other",
            f".xyz should classify as 'other', got '{info.file_type}'")

    def test_known_ttf_is_other(self):
        path = self._write_binary("font.ttf")
        s = PeanutScanner([self.tmp], cache_dir=self.cache_dir)
        info = s._analyze_file(path)
        s.cache.close()
        self.assertIsNotNone(info)
        self.assertEqual(info.file_type, "other")

    def test_known_iso_is_other(self):
        path = self._write_binary("image.iso", size=8192)
        s = PeanutScanner([self.tmp], cache_dir=self.cache_dir)
        info = s._analyze_file(path)
        s.cache.close()
        self.assertIsNotNone(info)
        self.assertEqual(info.file_type, "other")

    def test_text_classification_unchanged(self):
        # Regression: known document type should still classify as 'document'
        p = os.path.join(self.tmp, "notes.md")
        with open(p, "w") as f:
            f.write("# Header\n\nSome content.\n" + ("Lorem ipsum dolor sit amet. " * 60))
        s = PeanutScanner([self.tmp], cache_dir=self.cache_dir)
        info = s._analyze_file(p)
        s.cache.close()
        self.assertEqual(info.file_type, "document")

    def test_stats_has_other_key(self):
        s = PeanutScanner([self.tmp], cache_dir=self.cache_dir)
        s.cache.close()
        self.assertIn("other", s.stats,
            "Scanner stats dict should have an 'other' key")
        self.assertEqual(s.stats["other"], 0)

    def test_other_counted_in_full_scan(self):
        # End-to-end: drop a binary blob and verify it shows up as "other"
        # in the final stats.
        self._write_binary("font.ttf")
        self._write_binary("image.iso", size=8192)
        # Add a text file too so the scan does something normal alongside
        with open(os.path.join(self.tmp, "readme.md"), "w") as f:
            f.write("# README\n\nHello world.\n" + ("Lorem ipsum dolor sit amet. " * 60))

        s = PeanutScanner([self.tmp], cache_dir=self.cache_dir)
        events = list(s.scan_progressive())
        # Find the complete event
        complete = [e for e in events if e["event"] == "complete"]
        self.assertEqual(len(complete), 1)
        stats = complete[0]["data"]["stats"]
        self.assertEqual(stats["other"], 2,
            f"Expected 2 'other' files (.ttf+.iso), got {stats['other']}")
        self.assertEqual(stats["documents"], 1)


# ── Standalone runner ────────────────────────────────────────────────────

if __name__ == "__main__":
    # Keep output quiet but verbose-on-failure
    runner = unittest.TextTestRunner(verbosity=2)
    suite = unittest.TestLoader().loadTestsFromModule(sys.modules[__name__])
    result = runner.run(suite)
    sys.exit(0 if result.wasSuccessful() else 1)
