"""Retain licenses from the exact restored packages in the single executable."""
from pathlib import Path
import json
root=Path(__file__).resolve().parent
assets=json.loads((root/'obj'/'project.assets.json').read_text())
parts=['Temoraxis Windows: third-party notices.\nMicrosoft .NET / Windows Forms and Microsoft Edge WebView2 are third-party components.']
found=False
for folder in assets['packageFolders']:
 base=Path(folder)
 paths={base/name.lower() for name,item in assets['libraries'].items() if item.get('type')=='package'}
 paths.update(p for pattern in ['microsoft.netcore.app.runtime.win-x64/*','microsoft.windowsdesktop.app.runtime.win-x64/*'] for p in base.glob(pattern))
 for path in sorted(paths):
  for file in path.iterdir() if path.is_dir() else []:
   if file.is_file() and ('license' in file.name.lower() or 'thirdpartynotices' in file.name.lower()) and file.suffix.lower() not in ['.rtf','.xml']:
    parts.append('\n\n--- '+str(path.relative_to(base))+' / '+file.name+' ---\n'+file.read_text(errors='replace'))
    if path.parts[-2]=='microsoft.web.webview2':found=True
if not found:raise SystemExit('WebView2 license missing')
(root/'DEPENDENCY-NOTICES.txt').write_text('\n'.join(parts),encoding='utf-8')
