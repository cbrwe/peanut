"""
test_correctness.py
===================
Regression test for the vectorized comparison code path in scanner.py.

The shipped (verified) version replaced the O(n^2) scalar inner loops with
numpy XOR + popcount. These tests prove the vectorized output exactly matches
a known-correct scalar reference for:

  * single-segment hashes (images, documents)
  * multi-segment hashes (videos: 5x256-bit, audio: 10x32-bit)
  * cross-bucket fallback (different segment counts)
  * unusual hex string lengths (zero-padded / truncated)

Run:  python3 tests/test_correctness.py
"""

import os
import random
import sys
import unittest
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE.parent))

import scanner
from scanner import (
    AUDIO_THRESHOLD, DOC_THRESHOLD, IMAGE_THRESHOLD, VIDEO_THRESHOLD,
    _hex_to_bits_array, _vectorized_pairs, audio_hash_distance, hamming,
    simhash_distance, video_hamming,
)


def _scalar_pairs_single(hashes, threshold, dist_fn):
    """Reference implementation: brute-force O(n^2) pair search."""
    out = []
    for i in range(len(hashes)):
        for j in range(i + 1, len(hashes)):
            d = dist_fn(hashes[i], hashes[j])
            if d <= threshold:
                out.append((i, j, d))
    return out


class TestVectorizedSingleSegment(unittest.TestCase):
    """Single-hash hamming distance via vectorized vs scalar reference."""

    def setUp(self):
        random.seed(42)

    def _gen_image_hashes(self, n, hex_len=16):
        """Generate n random hex hashes of given length."""
        return [
            "".join(random.choice("0123456789abcdef") for _ in range(hex_len))
            for _ in range(n)
        ]

    def test_image_hashes_small(self):
        hashes = self._gen_image_hashes(20, hex_len=16)
        ref = _scalar_pairs_single(hashes, IMAGE_THRESHOLD, hamming)
        packed = _hex_to_bits_array(hashes, expected_hex_len=16)
        vec = _vectorized_pairs(packed, IMAGE_THRESHOLD, divisor=1)
        # Order may differ — compare as sets of (i, j) and matching dist
        ref_set = {(i, j): d for i, j, d in ref}
        vec_set = {(i, j): d for i, j, d in vec}
        self.assertEqual(set(ref_set), set(vec_set),
            "Vectorized produces different (i,j) pairs than scalar")
        for k in ref_set:
            self.assertEqual(ref_set[k], vec_set[k],
                f"Distance mismatch at {k}: ref={ref_set[k]} vec={vec_set[k]}")

    def test_image_hashes_clustered(self):
        # Construct deliberately-similar hashes (small bit perturbations)
        base = "abcd" * 4  # 16 hex chars
        hashes = [base]
        # Single-bit flips of base
        for bit in [0, 4, 8, 12, 32, 60]:
            byte_idx = bit // 4
            new_char = format(int(base[byte_idx], 16) ^ (1 << (bit % 4)), "x")
            hashes.append(base[:byte_idx] + new_char + base[byte_idx + 1:])
        # Also wholly different ones
        hashes.extend(self._gen_image_hashes(10, hex_len=16))
        ref = _scalar_pairs_single(hashes, IMAGE_THRESHOLD, hamming)
        packed = _hex_to_bits_array(hashes, expected_hex_len=16)
        vec = _vectorized_pairs(packed, IMAGE_THRESHOLD, divisor=1)
        self.assertEqual(
            sorted((i, j, d) for i, j, d in ref),
            sorted((i, j, d) for i, j, d in vec),
        )

    def test_doc_hashes_simhash_128bit(self):
        hashes = self._gen_image_hashes(30, hex_len=32)  # 128-bit
        ref = _scalar_pairs_single(hashes, DOC_THRESHOLD, simhash_distance)
        packed = _hex_to_bits_array(hashes, expected_hex_len=32)
        vec = _vectorized_pairs(packed, DOC_THRESHOLD, divisor=1)
        ref_set = {(i, j) for i, j, _ in ref}
        vec_set = {(i, j) for i, j, _ in vec}
        self.assertEqual(ref_set, vec_set)

    def test_empty_input(self):
        packed = _hex_to_bits_array([], expected_hex_len=16)
        self.assertEqual(_vectorized_pairs(packed, 10, divisor=1), [])

    def test_single_input(self):
        packed = _hex_to_bits_array(["abcd1234abcd1234"], expected_hex_len=16)
        self.assertEqual(_vectorized_pairs(packed, 10, divisor=1), [])

    def test_unusual_hex_length_padded(self):
        # Some hashes too short — should be zero-padded, not crash
        hashes = ["abcd", "abcd", "abcd1234abcd1234"]
        packed = _hex_to_bits_array(hashes, expected_hex_len=16)
        self.assertEqual(packed.shape, (3, 8))
        # Pairs (0,1) should have distance 0 (both zero-padded the same way)
        pairs = _vectorized_pairs(packed, 100, divisor=1)
        pair_dists = {(i, j): d for i, j, d in pairs}
        self.assertEqual(pair_dists.get((0, 1)), 0)


class TestVectorizedMultiSegment(unittest.TestCase):
    """Multi-segment hashes (videos: 5 keyframes, audio: 10 segments)."""

    def setUp(self):
        random.seed(43)

    def _make_video_hash(self, n_segs=5, seg_hex=64):
        """Build a video phash: n_segs segments of seg_hex chars, ;-joined."""
        return ";".join(
            "".join(random.choice("0123456789abcdef") for _ in range(seg_hex))
            for _ in range(n_segs)
        )

    def _make_audio_fp(self, n_segs=10, seg_hex=8):
        return ";".join(
            "".join(random.choice("0123456789abcdef") for _ in range(seg_hex))
            for _ in range(n_segs)
        )

    def test_video_multi_segment_matches_scalar(self):
        # Build 15 fake videos all with 5 segments each
        from scanner import PeanutScanner

        class _FakeFile:
            def __init__(self, phash):
                self.phash = phash
                self.duration = 10.0  # all same so duration filter passes

        videos = [_FakeFile(self._make_video_hash(5, 64)) for _ in range(15)]
        # Add one nearly-identical pair (perturb one segment of video 0)
        v0 = videos[0].phash.split(";")
        v0[0] = "0" + v0[0][1:]  # tweak one nibble
        videos.append(_FakeFile(";".join(v0)))

        # Reference: brute force using video_hamming
        ref = []
        for i in range(len(videos)):
            for j in range(i + 1, len(videos)):
                d = video_hamming(videos[i].phash, videos[j].phash)
                if d <= VIDEO_THRESHOLD:
                    ref.append((i, j, d))

        # Vectorized via scanner internal
        s = PeanutScanner.__new__(PeanutScanner)
        # _multisegment_pairs only needs hashed list + params
        pairs = s._multisegment_pairs(
            videos, threshold=VIDEO_THRESHOLD,
            seg_hex_len=64, python_fallback=video_hamming,
        )

        ref_set = {(i, j) for i, j, _ in ref}
        vec_set = {(i, j) for i, j, _ in pairs}
        self.assertEqual(ref_set, vec_set,
            "Video multi-segment vectorized pairs don't match scalar")

    def test_audio_multi_segment_matches_scalar(self):
        from scanner import PeanutScanner

        class _FakeFile:
            def __init__(self, phash):
                self.phash = phash
                self.duration = 30.0

        # 12 audio fingerprints with 10 segments each
        audios = [_FakeFile(self._make_audio_fp(10, 8)) for _ in range(12)]

        ref = []
        for i in range(len(audios)):
            for j in range(i + 1, len(audios)):
                d = audio_hash_distance(audios[i].phash, audios[j].phash)
                if d <= AUDIO_THRESHOLD:
                    ref.append((i, j, d))

        s = PeanutScanner.__new__(PeanutScanner)
        pairs = s._multisegment_pairs(
            audios, threshold=AUDIO_THRESHOLD,
            seg_hex_len=8, python_fallback=audio_hash_distance,
        )

        ref_set = {(i, j) for i, j, _ in ref}
        vec_set = {(i, j) for i, j, _ in pairs}
        self.assertEqual(ref_set, vec_set,
            "Audio multi-segment vectorized pairs don't match scalar")

    def test_cross_bucket_fallback(self):
        """Videos with different segment counts — Python fallback path."""
        from scanner import PeanutScanner

        class _FakeFile:
            def __init__(self, phash):
                self.phash = phash
                self.duration = 10.0

        # 5 videos with 5 segments, 5 with 4 segments
        five_seg = [_FakeFile(self._make_video_hash(5, 64)) for _ in range(5)]
        four_seg = [_FakeFile(self._make_video_hash(4, 64)) for _ in range(5)]
        all_vids = five_seg + four_seg

        # Make one cross-bucket "match": copy the first 4 segments of v0
        # into a new 4-segment video.
        v0_segs = five_seg[0].phash.split(";")
        all_vids.append(_FakeFile(";".join(v0_segs[:4])))

        # Reference
        ref = []
        for i in range(len(all_vids)):
            for j in range(i + 1, len(all_vids)):
                d = video_hamming(all_vids[i].phash, all_vids[j].phash)
                if d <= VIDEO_THRESHOLD:
                    ref.append((i, j))

        s = PeanutScanner.__new__(PeanutScanner)
        pairs = s._multisegment_pairs(
            all_vids, threshold=VIDEO_THRESHOLD,
            seg_hex_len=64, python_fallback=video_hamming,
        )
        vec_set = {(i, j) for i, j, _ in pairs}
        self.assertEqual(set(ref), vec_set,
            "Cross-bucket pairs don't match scalar reference")


class TestPopcountLUT(unittest.TestCase):
    """Sanity-check the popcount lookup table itself."""

    def test_popcount_lut_correct(self):
        from scanner import _POPCOUNT_LUT
        for i in range(256):
            self.assertEqual(int(_POPCOUNT_LUT[i]), bin(i).count("1"),
                f"_POPCOUNT_LUT[{i}] is wrong")


if __name__ == "__main__":
    runner = unittest.TextTestRunner(verbosity=2)
    suite = unittest.TestLoader().loadTestsFromModule(sys.modules[__name__])
    result = runner.run(suite)
    sys.exit(0 if result.wasSuccessful() else 1)
