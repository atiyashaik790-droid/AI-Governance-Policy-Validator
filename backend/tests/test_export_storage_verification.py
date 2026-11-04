"""Independent reader verifies actual bytes and rejects corruption or permission loss."""

import hashlib
import importlib.util
from pathlib import Path
from unittest.mock import MagicMock

import pytest
from azure.core import MatchConditions
from azure.core.exceptions import HttpResponseError

spec = importlib.util.spec_from_file_location(
    "storage_verification", Path(__file__).resolve().parents[2] / "scripts/verify_export_storage.py"
)
verification = importlib.util.module_from_spec(spec)
spec.loader.exec_module(verification)


@pytest.mark.parametrize("body,expected_status", [(b"export bytes", "PASS"), (b"corrupted bytes", "MISMATCH")])
def test_readback_hashes_storage_bytes_and_pins_etag(monkeypatch, body, expected_status):
    credential = MagicMock()
    service = MagicMock()
    monkeypatch.setattr("azure.identity.AzureCliCredential", credential)
    monkeypatch.setattr("azure.storage.filedatalake.DataLakeServiceClient", service)
    file = service.return_value.__enter__.return_value.get_file_system_client.return_value.get_file_client.return_value
    file.get_file_properties.return_value.size = len(body)
    file.get_file_properties.return_value.etag = "version-one"
    file.download_file.return_value.chunks.return_value = [body[:3], body[3:]]
    report = verification.verify(
        "https://example.dfs.core.windows.net",
        "reports",
        "tenant/export.json",
        hashlib.sha256(b"export bytes").hexdigest(),
        "explicit-tenant",
    )
    assert report["status"] == expected_status
    assert report["actual_sha256"] == hashlib.sha256(body).hexdigest()
    file.download_file.assert_called_once_with(etag="version-one", match_condition=MatchConditions.IfNotModified)
    credential.assert_called_once_with(tenant_id="explicit-tenant")
    file.upload_data.assert_not_called()
    file.delete_file.assert_not_called()


def test_reader_permission_failure_stays_unverified(monkeypatch):
    credential = MagicMock()
    service = MagicMock()
    monkeypatch.setattr("azure.identity.AzureCliCredential", credential)
    monkeypatch.setattr("azure.storage.filedatalake.DataLakeServiceClient", service)
    file = service.return_value.__enter__.return_value.get_file_system_client.return_value.get_file_client.return_value
    file.get_file_properties.side_effect = HttpResponseError("Private response must not be retained")
    report = verification.verify("https://example.dfs.core.windows.net", "reports", "tenant/export.json", "a" * 64, "explicit-tenant")
    assert report["status"] == "UNVERIFIED"
    assert "Private" not in str(report)
    file.download_file.assert_not_called()
