"""Compatibility entry point: isolated QA packages, emulators only."""
from pathlib import Path
import sys,subprocess
if '--physical' in sys.argv:raise SystemExit('Use device_verify.py for explicitly authorized physical devices.')
raise SystemExit(subprocess.call([sys.executable,str(Path(__file__).with_name('device_verify.py')),*sys.argv[1:]]))
