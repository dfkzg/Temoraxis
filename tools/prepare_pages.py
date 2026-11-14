"""Build the public download site without publishing maintenance documents or duplicate assets in Git."""
from pathlib import Path
import shutil
ROOT=Path(__file__).resolve().parents[1]
output=ROOT/'dist'/'pages'
if output.exists():shutil.rmtree(output)
output.mkdir(parents=True)
for name in ['index.html','sitemap.xml','.nojekyll']:
    shutil.copy2(ROOT/'docs'/name,output/name)
for name in ['icon.svg','icon-512.png']:
    shutil.copy2(ROOT/'web-source'/name,output/name)
# Ownership verification files, if supplied by the site owner.
for path in (ROOT/'docs').glob('google*.html'):
    shutil.copy2(path,output/path.name)
print('Public download site built:',output)
