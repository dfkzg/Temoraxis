"""Stage web assets and wrap the original project PNG in a Windows ICO."""
from pathlib import Path
import runpy,struct
root=Path(__file__).resolve().parents[1]
runpy.run_path(str(root/'stage_web.py'))
png=(root/'web-source'/'icon-192.png').read_bytes()
(root/'windows'/'app.ico').write_bytes(struct.pack('<HHH',0,1,1)+struct.pack('<BBBBHHII',192,192,0,0,1,32,len(png),22)+png)
