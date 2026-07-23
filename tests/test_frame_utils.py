import unittest

from protocol.frame_utils import normalize_frame, validate_frame_length


class FrameUtilsTests(unittest.TestCase):
    def test_normalize_frame_returns_independent_list(self):
        source = [0x01, 0x80, 0xFF]

        normalized = normalize_frame(source, expected_length=3)
        source[0] = 0

        self.assertEqual(normalized, [0x01, 0x80, 0xFF])

    def test_normalize_frame_rejects_invalid_byte_values(self):
        for frame in ([0, 256], [0, -1], [0, True], [0, "1"]):
            with self.subTest(frame=frame):
                with self.assertRaises(ValueError):
                    normalize_frame(frame)

    def test_normalize_frame_rejects_wrong_length(self):
        with self.assertRaises(ValueError):
            normalize_frame([1, 2], expected_length=3)

    def test_validate_frame_length_rejects_bool_and_non_positive_values(self):
        for value in (True, 0, -1, 1.5):
            with self.subTest(value=value):
                with self.assertRaises(ValueError):
                    validate_frame_length(value)


if __name__ == "__main__":
    unittest.main()
