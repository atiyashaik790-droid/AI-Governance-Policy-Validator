"""Bounded local tests with inherited kernel network denial and a clean environment."""
import ctypes
import errno
import os
from pathlib import Path
import socket
import subprocess
import sys

ROOT = Path(__file__).resolve().parents[3]
OUT = Path(__file__).resolve().parent
class Arg(ctypes.Structure):
    _fields_ = [('arg', ctypes.c_uint), ('op', ctypes.c_uint), ('a', ctypes.c_uint64), ('b', ctypes.c_uint64)]
lib = ctypes.CDLL('libseccomp.so.2', use_errno=True)
lib.seccomp_init.restype = ctypes.c_void_p
lib.seccomp_init.argtypes = [ctypes.c_uint32]
lib.seccomp_syscall_resolve_name.argtypes = [ctypes.c_char_p]
lib.seccomp_rule_add.argtypes = [ctypes.c_void_p, ctypes.c_uint32, ctypes.c_int, ctypes.c_uint]
lib.seccomp_load.argtypes = [ctypes.c_void_p]
ctx = lib.seccomp_init(0x7fff0000)
assert ctx
for family in (socket.AF_INET, socket.AF_INET6):
    assert lib.seccomp_rule_add(ctx, 0x50000 | errno.EPERM, lib.seccomp_syscall_resolve_name(b'socket'), 1, Arg(0, 4, family, 0)) == 0
assert lib.seccomp_load(ctx) == 0
for family in (socket.AF_INET, socket.AF_INET6):
    try:
        socket.socket(family)
    except PermissionError:
        pass
    else:
        raise AssertionError('IP socket guard failed')
print('GUARD PASS: IPv4/IPv6 sockets denied by inherited seccomp; clean env; repository dotenv blocked', flush=True)
package_path = os.environ.get('PHASE6B_TEST_PACKAGE')
if package_path:
    assert Path(package_path).resolve().is_relative_to('/tmp')
    assert (Path(package_path) / 'app/protected_reviews.py').is_file()
    print('EXTRACTED PACKAGE ' + package_path, flush=True)
env = {'PATH': str(ROOT / '.venv/bin') + ':/usr/bin:/bin', 'HOME': '/tmp', 'TMPDIR': '/tmp',
       'PYTHONPATH': str(OUT / 'continued-guard') + ':' + (package_path or str(ROOT / 'backend')),
       'PYTHONDONTWRITEBYTECODE': '1', 'DATABASE_URL': 'sqlite://', 'PROVIDER_MODE': 'fixture', 'PII_MODE': 'regex'}
if package_path:
    env["PHASE6B_TEST_PACKAGE"] = package_path
name, *args = sys.argv[1:]
command = [str(ROOT / '.venv/bin/python'), '-B', '-m', 'pytest', *args, '-o', 'faulthandler_timeout=45', '--junitxml=' + str(OUT / (name + '.xml'))]
print('COMMAND ' + repr(command), flush=True)
with (OUT / (name + '.log')).open('w') as log:
    try:
        result = subprocess.run(command, cwd=ROOT, env=env, stdout=log, stderr=subprocess.STDOUT, timeout=480)
        code = result.returncode
    except subprocess.TimeoutExpired:
        code = 124
print('RESULT', code, flush=True)
print((OUT / (name + '.log')).read_text()[-6500:])
sys.exit(code)
