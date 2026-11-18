"""Create standalone desktop HTML without PWA companion files."""
import html,re
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]
def standalone_html(name):
    source=(ROOT/'server'/'web'/name).read_text()
    source=re.sub(r'<link\b[^>]*rel="(?:manifest|icon|apple-touch-icon)"[^>]*>','',source)
    source=source.replace("if(location.protocol==='https:'&&!window.PlannerAndroid&&'serviceWorker'in navigator)","if(false)")
    notices=(ROOT/'server'/'web'/'THIRD-PARTY.txt').read_text()
    return source.replace('</body>','<details style="margin:16px"><summary>Лицензии компонентов</summary><pre style="white-space:pre-wrap">'+html.escape(notices)+'</pre></details></body>',1)
