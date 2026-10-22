"""Do not start a partially rebuilt family installation."""
from pathlib import Path
import ctypes
import hashlib
import subprocess
import sys

repo = Path(__file__).resolve().parents[1]
# Share the setup lock for the lifetime of the game, including launches during an update download.
kernel = ctypes.WinDLL('kernel32', use_last_error=True)
kernel.CreateMutexW.argtypes = [ctypes.c_void_p, ctypes.c_bool, ctypes.c_wchar_p]
kernel.CreateMutexW.restype = ctypes.c_void_p
kernel.WaitForSingleObject.argtypes = [ctypes.c_void_p, ctypes.c_uint32]
kernel.ReleaseMutex.argtypes = [ctypes.c_void_p]
kernel.CloseHandle.argtypes = [ctypes.c_void_p]
name = 'Local\\OpenSmashSetup' + hashlib.sha256(str(repo).lower().encode('utf-8')).hexdigest().upper()
handle = kernel.CreateMutexW(None, False, name)
if not handle or kernel.WaitForSingleObject(handle, 0) not in (0, 0x80):
    input('OpenSmash or its installer is already running. Close it first. Press Enter to close.')
    sys.exit(1)
if (repo / 'build/family-install-pending.json').exists():
    input('Setup was interrupted. Run Install OpenSmash again before playing. Press Enter to close.')
    sys.exit(1)
if (repo / 'artifacts/local/family-update/pending.json').exists():
    input('An update needs to finish. Run Update OpenSmash before playing. Press Enter to close.')
    sys.exit(1)
if (repo / 'artifacts/local/save-backups/pending.json').exists():
    input('Save import was interrupted. Run Import Save again before playing. Press Enter to close.')
    sys.exit(1)
try:
    result = subprocess.call([sys.executable, str(repo / 'scripts/run.py'), '--play', '--seconds', '0'], cwd=repo)
finally:
    kernel.ReleaseMutex(handle)
    kernel.CloseHandle(handle)
sys.exit(result)
