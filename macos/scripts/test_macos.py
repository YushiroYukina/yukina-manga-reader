"""Run regression tests using the native Cocoa platform, without user library data."""
import os,sys,platform,subprocess
from pathlib import Path
root=Path(__file__).resolve().parents[1]
if sys.platform!='darwin' or platform.machine()!='arm64':
    raise SystemExit('Requires native arm64 macOS with a graphical session.')
env=os.environ.copy();env['PYTHONPATH']=str(root/'reader');env['QT_QPA_PLATFORM']='cocoa'
raise SystemExit(subprocess.call([sys.executable,'-m','unittest','discover','-s','reader/tests','-v'],cwd=root,env=env))
