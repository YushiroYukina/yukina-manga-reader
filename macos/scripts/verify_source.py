"""Verify the published source manifest without external dependencies."""
from pathlib import Path
import hashlib,json
root=Path(__file__).resolve().parents[1]
manifest=json.loads((root/'SOURCE_MANIFEST.json').read_text())
failed=[name for name,value in manifest.items() if not (root/name).is_file() or hashlib.sha256((root/name).read_bytes()).hexdigest()!=value]
if failed:raise SystemExit('Integrity failed: '+', '.join(failed))
print('Source integrity passed:',len(manifest),'files')
