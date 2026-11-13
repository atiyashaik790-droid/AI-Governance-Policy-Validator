"""Bounded read-only App Service layout discovery; never read process environments."""

from pathlib import Path
import os
import shutil


class LayoutError(Exception):
    pass


def discover_layout(*, roots=None, processes=None, proc=Path("/proc"), environ=None):
    environ = os.environ if environ is None else environ
    cwd = Path.cwd()
    if processes is None:
        processes = []
        try:
            entries = sorted(
                (p for p in proc.iterdir() if p.name.isdigit()),
                key=lambda p: int(p.name),
            )[:256]
        except OSError:
            entries = []
        for entry in entries:
            try:
                # Read at most 16 KiB; never print command lines or read environ.
                with (entry / "cmdline").open("rb") as source:
                    argv = source.read(16384).decode(errors="replace").split("\0")
                target = next(
                    (
                        arg
                        for arg in argv
                        if arg
                        in {
                            "app.hosting:app",
                            "app.main:app",
                            "backend.app.hosting:app",
                            "backend.app.main:app",
                        }
                    ),
                    None,
                )
                if target and any(
                    "uvicorn" in arg or "gunicorn" in arg for arg in argv
                ):
                    processes.append(
                        {
                            "cwd": (entry / "cwd").resolve(strict=True),
                            "exe": (entry / "exe").resolve(strict=True),
                            "argv": argv,
                            "target": target,
                        }
                    )
            except (OSError, ValueError):
                continue

    def process_roots(process):
        base = Path(process["cwd"])
        candidates = [base]
        argv = process.get("argv", [])
        for flag in ("--app-dir", "--chdir"):
            for index, value in enumerate(argv):
                option = (
                    argv[index + 1]
                    if value == flag and index + 1 < len(argv)
                    else value[len(flag) + 1 :]
                    if value.startswith(flag + "=")
                    else None
                )
                if option:
                    candidates.append(base / option)
        return candidates

    active_roots = [root for process in processes for root in process_roots(process)]
    if roots is None:
        roots = [environ.get("APP_PATH"), cwd, Path("/home/site/wwwroot")]

    def packages(candidates):
        found = set()
        for candidate in candidates:
            if not candidate:
                continue
            for root in (Path(candidate), Path(candidate) / "backend"):
                try:
                    if all(
                        (root / "app" / name).is_file()
                        for name in (
                            "__init__.py",
                            "database.py",
                            "config.py",
                            "models.py",
                        )
                    ):
                        found.add(root.resolve())
                except OSError:
                    continue
        return found

    found = packages(active_roots) or packages(roots)
    if not found:
        raise LayoutError("RUNTIME_APP_PACKAGE_NOT_FOUND_IN_BOUNDED_ROOTS")
    if len(found) != 1:
        raise LayoutError("RUNTIME_APP_PACKAGE_LOCATION_AMBIGUOUS")
    root = found.pop()
    matching = [p for p in processes if root in packages(process_roots(p))]
    # Prefer the observed app process's venv interpreter or one adjacent to its
    # verified root. /proc/exe may resolve outside a venv, so it comes last.
    python_candidates = []
    for process in matching:
        argv = process.get("argv", [])
        if argv and Path(argv[0]).is_absolute() and "python" in Path(argv[0]).name:
            python_candidates.append(Path(argv[0]))
    for base in (root, root.parent):
        python_candidates.extend(
            base / name / "bin/python" for name in ("antenv", ".venv", "venv")
        )
    if environ.get("VIRTUAL_ENV"):
        python_candidates.append(Path(environ["VIRTUAL_ENV"]) / "bin/python")
    python_candidates.extend(Path(p["exe"]) for p in matching)
    for name in ("python", "python3"):
        executable = shutil.which(name, path=environ.get("PATH", ""))
        if executable:
            python_candidates.append(Path(executable))
    python = next(
        (
            p.absolute()
            for p in python_candidates
            if p.is_file() and os.access(p, os.X_OK)
        ),
        None,
    )
    if python is None:
        raise LayoutError("RUNTIME_PYTHON_EXECUTABLE_UNAVAILABLE")
    return {
        "working_directory": str(root),
        "package_location": str(root / "app"),
        "python_executable": str(python),
        "application_import_path": str(root),
        "evidence": "running_app_process"
        if packages(active_roots)
        else "verified_bounded_root",
        "startup_module": next(
            (p.get("target") for p in matching),
            "NOT_OBSERVED",
        ),
        "process_working_directory": next(
            (str(p["cwd"]) for p in matching),
            "NOT_OBSERVED",
        ),
    }
