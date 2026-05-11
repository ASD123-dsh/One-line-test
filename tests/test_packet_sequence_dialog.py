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


if __name__ == "__main__":
    unittest.main()
