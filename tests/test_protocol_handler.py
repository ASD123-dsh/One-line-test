import unittest

from protocol.protocol_handler import (
    PROTOCOL_CHANGZHOU_XINSIWEI,
    PROTOCOL_DONGWEI_GTXH,
    PROTOCOL_HANGZHOU_ANXIAN,
    PROTOCOL_RUILUN,
    PROTOCOL_WUXI_YIGE,
    PROTOCOL_XINRI,
    PROTOCOL_YADEA,
    PresetScenarios,
    ProtocolHandler,
    StatusBits,
)


class ProtocolHandlerTests(unittest.TestCase):
    def setUp(self):
        self.handler = ProtocolHandler()

    def test_ruilun_frame_matches_v156_mapping(self):
        status = StatusBits(protocol_name=PROTOCOL_RUILUN)
        status.distance_mode = True
        status.hall_fault = True
        status.motor_running = True
        status.one_key_enable = True
        status.current_a = -1
        status.hall_count = 0x1234
        status.soc_percent = 80
        status.lithium_soc_mode = True
        status.voltage_48v = True

        success, frame, error = self.handler.generate_frame_for_preview(status)

        self.assertTrue(success, error)
        self.assertEqual(frame, [8, 97, 8, 64, 64, 64, 255, 18, 52, 208, 2, 42])

    def test_hangzhou_frame_uses_sequence_and_pulse(self):
        status = StatusBits(protocol_name=PROTOCOL_HANGZHOU_ANXIAN)
        status.protocol_speed_limit = True
        status.p_gear_protect = True
        status.hall_fault = True
        status.current_a = 5
        status.hall_count = 0x0030
        status.voltage_percentage = 90
        status.voltage_48v = False
        status.voltage_60v = True

        success, frame, error = self.handler.generate_frame(status)

        self.assertTrue(success, error)
        self.assertEqual(frame, [8, 1, 6, 160, 96, 96, 5, 96, 144, 186, 100, 132])
        self.assertEqual(self.handler.get_current_hangzhou_sequence(), 2)

    def test_xinri_frame_uses_unsigned_point_two_amp_encoding(self):
        status = StatusBits(protocol_name=PROTOCOL_XINRI)
        status.p_gear_protect = True
        status.low_voltage_alarm = True
        status.hall_fault = True
        status.controller_fault = True
        status.cruise = True
        status.brake = True
        status.speed_mode = 4
        status.one_key_enable = True
        status.current_a = 10
        status.hall_count = 0x1234

        success, frame, error = self.handler.generate_frame_for_preview(status)

        self.assertTrue(success, error)
        self.assertEqual(frame, [8, 97, 12, 84, 160, 64, 50, 18, 52, 0, 0, 197])

    def test_wuxi_yige_frame_uses_fixed_device_and_seq(self):
        status = StatusBits(protocol_name=PROTOCOL_WUXI_YIGE)
        status.side_stand = True
        status.p_gear_protect = True
        status.walk_mode = True
        status.gear_four = True
        status.motor_running = True
        status.cloud_power_mode = True
        status.one_key_enable = True
        status.reverse = True
        status.current_a = 12
        status.hall_count = 0x0102
        status.soc_percent = 60
        status.lithium_soc_mode = True
        status.voltage_48v = False
        status.voltage_72v = True

        success, frame, error = self.handler.generate_frame_for_preview(status)

        self.assertTrue(success, error)
        self.assertEqual(frame, [16, 149, 10, 128, 192, 196, 12, 1, 2, 188, 16, 168])

    def test_yadea_frame_supports_percentage_current(self):
        status = StatusBits(protocol_name=PROTOCOL_YADEA)
        status.side_stand = True
        status.p_gear_protect = True
        status.hall_fault = True
        status.assist = True
        status.motor_running = True
        status.regen_charging = True
        status.speed_mode = 5
        status.current_70_flag = True
        status.electronic_brake = True
        status.current_a = -2
        status.hall_count = 0x002A
        status.soc_percent = 75
        status.current_percentage = 60

        success, frame, error = self.handler.generate_frame_for_preview(status)

        self.assertTrue(success, error)
        self.assertEqual(frame, [8, 97, 10, 66, 201, 2, 254, 0, 42, 75, 60, 73])

    def test_dongwei_gtxh_frame_supports_voltage_state_and_current_percentage(self):
        status = StatusBits(protocol_name=PROTOCOL_DONGWEI_GTXH)
        status.voltage_48v = True
        status.p_gear_protect = True
        status.hall_fault = True
        status.motor_running = True
        status.regen_charging = True
        status.speed_mode = 5
        status.current_70_flag = True
        status.side_stand = True
        status.electronic_brake = True
        status.current_a = -2
        status.hall_count = 0x002A
        status.soc_percent = 75
        status.current_percentage = 60

        success, frame, error = self.handler.generate_frame_for_preview(status)

        self.assertTrue(success, error)
        self.assertEqual(frame, [8, 97, 10, 64, 201, 194, 246, 0, 42, 75, 60, 131])

    def test_xinsiwei_preview_does_not_increment_sequence(self):
        status = PresetScenarios.changzhou_xinsiwei_normal_running()

        preview_success, preview_frame, preview_error = self.handler.generate_frame_for_preview(status)
        send_success, send_frame, send_error = self.handler.generate_frame(status)
        next_preview_success, next_preview_frame, next_preview_error = self.handler.generate_frame_for_preview(status)

        self.assertTrue(preview_success, preview_error)
        self.assertTrue(send_success, send_error)
        self.assertTrue(next_preview_success, next_preview_error)
        self.assertEqual(preview_frame, [48, 1, 0, 62, 126, 62, 15, 95, 114, 142, 64, 163])
        self.assertEqual(send_frame, [48, 1, 0, 62, 126, 62, 15, 95, 114, 142, 64, 163])
        self.assertEqual(next_preview_frame, [48, 2, 0, 0, 64, 0, 15, 33, 52, 80, 2, 58])

    def test_supported_protocols_have_byte_descriptions(self):
        for protocol_name in (
            PROTOCOL_RUILUN,
            PROTOCOL_XINRI,
            PROTOCOL_HANGZHOU_ANXIAN,
            PROTOCOL_CHANGZHOU_XINSIWEI,
            PROTOCOL_WUXI_YIGE,
            PROTOCOL_YADEA,
            PROTOCOL_DONGWEI_GTXH,
        ):
            descriptions = self.handler.get_byte_descriptions(protocol_name)
            self.assertEqual(len(descriptions), 12)


if __name__ == "__main__":
    unittest.main()
