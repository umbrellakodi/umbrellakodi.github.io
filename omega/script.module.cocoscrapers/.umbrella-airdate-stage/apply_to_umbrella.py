from pathlib import Path
import hashlib,json
stage=Path(__file__).resolve().parent
manifest=json.loads((stage/'manifest.json').read_text())
target=Path(manifest['target']).resolve()
expected=(stage.parent.parent/'plugin.video.umbrella').resolve()
if target!=expected:raise RuntimeError('Unexpected Umbrella target')
# Verify every input before writing any file, preserving concurrent user edits.
for item in manifest['files']:
 dest=(target/item['path']).resolve();src=(stage/item['path']).resolve()
 if not dest.is_relative_to(target) or not src.is_relative_to(stage):raise RuntimeError('Path outside project')
 before=hashlib.sha256(dest.read_bytes()).hexdigest() if dest.exists() else None
 if before!=item['before']:raise RuntimeError('File changed since preparation: '+str(dest))
 if hashlib.sha256(src.read_bytes()).hexdigest()!=item['after']:raise RuntimeError('Staged file changed: '+str(src))
for item in manifest['files']:
 dest=target/item['path'];dest.parent.mkdir(parents=True,exist_ok=True)
 dest.write_bytes((stage/item['path']).read_bytes())
print('Applied air-date support to',len(manifest['files']),'Umbrella files.')
