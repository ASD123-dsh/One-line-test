import json
import os
import tempfile
import unittest
from datetime import datetime, timedelta
from pathlib import Path
from unittest.mock import patch

import rsa

from licensing.activation import (
    ActivationService,
    build_validity_seconds,
    describe_validity_duration,
    generate_activation_code,
    get_current_device_code,
    get_default_license_path,
    normalize_device_code,
    verify_activation_code,
)
from tools.activation_tool import save_activation_code_file


class ActivationTests(unittest.TestCase):
    def setUp(self):
        self.public_key, self.private_key = rsa.newkeys(512)
        self.device_code = "12345678-1234-5678-1234-567812345678"
        self.fixed_now = datetime(2026, 5, 11, 21, 0, 0)

    def test_generate_and_verify_legacy_activation_code(self):
        activation_code = generate_activation_code(self.device_code, self.private_key)

        self.assertTrue(
            verify_activation_code(self.device_code, activation_code, self.public_key)
        )

    def test_activation_code_rejects_different_device(self):
        activation_code = generate_activation_code(self.device_code, self.private_key)

        self.assertFalse(
            verify_activation_code(
                "87654321-4321-8765-4321-876543218765",
                activation_code,
                self.public_key,
            )
        )

    def test_time_limited_activation_code_verifies_before_expiry(self):
        activation_code = generate_activation_code(
            self.device_code,
            self.private_key,
            validity_seconds=build_validity_seconds(7, "days"),
            issued_at=self.fixed_now,
        )

        self.assertTrue(
            verify_activation_code(
                self.device_code,
                activation_code,
                self.public_key,
                now=self.fixed_now + timedelta(days=3),
            )
        )

    def test_time_limited_activation_code_rejects_after_expiry(self):
        activation_code = generate_activation_code(
            self.device_code,
            self.private_key,
            validity_seconds=build_validity_seconds(1, "days"),
            issued_at=self.fixed_now,
        )

        self.assertFalse(
            verify_activation_code(
                self.device_code,
                activation_code,
                self.public_key,
                now=self.fixed_now + timedelta(days=2),
            )
        )

    def test_activation_service_persists_valid_license(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            license_path = Path(temp_dir) / "activation_license.json"
            activation_code = generate_activation_code(
                self.device_code,
                self.private_key,
                validity_seconds=build_validity_seconds(7, "days"),
                issued_at=self.fixed_now,
            )

            service = ActivationService(
                public_key_pem=self.public_key.save_pkcs1().decode("ascii"),
                license_path=license_path,
                device_code_provider=lambda: self.device_code,
                now_provider=lambda: self.fixed_now,
            )

            success, message = service.activate(activation_code)

            self.assertTrue(success, message)
            self.assertTrue(service.is_activated())
            self.assertEqual(service.get_remaining_validity_text(), "7天")

    def test_activation_service_rejects_expired_license(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            license_path = Path(temp_dir) / "activation_license.json"
            activation_code = generate_activation_code(
                self.device_code,
                self.private_key,
                validity_seconds=build_validity_seconds(1, "days"),
                issued_at=self.fixed_now,
            )

            service = ActivationService(
                public_key_pem=self.public_key.save_pkcs1().decode("ascii"),
                license_path=license_path,
                device_code_provider=lambda: self.device_code,
                now_provider=lambda: self.fixed_now + timedelta(days=2),
            )

            success, message = service.activate(activation_code)

            self.assertFalse(success)
            self.assertIn("过期", message)

    def test_activation_service_rejects_malformed_record_without_crashing(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            license_path = Path(temp_dir) / "activation_license.json"
            license_path.write_text(
                json.dumps({"device_code": 123, "activation_code": []}),
                encoding="utf-8",
            )
            service = ActivationService(
                public_key_pem=self.public_key.save_pkcs1().decode("ascii"),
                license_path=license_path,
                device_code_provider=lambda: self.device_code,
            )

            self.assertFalse(service.is_activated())

    def test_atomic_save_failure_preserves_existing_license_file(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            license_path = Path(temp_dir) / "activation_license.json"
            original_content = '{"existing": true}'
            license_path.write_text(original_content, encoding="utf-8")
            activation_code = generate_activation_code(
                self.device_code,
                self.private_key,
            )
            service = ActivationService(
                public_key_pem=self.public_key.save_pkcs1().decode("ascii"),
                license_path=license_path,
                device_code_provider=lambda: self.device_code,
                now_provider=lambda: self.fixed_now,
            )

            with patch(
                "licensing.activation.os.replace",
                side_effect=OSError("replace failed"),
            ):
                success, message = service.activate(activation_code)

            self.assertFalse(success)
            self.assertIn("保存失败", message)
            self.assertEqual(license_path.read_text(encoding="utf-8"), original_content)
            self.assertEqual(list(license_path.parent.glob("*.tmp")), [])

    def test_normalize_device_code_formats_plain_hex(self):
        self.assertEqual(
            normalize_device_code("12345678123456781234567812345678"),
            "12345678-1234-5678-1234-567812345678",
        )

    def test_save_activation_code_file_writes_txt_content(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            output_path = Path(temp_dir) / "activation_code.txt"

            saved_path = save_activation_code_file(
                self.device_code,
                "TEST-CODE-123",
                "30天",
                "2026-06-10T12:00:00",
                output_path=output_path,
            )

            self.assertEqual(saved_path, output_path)
            content = output_path.read_text(encoding="utf-8")
            self.assertIn(self.device_code, content)
            self.assertIn("TEST-CODE-123", content)
            self.assertIn("30天", content)
            self.assertIn("2026-06-10T12:00:00", content)

    def test_activation_service_caches_device_code_lookup(self):
        call_count = {"value": 0}

        def provider():
            call_count["value"] += 1
            return self.device_code

        service = ActivationService(
            public_key_pem=self.public_key.save_pkcs1().decode("ascii"),
            license_path=Path(tempfile.gettempdir()) / "unused_activation_license.json",
            device_code_provider=provider,
        )

        self.assertEqual(service.get_device_code(), self.device_code)
        self.assertEqual(service.get_device_code(), self.device_code)
        self.assertEqual(call_count["value"], 1)

    def test_describe_validity_duration(self):
        self.assertEqual(describe_validity_duration(12, "hours"), "12小时")

    def test_default_license_path_lookup_has_no_directory_side_effect(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            appdata_path = Path(temp_dir) / "missing-appdata"
            with patch.dict(os.environ, {"APPDATA": str(appdata_path)}):
                license_path = get_default_license_path()

            self.assertEqual(
                license_path,
                appdata_path / "AD仪表一线通协议测试工具" / "activation_license.json",
            )
            self.assertFalse(license_path.parent.exists())

    def test_device_code_lookup_stops_after_first_valid_command(self):
        with patch(
            "licensing.activation._run_identifier_command",
            return_value=self.device_code,
        ) as command_mock:
            with patch("licensing.activation._read_windows_machine_guid") as registry_mock:
                device_code = get_current_device_code()

        self.assertEqual(device_code, self.device_code)
        command_mock.assert_called_once()
        registry_mock.assert_not_called()


if __name__ == "__main__":
    unittest.main()
