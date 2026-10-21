from dataclasses import FrozenInstanceError, fields
import unittest

from protocol.definitions import (
    DEFAULT_SEND_INTERVAL_MS,
    MIN_SEND_INTERVAL_MS,
    PROTOCOL_DEFINITIONS,
    ProtocolDefinition,
)
from protocol.models import (
    ProtocolConfig as ModelProtocolConfig,
    StatusBits as ModelStatusBits,
)
from protocol.protocol_handler import (
    PROTOCOL_BATTERY_SINGLE_WIRE,
    PROTOCOL_CHANGZHOU_XINSIWEI,
    PROTOCOL_DONGWEI_GTXH,
    PROTOCOL_FZ_SIF,
    PROTOCOL_HANGZHOU_ANXIAN,
    PROTOCOL_JINGXIAN,
    PROTOCOL_LITHIUM_BMS,
    PROTOCOL_LISHEN_BMS,
    PROTOCOL_LUYUAN_BMS,
    PROTOCOL_RUILUN,
    PROTOCOL_TAILING_Y34B,
    PROTOCOL_TAILING_Y34F,
    PROTOCOL_SHENZHOUXING,
    PROTOCOL_SXSY,
    PROTOCOL_WUXI_YIGE,
    PROTOCOL_XINCHI,
    PROTOCOL_XINRI,
    PROTOCOL_YADEA,
    PROTOCOL_YOUYIBAO,
    PresetScenarios,
    ProtocolConfig,
    ProtocolHandler,
    SUPPORTED_PROTOCOLS,
    StatusBits,
)


class ProtocolHandlerTests(unittest.TestCase):
    def setUp(self):
        self.handler = ProtocolHandler()

    def test_protocol_models_remain_available_from_legacy_module(self):
        self.assertIs(ProtocolConfig, ModelProtocolConfig)
        self.assertIs(StatusBits, ModelStatusBits)

    def test_sxsy_fields_do_not_reorder_legacy_status_model(self):
        field_names = [field.name for field in fields(StatusBits)]
        percentage_index = field_names.index("current_percentage")

        self.assertEqual(field_names[percentage_index + 1], "voltage_24v")
        legacy_tail_index = field_names.index("lithium_bms_min_cell_voltage_v")
        self.assertEqual(
            field_names[legacy_tail_index:legacy_tail_index + 3],
            [
                "lithium_bms_min_cell_voltage_v",
                "sxsy_p_gear_state",
                "sxsy_three_speed",
            ],
        )

    def test_protocol_registry_is_immutable_and_drives_public_metadata(self):
        self.assertIsInstance(SUPPORTED_PROTOCOLS, list)
        self.assertEqual(SUPPORTED_PROTOCOLS, list(PROTOCOL_DEFINITIONS))

        for protocol_name, definition in PROTOCOL_DEFINITIONS.items():
            self.assertEqual(definition.name, protocol_name)
            self.assertEqual(
                self.handler.get_protocol_frame_length(protocol_name),
                definition.frame_length,
            )
            self.assertEqual(
                self.handler.get_protocol_checksum_mode(protocol_name),
                definition.checksum_mode,
            )
            self.assertEqual(
                self.handler.get_protocol_send_mode(protocol_name),
                definition.send_mode,
            )
            self.assertEqual(
                definition.min_send_interval_ms,
                MIN_SEND_INTERVAL_MS,
            )
            self.assertEqual(
                definition.default_send_interval_ms,
                1000 if protocol_name == PROTOCOL_LISHEN_BMS else DEFAULT_SEND_INTERVAL_MS,
            )
            self.assertTrue(
                callable(getattr(self.handler, definition.generator_method))
            )
            if definition.preview_generator_method is not None:
                self.assertTrue(
                    callable(
                        getattr(self.handler, definition.preview_generator_method)
                    )
                )

        with self.assertRaises(TypeError):
            PROTOCOL_DEFINITIONS["测试协议"] = PROTOCOL_DEFINITIONS[PROTOCOL_RUILUN]
        with self.assertRaises(FrozenInstanceError):
            PROTOCOL_DEFINITIONS[PROTOCOL_RUILUN].frame_length = 99

    def test_protocol_definition_rejects_invalid_interval_policy(self):
        with self.assertRaisesRegex(ValueError, "发送间隔配置无效"):
            ProtocolDefinition(
                name="测试协议",
                frame_length=12,
                checksum_mode="xor",
                send_mode="uart",
                generator_method="_generate_test_frame",
                min_send_interval_ms=9,
                max_send_interval_ms=5000,
                default_send_interval_ms=500,
            )

        with self.assertRaisesRegex(ValueError, "发送间隔配置无效"):
            ProtocolDefinition(
                name="测试协议",
                frame_length=12,
                checksum_mode="xor",
                send_mode="uart",
                generator_method="_generate_test_frame",
                min_send_interval_ms=1000,
                max_send_interval_ms=500,
                default_send_interval_ms=500,
            )

    def test_unknown_protocol_keeps_ruilun_fallback_behavior(self):
        unknown_status = StatusBits(protocol_name="未注册协议")
        ruilun_status = StatusBits(protocol_name=PROTOCOL_RUILUN)

        unknown_result = self.handler.generate_frame_for_preview(unknown_status)
        ruilun_result = self.handler.generate_frame_for_preview(ruilun_status)

        self.assertEqual(unknown_result, ruilun_result)
        self.assertEqual(self.handler.get_protocol_frame_length("未注册协议"), 12)
        self.assertEqual(self.handler.get_protocol_checksum_mode("未注册协议"), "xor")
        self.assertEqual(self.handler.get_protocol_send_mode("未注册协议"), "uart")

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

    def test_hangzhou_preview_does_not_increment_sequence(self):
        status = StatusBits(protocol_name=PROTOCOL_HANGZHOU_ANXIAN)

        first_preview = self.handler.generate_frame_for_preview(status)
        second_preview = self.handler.generate_frame_for_preview(status)
        send_result = self.handler.generate_frame(status)

        self.assertEqual(first_preview, second_preview)
        self.assertEqual(send_result, first_preview)
        self.assertEqual(self.handler.get_current_hangzhou_sequence(), 2)

    def test_sxsy_examples_match_specification(self):
        self.assertEqual(
            [self.handler.sxsy_pluscode_encrypt(value) for value in range(1, 5)],
            [0x64, 0x61, 0x7A, 0x67],
        )
        for sequence, expected in (
            (0x000, 0x7B),
            (0x0ED, 0x28),
            (0x158, 0x6A),
            (0xFFF, 0x17),
        ):
            with self.subTest(sequence=sequence):
                self.assertEqual(
                    self.handler.sxsy_pluscode_encrypt(sequence),
                    expected,
                )
        expected_frames = [
            [
                0x30, 0x01, 0x00, 0xA4, 0x64, 0x64,
                0x00, 0x64, 0x64, 0x64, 0x64, 0x95,
            ],
            [
                0x30, 0x02, 0x00, 0x71, 0x61, 0x61,
                0x00, 0x61, 0x61, 0x61, 0x61, 0x43,
            ],
            [
                0x30, 0x03, 0x00, 0x7A, 0x7C, 0x7A,
                0x00, 0x7A, 0x7A, 0x7A, 0x7A, 0x4F,
            ],
            [
                0x30, 0x04, 0x00, 0x6B, 0x67, 0x67,
                0x00, 0x68, 0xF7, 0x67, 0x67, 0xC0,
            ],
        ]
        statuses = [
            StatusBits(protocol_name=PROTOCOL_SXSY, soc_percent=0, hall_fault=True),
            StatusBits(
                protocol_name=PROTOCOL_SXSY,
                soc_percent=0,
                controller_fault=True,
            ),
            StatusBits(protocol_name=PROTOCOL_SXSY, soc_percent=0, speed_mode=2),
            StatusBits(
                protocol_name=PROTOCOL_SXSY,
                soc_percent=0,
                cruise=True,
                hall_count=400,
            ),
        ]

        for status, expected in zip(statuses, expected_frames):
            success, frame, error = self.handler.generate_frame(status)

            self.assertTrue(success, error)
            self.assertEqual(frame, expected)
            checksum = 0
            for value in frame[:11]:
                checksum ^= value
            self.assertEqual(frame[11], checksum)

        self.assertEqual(self.handler.get_current_sxsy_sequence(), 5)

    def test_sxsy_preview_does_not_increment_and_sequence_wraps(self):
        status = StatusBits(protocol_name=PROTOCOL_SXSY, soc_percent=0)
        self.handler.reset_sxsy_sequence(0x0FFF)

        first_preview = self.handler.generate_frame_for_preview(status)
        second_preview = self.handler.generate_frame_for_preview(status)
        send_result = self.handler.generate_frame(status)

        self.assertEqual(first_preview, second_preview)
        self.assertEqual(send_result, first_preview)
        preview_frame = first_preview[1]
        self.assertEqual(preview_frame[1], 0xFF)
        self.assertEqual(preview_frame[2] >> 4, 0x0F)
        self.assertEqual(self.handler.get_current_sxsy_sequence(), 0)

        success, wrapped_frame, error = self.handler.generate_frame(status)
        self.assertTrue(success, error)
        self.assertEqual(wrapped_frame[1], 0x00)
        self.assertEqual(wrapped_frame[2] >> 4, 0x00)
        self.assertEqual(self.handler.get_current_sxsy_sequence(), 1)

    def test_sxsy_p_gear_and_sign_magnitude_current(self):
        for state_code in (0x00, 0x0D, 0x0E, 0x0F):
            with self.subTest(state_code=state_code):
                status = StatusBits(
                    protocol_name=PROTOCOL_SXSY,
                    sxsy_p_gear_state=state_code,
                    current_a=-5,
                )

                success, frame, error = self.handler.generate_frame_for_preview(status)

                self.assertTrue(success, error)
                self.assertEqual(frame[2] & 0x0F, state_code)
                self.assertEqual(frame[6], 0x85)

        for current_a, expected_raw in ((-127, 0xFF), (0, 0x00), (127, 0x7F)):
            with self.subTest(current_a=current_a):
                status = StatusBits(
                    protocol_name=PROTOCOL_SXSY,
                    current_a=current_a,
                )
                success, frame, error = self.handler.generate_frame_for_preview(
                    status
                )
                self.assertTrue(success, error)
                self.assertEqual(frame[6], expected_raw)

        invalid_state = StatusBits(
            protocol_name=PROTOCOL_SXSY,
            sxsy_p_gear_state=0x01,
        )
        success, frame, error = self.handler.generate_frame(invalid_state)
        self.assertFalse(success)
        self.assertEqual(frame, [])
        self.assertIn("SXSY P档状态", error)
        self.assertEqual(self.handler.get_current_sxsy_sequence(), 1)

        invalid_current = StatusBits(
            protocol_name=PROTOCOL_SXSY,
            current_a=-128,
        )
        success, frame, error = self.handler.generate_frame(invalid_current)
        self.assertFalse(success)
        self.assertEqual(frame, [])
        self.assertIn("SXSY 运行电流", error)
        self.assertEqual(self.handler.get_current_sxsy_sequence(), 1)

    def test_sxsy_byte_descriptions_and_presets_are_protocol_specific(self):
        descriptions = self.handler.get_byte_descriptions(PROTOCOL_SXSY)

        self.assertEqual(len(descriptions), 12)
        self.assertIn("0x30", descriptions[0])
        self.assertIn("电压比例", descriptions[9])
        self.assertIn("SOC", descriptions[10])
        self.assertNotEqual(
            descriptions,
            self.handler.get_byte_descriptions(PROTOCOL_RUILUN),
        )

        for preset_factory in (
            PresetScenarios.sxsy_normal_running,
            PresetScenarios.sxsy_energy_recovery,
            PresetScenarios.sxsy_fault_scenario,
        ):
            with self.subTest(preset=preset_factory.__name__):
                status = preset_factory()
                self.assertEqual(status.protocol_name, PROTOCOL_SXSY)
                success, frame, error = self.handler.generate_frame_for_preview(
                    status
                )
                self.assertTrue(success, error)
                self.assertEqual(len(frame), 12)

    def test_sxsy_percentage_fields_reject_out_of_range_values(self):
        for field_name, value, error_text in (
            ("voltage_percentage", -1, "电压百分比"),
            ("voltage_percentage", 101, "电压百分比"),
            ("soc_percent", -1, "百分比输入"),
            ("soc_percent", 101, "百分比输入"),
        ):
            with self.subTest(field_name=field_name, value=value):
                status = StatusBits(protocol_name=PROTOCOL_SXSY)
                setattr(status, field_name, value)

                success, frame, error = self.handler.generate_frame(status)

                self.assertFalse(success)
                self.assertEqual(frame, [])
                self.assertIn(error_text, error)
                self.assertEqual(self.handler.get_current_sxsy_sequence(), 1)

    def test_sxsy_malformed_integer_fields_do_not_consume_sequence(self):
        for field_name in (
            "speed_mode",
            "hall_count",
            "voltage_percentage",
            "soc_percent",
        ):
            with self.subTest(field_name=field_name):
                status = StatusBits(protocol_name=PROTOCOL_SXSY)
                setattr(status, field_name, 1.5)

                success, frame, error = self.handler.generate_frame(status)

                self.assertFalse(success)
                self.assertEqual(frame, [])
                self.assertIn("必须是整数", error)
                self.assertEqual(self.handler.get_current_sxsy_sequence(), 1)

    def test_sxsy_status_bits_match_documented_positions(self):
        status2_fields = (
            ("hall_fault", 0x40),
            ("throttle_fault", 0x20),
            ("controller_fault", 0x10),
            ("under_voltage", 0x08),
            ("cruise", 0x04),
            ("assist", 0x02),
            ("motor_phase_loss", 0x01),
        )
        status3_fields = (
            ("sxsy_three_speed", 0x80),
            ("motor_running", 0x40),
            ("brake", 0x20),
            ("controller_protect", 0x10),
            ("regen_charging", 0x08),
            ("anti_runaway", 0x04),
        )
        status4_fields = (
            ("one_key_enable", 0x40),
            ("ekk_enable", 0x20),
            ("over_current", 0x10),
            ("stall_protect", 0x08),
            ("reverse", 0x04),
            ("electronic_brake", 0x02),
            ("speed_limit", 0x01),
        )
        plus_code = self.handler.sxsy_pluscode_encrypt(1)

        for byte_index, field_mappings in (
            (3, status2_fields),
            (4, status3_fields),
            (5, status4_fields),
        ):
            for field_name, expected_bit in field_mappings:
                with self.subTest(byte_index=byte_index, field_name=field_name):
                    status = StatusBits(protocol_name=PROTOCOL_SXSY)
                    setattr(status, field_name, True)
                    success, frame, error = self.handler.generate_frame_for_preview(
                        status
                    )
                    self.assertTrue(success, error)
                    self.assertEqual(
                        (frame[byte_index] - plus_code) & 0xFF,
                        expected_bit,
                    )

        for speed_mode in range(4):
            with self.subTest(speed_mode=speed_mode):
                status = StatusBits(
                    protocol_name=PROTOCOL_SXSY,
                    speed_mode=speed_mode,
                )
                success, frame, error = self.handler.generate_frame_for_preview(
                    status
                )
                self.assertTrue(success, error)
                self.assertEqual((frame[4] - plus_code) & 0x03, speed_mode)

        reserved_status = StatusBits(
            protocol_name=PROTOCOL_SXSY,
            walk_mode=True,
            current_70_flag=True,
        )
        success, frame, error = self.handler.generate_frame_for_preview(
            reserved_status
        )
        self.assertTrue(success, error)
        self.assertEqual((frame[3] - plus_code) & 0x80, 0)
        self.assertEqual((frame[5] - plus_code) & 0x80, 0)

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

    def test_xinri_current_accepts_exact_point_two_amp_byte_boundaries(self):
        for current_a in (51.0, -51.0):
            with self.subTest(current_a=current_a):
                status = StatusBits(
                    protocol_name=PROTOCOL_XINRI,
                    current_a=current_a,
                )

                success, frame, error = self.handler.generate_frame_for_preview(
                    status
                )

                self.assertTrue(success, error)
                self.assertEqual(frame[6], 0xFF)

    def test_xinri_current_rejects_out_of_range_values_instead_of_clipping(self):
        for current_a in (51.2, -51.2):
            with self.subTest(current_a=current_a):
                status = StatusBits(
                    protocol_name=PROTOCOL_XINRI,
                    current_a=current_a,
                )

                success, frame, error = self.handler.generate_frame_for_preview(
                    status
                )

                self.assertFalse(success)
                self.assertEqual(frame, [])
                self.assertIn("新日协议电流", error)
                self.assertIn("0.2A", error)

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

    def test_tailing_y34b_frame_supports_13_bytes_and_extended_status11(self):
        status = StatusBits(protocol_name=PROTOCOL_TAILING_Y34B)
        status.side_stand = True
        status.p_gear_protect = True
        status.tailing_national_standard = True
        status.walk_mode = True
        status.hall_fault = True
        status.assist = True
        status.motor_phase_loss = True
        status.gear_four = True
        status.motor_running = True
        status.brake = True
        status.regen_charging = True
        status.anti_runaway = True
        status.speed_mode = 2
        status.cloud_power_mode = True
        status.tailing_actual_speed_mode = True
        status.ekk_enable = True
        status.over_current = True
        status.stall_protect = True
        status.reverse = True
        status.electronic_brake = True
        status.current_a = -3
        status.speed_kmh = 23.4
        status.soc_percent = 88
        status.lithium_soc_mode = True
        status.voltage_48v = False
        status.voltage_72v = True
        status.tailing_dual_soc = True
        status.tailing_display_sleep = True
        status.tailing_speed_15kmh_warning = True
        status.tailing_brake_fault = True

        success, frame, error = self.handler.generate_frame_for_preview(status)

        self.assertTrue(success, error)
        self.assertEqual(frame, [8, 97, 11, 195, 238, 254, 253, 0, 234, 216, 16, 15, 97])

    def test_tailing_y34f_frame_supports_15_bytes_tcs_hdc_and_realtime_voltage(self):
        status = StatusBits(protocol_name=PROTOCOL_TAILING_Y34F)
        status.side_stand = True
        status.p_gear_protect = True
        status.tailing_national_standard = True
        status.walk_mode = True
        status.hall_fault = True
        status.throttle_fault = True
        status.controller_fault = True
        status.under_voltage = True
        status.cruise = True
        status.tailing_tire_pressure_low = True
        status.gear_four = True
        status.tailing_tcs_indicator = True
        status.brake = True
        status.tailing_hdc_indicator = True
        status.regen_charging = True
        status.speed_mode = 1
        status.cloud_power_mode = True
        status.tailing_actual_speed_mode = True
        status.tailing_dual_undervoltage = True
        status.over_current = True
        status.stall_protect = True
        status.reverse = True
        status.tailing_seat_state = 1
        status.current_a = 12
        status.speed_kmh = 45.6
        status.soc_percent = 77
        status.lithium_soc_mode = True
        status.voltage_48v = False
        status.voltage_84v = True
        status.tailing_display_voltage_from_data = True
        status.tailing_battery_over_temp = True
        status.tailing_battery_over_current = True
        status.tailing_battery_over_voltage = True
        status.tailing_dual_soc = True
        status.tailing_display_sleep = True
        status.tailing_speed_15kmh_warning = True
        status.tailing_brake_fault = True
        status.tailing_real_time_voltage_v = 65.8

        success, frame, error = self.handler.generate_frame_for_preview(status)

        self.assertTrue(success, error)
        self.assertEqual(frame, [8, 97, 11, 254, 249, 253, 12, 1, 200, 205, 64, 255, 2, 146, 191])

    def test_shenzhouxing_frame_supports_extended_status_and_time_fields(self):
        status = StatusBits(protocol_name=PROTOCOL_SHENZHOUXING)
        status.side_stand = True
        status.shenzhouxing_hdc = True
        status.p_gear_protect = True
        status.shenzhouxing_hhc = True
        status.shenzhouxing_tcs = True
        status.hall_fault = True
        status.throttle_fault = True
        status.controller_fault = True
        status.under_voltage = True
        status.cruise = True
        status.assist = True
        status.motor_phase_loss = True
        status.gear_four = True
        status.motor_running = True
        status.shenzhouxing_brake_fault = True
        status.controller_protect = True
        status.regen_charging = True
        status.anti_runaway = True
        status.speed_mode = 3
        status.shenzhouxing_bluetooth = True
        status.shenzhouxing_time_display = True
        status.shenzhouxing_4g_signal_indicator = True
        status.shenzhouxing_position_indicator = True
        status.stall_protect = True
        status.reverse = True
        status.brake = True
        status.speed_limit = True
        status.current_a = -7
        status.hall_count = 0x1234
        status.soc_percent = 93
        status.lithium_soc_mode = True
        status.voltage_48v = False
        status.voltage_72v = True
        status.shenzhouxing_signal_strength = 29
        status.shenzhouxing_time_hour = 21
        status.shenzhouxing_time_minute = 47
        status.shenzhouxing_push_assist = True
        status.shenzhouxing_p_blink = True

        success, frame, error = self.handler.generate_frame_for_preview(status)

        self.assertTrue(success, error)
        self.assertEqual(frame, [31, 238, 15, 255, 255, 255, 249, 18, 52, 221, 16, 237, 111, 192, 81])

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

    def test_youyibao_frame_uses_fixed_header_low_nibble_status1_and_percentage_fields(self):
        status = StatusBits(protocol_name=PROTOCOL_YOUYIBAO)
        status.p_gear_protect = True
        status.side_stand = True
        status.hall_fault = True
        status.assist = True
        status.motor_running = True
        status.regen_charging = True
        status.speed_mode = 2
        status.current_70_flag = True
        status.one_key_enable = True
        status.electronic_brake = True
        status.current_a = -2
        status.hall_count = 0x002A
        status.soc_percent = 75
        status.current_percentage = 60

        success, frame, error = self.handler.generate_frame_for_preview(status)

        self.assertTrue(success, error)
        self.assertEqual(frame, [8, 97, 12, 66, 74, 194, 254, 0, 42, 75, 60, 12])
        self.assertEqual(self.handler.get_protocol_send_mode(PROTOCOL_YOUYIBAO), "uart")

    def test_jingxian_frame_uses_12_bytes_pluscode_and_auto_sequence(self):
        status = StatusBits(protocol_name=PROTOCOL_JINGXIAN)
        status.side_stand = True
        status.p_gear_protect = True
        status.walk_mode = True
        status.hall_fault = True
        status.assist = True
        status.motor_running = True
        status.regen_charging = True
        status.speed_mode = 5
        status.current_70_flag = True
        status.one_key_enable = True
        status.electronic_brake = True
        status.current_a = -2
        status.hall_count = 0x002A
        status.voltage_percentage = 75
        status.current_percentage = 60

        preview_success, preview_frame, preview_error = self.handler.generate_frame_for_preview(status)
        send_success, send_frame, send_error = self.handler.generate_frame(status)
        next_preview_success, next_preview_frame, next_preview_error = self.handler.generate_frame_for_preview(status)

        self.assertTrue(preview_success, preview_error)
        self.assertTrue(send_success, send_error)
        self.assertTrue(next_preview_success, next_preview_error)
        self.assertEqual(
            preview_frame,
            [7, 1, 10, 59, 66, 59, 254, 121, 163, 196, 181, 27],
        )
        self.assertEqual(send_frame, preview_frame)
        self.assertEqual(
            next_preview_frame,
            [7, 2, 10, 64, 71, 64, 254, 126, 168, 201, 186, 19],
        )
        self.assertEqual(self.handler.get_protocol_send_mode(PROTOCOL_JINGXIAN), "uart")

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

    def test_dongwei_current_accepts_signed_point_two_amp_byte_boundaries(self):
        for current_a, expected_raw in ((-25.6, 0x80), (25.4, 0x7F)):
            with self.subTest(current_a=current_a):
                status = StatusBits(
                    protocol_name=PROTOCOL_DONGWEI_GTXH,
                    current_a=current_a,
                )

                success, frame, error = self.handler.generate_frame_for_preview(
                    status
                )

                self.assertTrue(success, error)
                self.assertEqual(frame[6], expected_raw)

    def test_dongwei_current_rejects_out_of_range_values_instead_of_clipping(self):
        for current_a in (-25.8, 25.6):
            with self.subTest(current_a=current_a):
                status = StatusBits(
                    protocol_name=PROTOCOL_DONGWEI_GTXH,
                    current_a=current_a,
                )

                success, frame, error = self.handler.generate_frame_for_preview(
                    status
                )

                self.assertFalse(success)
                self.assertEqual(frame, [])
                self.assertIn("东威协议电流", error)
                self.assertIn("0.2A", error)

    def test_scaled_current_keeps_existing_rounding_for_fractional_input(self):
        for protocol_name in (PROTOCOL_XINRI, PROTOCOL_DONGWEI_GTXH):
            with self.subTest(protocol_name=protocol_name):
                status = StatusBits(
                    protocol_name=protocol_name,
                    current_a=0.1,
                )

                success, frame, error = self.handler.generate_frame_for_preview(
                    status
                )

                self.assertTrue(success, error)
                self.assertEqual(frame[6], 0x00)

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

    def test_invalid_send_preserves_each_sequence_protocol_existing_semantics(self):
        xinsiwei_status = StatusBits(
            protocol_name=PROTOCOL_CHANGZHOU_XINSIWEI,
            speed_mode=4,
        )
        hangzhou_status = StatusBits(
            protocol_name=PROTOCOL_HANGZHOU_ANXIAN,
            speed_mode=4,
        )
        jingxian_status = StatusBits(
            protocol_name=PROTOCOL_JINGXIAN,
            speed_mode=8,
        )

        self.assertFalse(self.handler.generate_frame(xinsiwei_status)[0])
        self.assertFalse(self.handler.generate_frame(hangzhou_status)[0])
        self.assertFalse(self.handler.generate_frame(jingxian_status)[0])

        self.assertEqual(self.handler.get_current_xinsiwei_sequence(), 2)
        self.assertEqual(self.handler.get_current_hangzhou_sequence(), 1)
        self.assertEqual(self.handler.get_current_jingxian_sequence(), 1)

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
        """验证 0x00 数据头、测试默认字节、SOC 位置及累加校验和发送方式。"""
        status = StatusBits(protocol_name=PROTOCOL_BATTERY_SINGLE_WIRE)
        status.soc_percent = 88

        success, frame, error = self.handler.generate_frame_for_preview(status)

        self.assertTrue(success, error)
        self.assertEqual(frame, [0, 88, 1, 1, 1, 91])
        self.assertEqual(
            self.handler.get_protocol_checksum_mode(PROTOCOL_BATTERY_SINGLE_WIRE),
            "sum",
        )
        self.assertEqual(
            self.handler.get_protocol_send_mode(PROTOCOL_BATTERY_SINGLE_WIRE),
            "uart",
        )

    def test_battery_single_wire_sum_differs_from_xor_for_every_valid_soc(self):
        """遍历所有合法 SOC，独立计算校验并验证发送帧与预览帧一致。"""
        for soc in range(101):
            with self.subTest(soc=soc):
                status = StatusBits(
                    protocol_name=PROTOCOL_BATTERY_SINGLE_WIRE,
                    soc_percent=soc,
                )
                preview = self.handler.generate_frame_for_preview(status)
                sent = self.handler.generate_frame(status)

                self.assertEqual(sent, preview)
                success, frame, error = sent
                self.assertTrue(success, error)
                self.assertEqual(len(frame), 6)
                self.assertEqual(frame[0], 0x00)
                self.assertEqual(frame[1], soc)
                expected_xor = 0
                for value in frame[:5]:
                    expected_xor ^= value
                expected_sum = sum(frame[:5]) & 0xFF
                self.assertEqual(frame[5], expected_sum)
                self.assertNotEqual(frame[5], expected_xor)

    def test_battery_single_wire_presets_use_nonzero_test_defaults(self):
        """验证三个预设场景统一使用测试默认字节且保留原 SOC。"""
        for preset, expected_soc in (
            (PresetScenarios.battery_single_wire_normal_running, 80),
            (PresetScenarios.battery_single_wire_energy_recovery, 62),
            (PresetScenarios.battery_single_wire_fault_scenario, 15),
        ):
            with self.subTest(preset=preset.__name__):
                success, frame, error = self.handler.generate_frame(preset())
                self.assertTrue(success, error)
                self.assertEqual(
                    frame, [0, expected_soc, 1, 1, 1, expected_soc + 3]
                )

    def test_soc_fault_only_bypasses_range_for_protocols_that_encode_it(self):
        fault_protocols = {
            PROTOCOL_RUILUN,
            PROTOCOL_CHANGZHOU_XINSIWEI,
        }

        for protocol_name in SUPPORTED_PROTOCOLS:
            with self.subTest(protocol_name=protocol_name):
                status = StatusBits(
                    protocol_name=protocol_name,
                    soc_percent=101,
                    soc_fault=True,
                )

                success, frame, error = self.handler.generate_frame_for_preview(
                    status
                )

                if protocol_name in fault_protocols:
                    self.assertTrue(success, error)
                    self.assertTrue(frame)
                else:
                    self.assertFalse(success)
                    self.assertEqual(frame, [])
                    self.assertIn("0-100", error)

    def test_soc_range_still_applies_without_fault_encoding(self):
        for protocol_name in (
            PROTOCOL_RUILUN,
            PROTOCOL_CHANGZHOU_XINSIWEI,
        ):
            with self.subTest(protocol_name=protocol_name):
                status = StatusBits(
                    protocol_name=protocol_name,
                    soc_percent=-1,
                    soc_fault=False,
                )

                success, frame, error = self.handler.generate_frame_for_preview(
                    status
                )

                self.assertFalse(success)
                self.assertEqual(frame, [])
                self.assertIn("0-100", error)

    def test_current_rejects_non_numeric_values_without_crashing(self):
        for invalid_value in (True, "1", None):
            with self.subTest(invalid_value=invalid_value):
                success, frame, error = self.handler.generate_frame_for_preview(
                    StatusBits(
                        protocol_name=PROTOCOL_RUILUN,
                        current_a=invalid_value,
                    )
                )

                self.assertFalse(success)
                self.assertEqual(frame, [])
                self.assertIn("必须是数值", error)

    def test_generate_frame_rejects_wrong_status_type(self):
        for invalid_status in (None, {}, "status"):
            with self.subTest(invalid_status=invalid_status):
                success, frame, error = self.handler.generate_frame_for_preview(
                    invalid_status
                )

                self.assertFalse(success)
                self.assertEqual(frame, [])
                self.assertIn("StatusBits", error)

    def test_generate_frame_returns_error_for_malformed_status_field(self):
        status = StatusBits(protocol_name=PROTOCOL_RUILUN)
        status.speed_mode = "fast"

        success, frame, error = self.handler.generate_frame_for_preview(status)

        self.assertFalse(success)
        self.assertEqual(frame, [])
        self.assertIn("协议状态参数无效", error)

    def test_integer_current_protocol_rejects_fractional_amperes(self):
        success, frame, error = self.handler.generate_frame_for_preview(
            StatusBits(
                protocol_name=PROTOCOL_RUILUN,
                current_a=1.5,
            )
        )

        self.assertFalse(success)
        self.assertEqual(frame, [])
        self.assertIn("整数安培", error)

    def test_supported_protocols_have_byte_descriptions(self):
        for protocol_name in SUPPORTED_PROTOCOLS:
            descriptions = self.handler.get_byte_descriptions(protocol_name)
            self.assertEqual(
                len(descriptions),
                self.handler.get_protocol_frame_length(protocol_name),
            )


if __name__ == "__main__":
    unittest.main()
