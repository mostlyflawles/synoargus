"""Runs every test file in its own process. Usage: python tests/run_all.py"""
import glob
import os
import subprocess
import sys

here = os.path.dirname(os.path.abspath(__file__))
failed = []
for path in sorted(glob.glob(os.path.join(here, "test_*.py"))):
    name = os.path.basename(path)
    r = subprocess.run([sys.executable, path], cwd=here, capture_output=True, text=True, timeout=600)
    ok = r.returncode == 0
    print(("ok   " if ok else "FAIL ") + name)
    if not ok:
        failed.append(name)
        print((r.stdout + r.stderr)[-3000:])
print(f"{len(failed)} failed" if failed else "all tests passed")
sys.exit(1 if failed else 0)
