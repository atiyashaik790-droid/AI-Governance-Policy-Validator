"""Never load repository dotenv secrets; permit disposable test files under /tmp."""
from pathlib import Path
from pydantic_settings.sources import DotEnvSettingsSource
_original = DotEnvSettingsSource._read_env_file

def _read_disposable_only(self, file_path):
    if Path(file_path).resolve().is_relative_to('/tmp'):
        return _original(self, file_path)
    return {}

DotEnvSettingsSource._read_env_file = _read_disposable_only

# Bind the package before pytest prepends source test directories.
import os
if os.environ.get("PHASE6B_TEST_PACKAGE"):
    import app
    assert Path(app.__file__).resolve().parent == Path(os.environ["PHASE6B_TEST_PACKAGE"]) / "app"
