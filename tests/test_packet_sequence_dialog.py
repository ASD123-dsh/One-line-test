import unittest

from gui.packet_sequence_dialog import (
    PACKET_SEQUENCE_FILE_MAGIC,
    PACKET_SEQUENCE_FILE_VERSION,
    build_packet_sequence_payload,
    load_packet_sequence_payload,
)


class PacketSequenceDialogTests(unittest.TestCase):
    def test_build_packet_sequence_payload_includes_metadata(self):
        frames = [
            [0x01, 0x02, 0x03],
            [0x10, 0x20, 0x30],
        ]

        payload = build_packet_sequence_payload(
            frames,
            frame_length=3,
            dialog_title="杭州安显协议 包组配置",
            checksum_mode="xor",
            byte_descriptions=["A", "B", "C"],
        )

        self.assertEqual(payload["format"], PACKET_SEQUENCE_FILE_MAGIC)
        self.assertEqual(payload["version"], PACKET_SEQUENCE_FILE_VERSION)
        self.assertEqual(payload["frame_length"], 3)
        self.assertEqual(payload["frame_count"], 2)
        self.assertEqual(payload["frames"], frames)

    def test_build_packet_sequence_payload_rejects_invalid_container(self):
        for invalid_frames in (None, 123, "010203"):
            with self.subTest(invalid_frames=invalid_frames):
                with self.assertRaisesRegex(ValueError, "必须是帧列表"):
                    build_packet_sequence_payload(invalid_frames, frame_length=3)

    def test_load_packet_sequence_payload_accepts_legacy_frame_list(self):
        frames = [
            [0x01, 0x02, 0x03],
            [0x10, 0x20, 0x30],
        ]

        loaded = load_packet_sequence_payload(frames, expected_frame_length=3)

        self.assertEqual(loaded, frames)

    def test_load_packet_sequence_payload_rejects_length_mismatch(self):
        payload = {
            "format": PACKET_SEQUENCE_FILE_MAGIC,
            "version": PACKET_SEQUENCE_FILE_VERSION,
            "frame_length": 4,
            "frames": [[0x01, 0x02, 0x03, 0x04]],
        }

        with self.assertRaises(ValueError):
            load_packet_sequence_payload(payload, expected_frame_length=3)

    def test_load_packet_sequence_payload_rejects_unsupported_version(self):
        for invalid_version in (PACKET_SEQUENCE_FILE_VERSION + 1, True, "1"):
            with self.subTest(invalid_version=invalid_version):
                payload = {
                    "format": PACKET_SEQUENCE_FILE_MAGIC,
                    "version": invalid_version,
                    "frame_length": 3,
                    "frame_count": 1,
                    "frames": [[0x01, 0x02, 0x03]],
                }

                with self.assertRaisesRegex(ValueError, "不支持的包组文件版本"):
                    load_packet_sequence_payload(payload, expected_frame_length=3)

    def test_load_packet_sequence_payload_rejects_invalid_frames_container(self):
        invalid_containers = (123, "not-a-frame-list", {"frame": [1, 2, 3]})

        for invalid_frames in invalid_containers:
            with self.subTest(invalid_frames=invalid_frames):
                payload = {
                    "format": PACKET_SEQUENCE_FILE_MAGIC,
                    "version": PACKET_SEQUENCE_FILE_VERSION,
                    "frame_length": 3,
                    "frames": invalid_frames,
                }

                with self.assertRaisesRegex(ValueError, "frames 字段必须是帧列表"):
                    load_packet_sequence_payload(payload, expected_frame_length=3)

    def test_load_packet_sequence_payload_rejects_frame_count_mismatch(self):
        payload = {
            "format": PACKET_SEQUENCE_FILE_MAGIC,
            "version": PACKET_SEQUENCE_FILE_VERSION,
            "frame_length": 3,
            "frame_count": 2,
            "frames": [[0x01, 0x02, 0x03]],
        }

        with self.assertRaisesRegex(ValueError, "frame_count 与实际帧数量不一致"):
            load_packet_sequence_payload(payload, expected_frame_length=3)

    def test_load_packet_sequence_payload_rejects_invalid_frame_count_type(self):
        for invalid_count in (True, -1, "1"):
            with self.subTest(invalid_count=invalid_count):
                payload = {
                    "format": PACKET_SEQUENCE_FILE_MAGIC,
                    "version": PACKET_SEQUENCE_FILE_VERSION,
                    "frame_length": 3,
                    "frame_count": invalid_count,
                    "frames": [[0x01, 0x02, 0x03]],
                }

                with self.assertRaisesRegex(ValueError, "frame_count 必须是非负整数"):
                    load_packet_sequence_payload(payload, expected_frame_length=3)

    def test_load_packet_sequence_payload_rejects_actual_frame_length_mismatch(self):
        payload = {
            "format": PACKET_SEQUENCE_FILE_MAGIC,
            "version": PACKET_SEQUENCE_FILE_VERSION,
            "frame_length": 3,
            "frame_count": 1,
            "frames": [[0x01, 0x02]],
        }

        with self.assertRaisesRegex(ValueError, "长度不匹配"):
            load_packet_sequence_payload(payload, expected_frame_length=3)

    def test_load_packet_sequence_payload_rejects_invalid_byte_values(self):
        invalid_values = (-1, 256, True, "01")

        for invalid_value in invalid_values:
            with self.subTest(invalid_value=invalid_value):
                payload = {
                    "format": PACKET_SEQUENCE_FILE_MAGIC,
                    "version": PACKET_SEQUENCE_FILE_VERSION,
                    "frame_length": 3,
                    "frame_count": 1,
                    "frames": [[0x01, invalid_value, 0x03]],
                }

                with self.assertRaisesRegex(ValueError, "0-255"):
                    load_packet_sequence_payload(payload, expected_frame_length=3)


if __name__ == "__main__":
    unittest.main()
