"""Operator preservation gates must detect DDL left by a failed migration."""
import importlib.util
from pathlib import Path


def harness():
    path = Path(__file__).resolve().parents[2] / "scripts/phase6b_approval_a.py"
    spec = importlib.util.spec_from_file_location("qualification_catalog_test", path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


class CatalogConnection:
    def __init__(self, index_rows):
        self.index_rows = index_rows

    def __enter__(self):
        return self

    def __exit__(self, *args):
        pass

    def connect(self):
        return self

    def execute(self, statement):
        if "FROM sys.indexes" in str(statement):
            return self.index_rows
        return []


def test_preservation_fingerprint_detects_index_leaked_by_failed_007():
    module = harness()
    baseline = module.catalog_fingerprint(CatalogConnection([]))
    leaked = CatalogConnection([("dbo", "human_review_cases", "ux_review_cases_tenant_id")])
    assert module.catalog_fingerprint(leaked) != baseline


def test_catalog_fingerprint_ignores_unordered_catalog_result_order():
    module = harness()
    rows = [("dbo", "table", "first"), ("dbo", "table", "second")]
    assert module.catalog_fingerprint(CatalogConnection(rows)) == module.catalog_fingerprint(CatalogConnection(rows[::-1]))
