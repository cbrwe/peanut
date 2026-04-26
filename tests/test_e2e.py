"""
test_e2e.py
===========
End-to-end smoke test of the full scanner pipeline on a heterogeneous
fixture directory. This is the integration check: catalog → analyze →
exact duplicates → similar images → similar documents → complete event,
all firing correctly.

Run:  python3 tests/test_e2e.py
"""

import os
import sys
import tempfile
import unittest
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE.parent))

from scanner import PeanutScanner


def _make_image(path, size, color, variant=0, seed=None):
    """Make a textured (not solid-color) image so it has a distinctive phash.

    Solid-color JPEGs all produce nearly-identical perceptual hashes (phash
    captures structure, not color), so we need real texture to get distinct
    hashes. We seed an RNG and paint a deterministic gradient + noise pattern
    keyed on `seed`.
    """
    from PIL import Image
    import random as _r
    rng = _r.Random(seed if seed is not None else hash(color))
    img = Image.new("RGB", size, color)
    pixels = img.load()
    w, h = size
    # Paint a deterministic "structural" pattern: horizontal bands + scattered
    # high-contrast pixels keyed off `seed`. Different seeds → different phashes.
    for y in range(h):
        band = (y // 8) % 4
        shift = (band * 30) + rng.randint(-10, 10)
        for x in range(w):
            r = (color[0] + shift + ((x + y) % 13) * 5) % 256
            g = (color[1] + shift + ((x * 2 + y) % 11) * 7) % 256
            b = (color[2] + shift + ((x + y * 2) % 7) * 11) % 256
            pixels[x, y] = (r, g, b)
    # Apply additional perturbation per `variant` for near-duplicate testing
    if variant > 0:
        for i in range(min(variant, w)):
            pixels[i, i] = (255 - color[0], 255 - color[1], 255 - color[2])
    img.save(path, "JPEG", quality=85)


def _byte_copy(src, dst):
    with open(src, "rb") as fr, open(dst, "wb") as fw:
        fw.write(fr.read())


class TestE2EFullPipeline(unittest.TestCase):
    """One shot: build a directory with several duplicate cohorts, run a
    scan, verify every phase of the pipeline reports correctly."""

    @classmethod
    def setUpClass(cls):
        cls.tmp = tempfile.mkdtemp()
        cls.cache_dir = tempfile.mkdtemp()

        # === Images ===
        # Cohort 1: 3 byte-identical copies of red.jpg (exact dupes)
        red_path = os.path.join(cls.tmp, "red_orig.jpg")
        _make_image(red_path, (320, 320), (255, 50, 50), seed=1)
        for name in ["red_copy1.jpg", "red_copy2.jpg"]:
            _byte_copy(red_path, os.path.join(cls.tmp, name))

        # Cohort 2: 2 visually-similar but byte-different blue images.
        # Same seed = same base structure; different `variant` = small
        # pixel-level perturbation. Phashes should be close but not identical.
        _make_image(os.path.join(cls.tmp, "blue_a.jpg"),
                    (320, 320), (50, 50, 200), variant=0, seed=2)
        _make_image(os.path.join(cls.tmp, "blue_b.jpg"),
                    (320, 320), (50, 50, 200), variant=2, seed=2)

        # Cohort 3: 1 unique green image — different seed, different structure.
        _make_image(os.path.join(cls.tmp, "green_unique.jpg"),
                    (320, 320), (50, 200, 50), variant=0, seed=999)

        # === Documents ===
        # Cohort 4: 2 byte-identical text files
        long_text = ("# Annual Report\n\n"
                     "This document covers the fiscal year ending December. " * 30)
        a_path = os.path.join(cls.tmp, "report_a.md")
        with open(a_path, "w") as f:
            f.write(long_text)
        _byte_copy(a_path, os.path.join(cls.tmp, "report_b.md"))

        # Cohort 5: 1 unique YAML config (must be > MIN_FILE_SIZE = 1024 bytes)
        yaml_content = "# Configuration\nname: peanut\nversion: 1.0\n" + (
            "some_long_key_name: some_long_value_that_takes_space\n" * 30)
        with open(os.path.join(cls.tmp, "config.yaml"), "w") as f:
            f.write(yaml_content)

        # === Other (binary) ===
        # Cohort 6: 2 byte-identical "binary" .ttf files (will dedupe via md5)
        ttf_a = os.path.join(cls.tmp, "font_a.ttf")
        with open(ttf_a, "wb") as f:
            f.write(b"\x00\x01\x00\x00" + os.urandom(2048))
        _byte_copy(ttf_a, os.path.join(cls.tmp, "font_b.ttf"))

        # === Run the scan ===
        cls.scanner = PeanutScanner([cls.tmp], cache_dir=cls.cache_dir)
        cls.events = list(cls.scanner.scan_progressive())
        cls.groups = [e["data"] for e in cls.events if e["event"] == "group"]
        cls.complete = [e for e in cls.events if e["event"] == "complete"][0]
        cls.stats = cls.complete["data"]["stats"]

    @classmethod
    def tearDownClass(cls):
        import shutil
        shutil.rmtree(cls.tmp, ignore_errors=True)
        shutil.rmtree(cls.cache_dir, ignore_errors=True)

    def test_pipeline_emits_complete_event(self):
        completes = [e for e in self.events if e["event"] == "complete"]
        self.assertEqual(len(completes), 1, "Should emit exactly one complete event")

    def test_pipeline_emits_status_events(self):
        statuses = [e for e in self.events if e["event"] == "status"]
        # Should have catalog + analyze + exact + similar_images + similar_docs
        # (the exact set of phases is a moving target but at least these)
        phases = {e["data"].get("phase") for e in statuses}
        self.assertIn("catalog", phases)
        self.assertIn("analyze", phases)
        self.assertIn("exact", phases)

    def test_total_files_counted(self):
        # 3 red + 2 blue + 1 green + 2 md + 1 yaml + 2 ttf = 11
        self.assertEqual(self.stats["total_files"], 11,
            f"Expected 11 files, got {self.stats['total_files']}")

    def test_per_type_counts(self):
        self.assertEqual(self.stats["images"], 6, "6 jpg images")
        self.assertEqual(self.stats["documents"], 3, "2 md + 1 yaml = 3 documents")
        self.assertEqual(self.stats["other"], 2, "2 ttf binaries")

    def test_exact_duplicate_groups(self):
        exact = [g for g in self.groups if g["match_type"] == "exact"]
        # Cohort 1 (3 reds), Cohort 4 (2 mds), Cohort 6 (2 ttfs) = 3 exact groups
        self.assertEqual(len(exact), 3,
            f"Expected 3 exact groups, got {len(exact)}: "
            f"{[(g['file_count'], [f['name'] for f in g['files']]) for g in exact]}")

    def test_red_group_has_three_files(self):
        # The red cohort should be one exact group with 3 files
        red_groups = [
            g for g in self.groups
            if g["match_type"] == "exact"
            and any("red" in f["name"] for f in g["files"])
        ]
        self.assertEqual(len(red_groups), 1)
        self.assertEqual(red_groups[0]["file_count"], 3)

    def test_similar_images_finds_blue_pair(self):
        # Cohort 2 (two perturbed blue images) should be a similar group
        similar_imgs = [
            g for g in self.groups
            if g["match_type"] == "similar"
            and any("blue" in f["name"] for f in g["files"])
        ]
        self.assertGreaterEqual(len(similar_imgs), 1,
            "Expected at least one 'similar' group containing blue images")

    def test_recoverable_bytes_positive(self):
        # We have several duplicates, so recoverable bytes should be > 0
        self.assertGreater(self.stats["recoverable_bytes"], 0)

    def test_recommended_keep_set_for_each_group(self):
        for g in self.groups:
            self.assertTrue(g["recommended_keep"],
                f"Group {g['group_id']} has no recommended_keep")
            # And it should be one of the files in the group
            paths = [f["path"] for f in g["files"]]
            self.assertIn(g["recommended_keep"], paths)

    def test_unique_files_not_grouped(self):
        # green_unique.jpg should NOT appear in any group
        all_grouped_names = {
            f["name"] for g in self.groups for f in g["files"]
        }
        self.assertNotIn("green_unique.jpg", all_grouped_names)
        self.assertNotIn("config.yaml", all_grouped_names)


class TestE2ECacheReuse(unittest.TestCase):
    """Re-running the scan should hit cache, not recompute hashes."""

    def setUp(self):
        self.tmp = tempfile.mkdtemp()
        self.cache_dir = tempfile.mkdtemp()
        # Make a few images
        for i in range(5):
            _make_image(
                os.path.join(self.tmp, f"img{i}.jpg"),
                (320, 320), (i * 50, 100, 200 - i * 30),
            )

    def tearDown(self):
        import shutil
        shutil.rmtree(self.tmp, ignore_errors=True)
        shutil.rmtree(self.cache_dir, ignore_errors=True)

    def test_second_scan_hits_cache(self):
        # First scan: cold cache
        s1 = PeanutScanner([self.tmp], cache_dir=self.cache_dir)
        list(s1.scan_progressive())
        first_hits = s1.stats["cached_hits"]

        # Second scan: warm cache
        s2 = PeanutScanner([self.tmp], cache_dir=self.cache_dir)
        list(s2.scan_progressive())
        second_hits = s2.stats["cached_hits"]

        self.assertEqual(first_hits, 0, "First scan should have 0 cache hits")
        self.assertEqual(second_hits, 5,
            f"Second scan should have 5 cache hits (one per file), got {second_hits}")


if __name__ == "__main__":
    runner = unittest.TextTestRunner(verbosity=2)
    suite = unittest.TestLoader().loadTestsFromModule(sys.modules[__name__])
    result = runner.run(suite)
    sys.exit(0 if result.wasSuccessful() else 1)
