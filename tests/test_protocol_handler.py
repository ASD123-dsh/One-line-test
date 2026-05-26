import unittest

from protocol.protocol_handler import (
    PROTOCOL_BATTERY_SINGLE_WIRE,
    PROTOCOL_CHANGZHOU_XINSIWEI,
    PROTOCOL_DONGWEI_GTXH,
    PROTOCOL_FZ_SIF,
    PROTOCOL_HANGZHOU_ANXIAN,
    PROTOCOL_LITHIUM_BMS,
    PROTOCOL_LUYUAN_BMS,
    PROTOCOL_RUILUN,
    PROTOCOL_WUXI_YIGE,
    PROTOCOL_XINCHI,
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

    def test_fz_sif_frame_matches_bl1832_y62_mapping(self):
        status = StatusBits(protocol_name=PROTOCOL_FZ_SIF)
        status.side_stand = True
        status.protocol_speed_limit = True
        status.p_gear_protect = True
        status.walk_mode = True
        status.hall_fault = True
        status.under_voltage = True
        status.motor_running = True
        status.regen_charging = True
        status.speed_mode = 2
        status.cloud_power_mode = True
        status.one_key_enable = True
        status.over_current = True
        status.speed_limit = True
        status.current_a = -2
        status.hall_count = 0x1234
        status.voltage_percentage = 75
        status.voltage_48v = False
        status.voltage_84v = True

        success, frame, error = self.handler.generate_frame_for_preview(status)

        self.assertTrue(success, error)
        self.assertEqual(frame, [8, 97, 14, 200, 74, 209, 254, 18, 52, 75, 32, 135])

    def test_fz_sif_rejects_unsupported_voltage_bits(self):
        status = StatusBits(protocol_name=PROTOCOL_FZ_SIF)
        status.voltage_48v = False
        status.voltage_80v = True

        success, frame, error = self.handler.generate_frame_for_preview(status)

        self.assertFalse(success)
        self.assertEqual(frame, [])
        self.assertIn("FZ-sif协议", error)

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

    def test_xinchi_frame_uses_sum_checksum_and_little_endian_fields(self):
        status = StatusBits(protocol_name=PROTOCOL_XINCHI)
        status.xinchi_charge_mos = True
        status.xinchi_discharge_mos = True
        status.xinchi_low_temp_fault = True
        status.xinchi_under_voltage_fault = True
        status.xinchi_bms_fault = True
        status.soc_percent = 88
        status.xinchi_cycle_count = 0x1234
        status.xinchi_temperature_c = -5
        status.xinchi_total_voltage_v = 54.3
        status.xinchi_total_current_a = 36

        success, frame, error = self.handler.generate_frame_for_preview(status)

        self.assertTrue(success, error)
        self.assertEqual(frame, [58, 213, 88, 52, 18, 251, 31, 2, 36, 237])

    def test_luyuan_bms_frame_uses_15_bytes_sum_checksum_and_signed_temperature_byte(self):
        status = StatusBits(protocol_name=PROTOCOL_LUYUAN_BMS)
        status.luyuan_charge_mos = True
        status.luyuan_discharge_mos = True
        status.luyuan_charge_enable = True
        status.luyuan_charger_connected = True
        status.soc_percent = 88
        status.luyuan_cycle_count = 0x1234
        status.luyuan_temperature_c = -5
        status.luyuan_max_cell_voltage_mv = 4210
        status.luyuan_min_cell_voltage_mv = 4088
        status.luyuan_current_a = 12.34
        status.luyuan_total_voltage_v = 54
        status.luyuan_soh_percent = 97

        success, frame, error = self.handler.generate_frame_for_preview(status)

        self.assertTrue(success, error)
        self.assertEqual(
            frame,
            [58, 216, 88, 52, 18, 251, 114, 16, 248, 15, 210, 4, 54, 97, 161],
        )
        self.assertEqual(
            self.handler.get_protocol_send_mode(PROTOCOL_LUYUAN_BMS),
            "uart",
        )

    def test_luyuan_bms_rejects_out_of_range_current(self):
        status = StatusBits(protocol_name=PROTOCOL_LUYUAN_BMS)
        status.luyuan_current_a = 400.0

        success, frame, error = self.handler.generate_frame_for_preview(status)

        self.assertFalse(success)
        self.assertEqual(frame, [])
        self.assertIn("绿源BMS电流", error)

    def test_lithium_bms_frame_uses_xor_checksum_and_signed_temperature_encoding(self):
        status = StatusBits(protocol_name=PROTOCOL_LITHIUM_BMS)
        status.lithium_bms_alarm_enable = True
        status.lithium_bms_high_temp_alarm = True
        status.lithium_bms_soh_low = True
        status.lithium_bms_short_circuit_fault = True
        status.lithium_bms_max_cell_voltage_v = 3.61
        status.soc_percent = 80
        status.lithium_bms_total_voltage_v = 54
        status.lithium_bms_max_temp_c = 28
        status.lithium_bms_min_temp_c = -5
        status.lithium_bms_cycle_count = 0x1234
        status.lithium_bms_min_cell_voltage_v = 3.42

        success, frame, error = self.handler.generate_frame_for_preview(status)

        self.assertTrue(success, error)
        self.assertEqual(frame, [3, 1, 212, 176, 80, 54, 28, 133, 18, 52, 157, 34])

    def test_battery_single_wire_frame_uses_six_bytes_and_sum_checksum(self):
        status = StatusBits(protocol_name=PROTOCOL_BATTERY_SINGLE_WIRE)
        status.soc_percent = 88

        success, frame, error = self.handler.generate_frame_for_preview(status)

        self.assertTrue(success, error)
        self.assertEqual(frame, [0, 88, 0, 0, 0, 88])
        self.assertEqual(
            self.handler.get_protocol_send_mode(PROTOCOL_BATTERY_SINGLE_WIRE),
            "uart",
        )

    def test_supported_protocols_have_byte_descriptions(self):
        for protocol_name in (
            PROTOCOL_RUILUN,
            PROTOCOL_FZ_SIF,
            PROTOCOL_XINRI,
            PROTOCOL_HANGZHOU_ANXIAN,
            PROTOCOL_CHANGZHOU_XINSIWEI,
            PROTOCOL_WUXI_YIGE,
            PROTOCOL_YADEA,
            PROTOCOL_DONGWEI_GTXH,
            PROTOCOL_XINCHI,
            PROTOCOL_LUYUAN_BMS,
            PROTOCOL_LITHIUM_BMS,
            PROTOCOL_BATTERY_SINGLE_WIRE,
        ):
            descriptions = self.handler.get_byte_descriptions(protocol_name)
            self.assertEqual(
                len(descriptions),
                self.handler.get_protocol_frame_length(protocol_name),
            )


if __name__ == "__main__":
    unittest.main()
