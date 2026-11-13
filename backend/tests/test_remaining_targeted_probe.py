"""Execute the exact short SQL probe helper against disposable 008 locally."""
import importlib.util
from pathlib import Path

from app import protected_reviews as secure
import test_execution_008_application as application008
import test_protected_reviews as reviews

protected = application008.protected
template007 = application008.template007


def test_remaining_targeted_probe(protected):
    client, engine, factory = protected
    reviews.login(client, "admin")
    path = Path(__file__).resolve().parents[2] / "scripts/tests/phase6b_remaining_probe.py"
    spec = importlib.util.spec_from_file_location("remaining_targeted_probe", path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    checks = module.check_remaining(client, engine, factory, secure, "one", "admin")
    assert len(checks) == 4


def test_extracted_package_origin_when_requested():
    import os
    import app
    package = os.environ.get("PHASE6B_TEST_PACKAGE")
    if package:
        assert Path(app.__file__).resolve().parent == Path(package) / "app"
        assert Path(secure.__file__).resolve().parent == Path(package) / "app"
