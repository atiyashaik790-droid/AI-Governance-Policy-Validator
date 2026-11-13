"""Only layout/import discovery: disposable files, no Azure or SQL connections."""

import ast
import json
import os
from pathlib import Path
import sys

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
import runtime_layout as layout
import verify_hosted_runtime as runtime


def package(root):
    (root / "app").mkdir(parents=True)
    for name in ("__init__.py", "database.py", "config.py", "models.py"):
        (root / "app" / name).touch()
    return root


def env():
    return {"PATH": str(Path(sys.executable).parent)}


@pytest.mark.parametrize("nested", [False, True])
def test_flat_and_backend_layout(tmp_path, nested):
    root = package(tmp_path / "backend" if nested else tmp_path)
    result = layout.discover_layout(roots=[tmp_path], processes=[], environ=env())
    assert result["working_directory"] == str(root)
    assert result["package_location"] == str(root / "app")
    assert result["application_import_path"] == str(root)
    assert Path(result["python_executable"]).is_file()


def test_live_process_cwd_overrides_stale_app_path(tmp_path):
    active = package(tmp_path / "active")
    stale = package(tmp_path / "stale")
    result = layout.discover_layout(
        roots=[stale],
        processes=[
            {
                "cwd": active,
                "exe": sys.executable,
                "argv": [sys.executable, "-m", "uvicorn", "app.hosting:app"],
                "target": "app.hosting:app",
            }
        ],
        environ=env(),
    )
    assert result["working_directory"] == str(active)
    assert result["evidence"] == "running_app_process"
    assert result["startup_module"] == "app.hosting:app"


def test_app_dir_option_and_venv_selection(tmp_path):
    root = package(tmp_path / "source")
    python = root / "antenv/bin/python"
    python.parent.mkdir(parents=True)
    python.symlink_to(sys.executable)
    value = layout.discover_layout(
        roots=[],
        processes=[
            {
                "cwd": tmp_path,
                "exe": sys.executable,
                "argv": ["uvicorn", "--app-dir", "source", "app.hosting:app"],
                "target": "app.hosting:app",
            }
        ],
        environ=env(),
    )
    assert value["working_directory"] == str(root)
    assert value["python_executable"] == str(python)


def test_missing_and_ambiguous_are_specific(tmp_path):
    with pytest.raises(layout.LayoutError, match="NOT_FOUND_IN_BOUNDED_ROOTS"):
        layout.discover_layout(roots=[tmp_path], processes=[], environ=env())
    package(tmp_path)
    package(tmp_path / "backend")
    with pytest.raises(layout.LayoutError, match="LOCATION_AMBIGUOUS"):
        layout.discover_layout(roots=[tmp_path], processes=[], environ=env())


def test_bounded_proc_reads_never_expose_command_or_environment(tmp_path):
    root = package(tmp_path / "source")
    proc = tmp_path / "proc"
    entry = proc / "12"
    entry.mkdir(parents=True)
    (entry / "cmdline").write_bytes(
        b"python\0-m\0uvicorn\0app.hosting:app\0--password=SENSITIVE\0"
    )
    (entry / "cwd").symlink_to(root)
    (entry / "exe").symlink_to(sys.executable)
    # An unreadable/dangling environ ensures no reliance on process secrets.
    (entry / "environ").symlink_to(tmp_path / "never-read")
    result = layout.discover_layout(roots=[], proc=proc, environ=env())
    assert result["working_directory"] == str(root)
    assert "SENSITIVE" not in json.dumps(result)


def test_bootstrap_switches_to_discovered_root_and_interpreter(monkeypatch, tmp_path):
    root = package(tmp_path / "backend")
    source = runtime.layout_bootstrap("MARK:")
    ast.parse(source)
    calls = []
    real_compile = compile

    def custom_compile(text, filename, mode):
        code = real_compile(text, filename, mode)
        if filename == "<read-only-layout-discovery>":
            # Inject deterministic candidates into the in-memory discovery only.
            wrapper = f"_discover = discover_layout\ndef discover_layout():\n return _discover(roots=[{str(tmp_path)!r}], processes=[], environ={env()!r})"
            return real_compile(text + "\n" + wrapper, filename, mode)
        return code

    def fake_execve(python, argv, environ):
        calls.append((python, argv, environ))
        ast.parse(argv[2])

    monkeypatch.chdir(tmp_path)
    monkeypatch.setattr(os, "execve", fake_execve)
    exec(source, {"compile": custom_compile})
    assert Path.cwd() == root
    assert calls[0][1][0] == calls[0][0]
    assert f"sys.path.insert(0, {str(root)!r})" in calls[0][1][2]
    assert calls[0][2]["PYTHONDONTWRITEBYTECODE"] == "1"


def test_layout_only_bootstrap_never_imports_runtime_or_connects(
    monkeypatch, tmp_path, capsys
):
    package(tmp_path / "backend")
    monkeypatch.chdir(tmp_path)
    monkeypatch.setenv("APP_PATH", str(tmp_path))
    monkeypatch.setattr(
        os, "execve", lambda *args: pytest.fail("No runtime execution for layout-only")
    )
    exec(runtime.layout_bootstrap("MARK:", layout_only=True), {})
    result = runtime.safe_layout(capsys.readouterr().out.encode(), "MARK:")
    assert result["package_location"] == str(tmp_path / "backend/app")


def test_no_python_is_specific(tmp_path):
    package(tmp_path)
    with pytest.raises(layout.LayoutError, match="PYTHON_EXECUTABLE_UNAVAILABLE"):
        layout.discover_layout(roots=[tmp_path], processes=[], environ={"PATH": ""})


def test_layout_record_cannot_become_runtime_proof():
    record = {
        "working_directory": "/verified/backend",
        "package_location": "/verified/backend/app",
        "python_executable": "/verified/antenv/bin/python",
        "application_import_path": "/verified/backend",
        "startup_module": "app.hosting:app",
        "password": "SENSITIVE",
    }
    raw = b"MARK:LAYOUT:" + json.dumps(record).encode() + b"\n"
    assert runtime.safe_result(raw, "MARK:") is None
    safe = runtime.safe_layout(raw, "MARK:")
    assert safe["working_directory"] == "/verified/backend"
    assert "SENSITIVE" not in json.dumps(safe)
