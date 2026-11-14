"""Validate the version and package public tracked files without secrets/build caches."""
import argparse,hashlib,json,re,subprocess,zipfile,xml.etree.ElementTree as ET
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]
p=argparse.ArgumentParser();p.add_argument('--validate-only',action='store_true');args=p.parse_args()
meta=json.loads((ROOT/'release.json').read_text());version=meta['version'];code=meta['versionCode']
if not re.fullmatch(r'\d+\.\d+\.\d+',version) or type(code) is not int:raise SystemExit('Invalid version metadata')
NS='{http://schemas.android.com/apk/res/android}'
for name in ['AndroidManifest.xml','AndroidManifest.gradle.xml']:
 manifest=ET.parse(ROOT/'android/app/src/main'/name).getroot()
 if manifest.attrib[NS+'versionName']!=version or int(manifest.attrib[NS+'versionCode'])!=code:raise SystemExit('Manifest version differs: '+name)
gradle=(ROOT/'android/app/build.gradle').read_text()
if "versionName '"+version+"'" not in gradle or not re.search(r'\bversionCode\s+'+str(code)+r'\b',gradle):raise SystemExit('Gradle version differs')
if json.loads((ROOT/'package.json').read_text())['version']!=version:raise SystemExit('package.json version differs')
if args.validate_only:print('Version validated:',version,code);raise SystemExit(0)
dist=ROOT/'dist';dist.mkdir(exist_ok=True);apk=dist/'timeaxis-android.apk'
if not apk.is_file():raise SystemExit('Build dist/timeaxis-android.apk first')
changelog=(ROOT/'CHANGELOG.md').read_text();match=re.search(r'^## '+re.escape(version)+r'\s*\n(.*?)(?=^## |\Z)',changelog,re.S|re.M)
notes=match.group(1).strip() if match else 'Улучшения и исправления.'
(dist/'release-notes.md').write_text(notes+'\n')
meta.update(apk='timeaxis-android.apk',apkSha256=hashlib.sha256(apk.read_bytes()).hexdigest(),notes=notes)
(dist/'latest.json').write_text(json.dumps(meta,ensure_ascii=False,indent=2)+'\n')
files=subprocess.check_output(['git','ls-files','-z'],cwd=ROOT).decode().split('\0')
with zipfile.ZipFile(dist/'timeaxis-complete-kit.zip','w',zipfile.ZIP_DEFLATED) as archive:
 for name in files:
  if not name:continue
  path=Path(name)
  if any(part in {'.git','node_modules','build','data','dist','__pycache__'} for part in path.parts):continue
  if path.suffix in {'.keystore','.jks','.p12','.pem','.pfx','.sqlite','.db','.pyc'} or path.name=='.env':raise SystemExit('Private file is tracked: '+name)
  archive.write(ROOT/path,'Timeaxis/'+name)
 archive.write(apk,'Timeaxis/releases/timeaxis-android.apk')
 archive.write(dist/'latest.json','Timeaxis/releases/latest.json')
names=['timeaxis-android.apk','timeaxis-complete-kit.zip','latest.json']
(dist/'SHA256SUMS.txt').write_text(''.join(hashlib.sha256((dist/name).read_bytes()).hexdigest()+'  '+name+'\n' for name in names))
print('Public release prepared:',version)
