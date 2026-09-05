"""
Security and validation tests for Who Growth Chart Analyzer.
"""
import os
import sys
import tempfile
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).parent.parent))

import growth_chart
from agents.base import PHIGuard, AuditTrail, SecurityException


class TestPathTraversalProtection:
    def test_rejects_parent_directory_traversal(self):
        with pytest.raises(ValueError, match="traversal"):
            growth_chart._validate_safe_path("../etc/passwd")

    def test_rejects_nested_traversal(self):
        with pytest.raises(ValueError, match="traversal"):
            growth_chart._validate_safe_path("data/../../etc/passwd")

    def test_rejects_null_bytes(self):
        with pytest.raises(ValueError, match="null bytes"):
            growth_chart._validate_safe_path("foo\x00bar.csv")

    def test_accepts_safe_relative_path(self):
        result = growth_chart._validate_safe_path("sample.csv")
        assert os.path.isabs(result)

    def test_accepts_safe_absolute_path(self):
        result = growth_chart._validate_safe_path(tempfile.gettempdir() + "/out.csv")
        assert os.path.isabs(result)


class TestProcessCsvValidation:
    def test_rejects_nonexistent_input(self, tmp_path):
        out = tmp_path / "out.csv"
        with pytest.raises(FileNotFoundError):
            growth_chart.process_csv("/nonexistent/file.csv", str(out))

    def test_rejects_empty_csv(self, tmp_path):
        inp = tmp_path / "empty.csv"
        inp.write_text("")
        out = tmp_path / "out.csv"
        with pytest.raises(ValueError, match="empty"):
            growth_chart.process_csv(str(inp), str(out))

    def test_processes_valid_csv(self, tmp_path):
        inp = tmp_path / "input.csv"
        inp.write_text("id,value,qty\nA,10,2\nB,20,3\n")
        out = tmp_path / "out.csv"
        results = growth_chart.process_csv(str(inp), str(out))
        assert len(results) == 2
        assert out.exists()


class TestAuditTrailRequiresKey:
    def test_raises_without_key(self, monkeypatch):
        monkeypatch.delenv("AUDIT_SECRET_KEY", raising=False)
        with pytest.raises(RuntimeError, match="AUDIT_SECRET_KEY"):
            AuditTrail()

    def test_accepts_key_via_env(self, monkeypatch):
        monkeypatch.setenv("AUDIT_SECRET_KEY", "test-key-123")
        trail = AuditTrail()
        assert trail.secret_key == b"test-key-123"

    def test_accepts_key_via_argument(self, monkeypatch):
        monkeypatch.delenv("AUDIT_SECRET_KEY", raising=False)
        trail = AuditTrail(secret_key="direct-key")
        assert trail.secret_key == b"direct-key"


class TestPHIGuard:
    def test_blocks_mrn(self):
        with pytest.raises(SecurityException):
            PHIGuard.assert_no_phi("Patient MRN-12345678")

    def test_blocks_ssn(self):
        with pytest.raises(SecurityException):
            PHIGuard.assert_no_phi("SSN: 123-45-6789")

    def test_blocks_phone(self):
        with pytest.raises(SecurityException):
            PHIGuard.assert_no_phi("Call 555-123-4567")

    def test_blocks_email(self):
        with pytest.raises(SecurityException):
            PHIGuard.assert_no_phi("Email: patient@hospital.org")

    def test_allows_safe_text(self):
        PHIGuard.assert_no_phi("Analytical specimen KEY-001 optimal")

    def test_redact_phi(self):
        result = PHIGuard.redact_phi("Patient MRN-12345678 is stable")
        assert "REDACTED" in result
        assert "MRN-12345678" not in result


class TestCalculateFunctions:
    def test_calculate_bmi_z_valid(self):
        result = growth_chart.calculate_bmi_z(70, 175, 60, "M")
        assert "bmi" in result
        assert result["bmi"] == pytest.approx(22.86, rel=0.01)

    def test_calculate_bmi_z_invalid_input(self):
        result = growth_chart.calculate_bmi_z(-5, 0, 60, "M")
        assert "error" in result

    def test_convert_hba1c_to_eag(self):
        result = growth_chart.convert_hba1c(hba1c_percent=6.5, eag_mgdl=None)
        assert "eag_mgdl" in result
        assert result["eag_mgdl"] == pytest.approx(140.0, rel=0.01)

    def test_convert_eag_to_hba1c(self):
        result = growth_chart.convert_hba1c(hba1c_percent=None, eag_mgdl=140.0)
        assert "hba1c_percent" in result
        assert result["hba1c_percent"] == pytest.approx(6.5, rel=0.01)

    def test_convert_hba1c_no_input(self):
        result = growth_chart.convert_hba1c(hba1c_percent=None, eag_mgdl=None)
        assert "error" in result
