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
dist=ROOT/'dist';dist.mkdir(exist_ok=True);apk=dist/'temoraxis-android.apk'
if not apk.is_file():raise SystemExit('Build dist/temoraxis-android.apk first')
changelog=(ROOT/'CHANGELOG.md').read_text();match=re.search(r'^## '+re.escape(version)+r'\s*\n(.*?)(?=^## |\Z)',changelog,re.S|re.M)
notes=match.group(1).strip() if match else 'Улучшения и исправления.'
(dist/'release-notes.md').write_text(notes+'\n')
meta.update(apk='temoraxis-android.apk',apkSha256=hashlib.sha256(apk.read_bytes()).hexdigest(),notes=notes)
(dist/'latest.json').write_text(json.dumps(meta,ensure_ascii=False,indent=2)+'\n')
import runpy,shutil
runpy.run_path(str(ROOT/'stage_web.py'))
standalone_html=runpy.run_path(str(ROOT/'tools'/'user_html.py'))['standalone_html']
web_names=['planner.html','Start_page.html']
for name in web_names:(dist/name).write_text(standalone_html(name))
with zipfile.ZipFile(dist/'temoraxis-user-kit.zip','w',zipfile.ZIP_DEFLATED) as archive:
 for name in web_names:archive.write(dist/name,'Temoraxis/'+name)
 archive.write(apk,'Temoraxis/temoraxis-android.apk')
 archive.writestr('Temoraxis/README.txt',"Temoraxis "+version+"\n\nAndroid: установите temoraxis-android.apk поверх прежней версии.\nПК: распакуйте архив и откройте planner.html или Start_page.html в браузере.\nХранение данных локальных HTML зависит от браузера. Регулярно делайте экспорт JSON.\nДля общего хранилища страниц, облачной синхронизации и веб-уведомлений рекомендуем веб-версию: https://dfkzg.github.io/Temoraxis/app/planner.html\nСистемные фоновые будильники доступны в APK при выданных разрешениях.\nИсходники: https://github.com/dfkzg/Temoraxis\n")
names=['temoraxis-android.apk','temoraxis-user-kit.zip','latest.json','planner.html','Start_page.html']
(dist/'SHA256SUMS.txt').write_text(''.join(hashlib.sha256((dist/name).read_bytes()).hexdigest()+'  '+name+'\n' for name in names))
print('Public release prepared:',version)
