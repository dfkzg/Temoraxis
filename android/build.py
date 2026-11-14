"""Build the test APK with JDK 17+ and Android SDK platform/build-tools 35."""
from pathlib import Path
import argparse,os,shutil,subprocess,zipfile
ROOT=Path(__file__).resolve().parent
p=argparse.ArgumentParser();p.add_argument('--sdk',default=os.environ.get('ANDROID_HOME',''));p.add_argument('--compiler-jar');p.add_argument('--keystore');p.add_argument('--key-alias',default='androiddebugkey');p.add_argument('--output',default=str(ROOT/'build'/'planner-test.apk'));args=p.parse_args()
sdk=Path(args.sdk)
platform=sdk/'platforms'/'android-35'/'android.jar'
if not platform.exists():platform=sdk/'android-35'/'android.jar'
tools=sdk/'build-tools'/'35.0.0'
if not tools.exists():tools=sdk/'android-15'
def tool(name):return tools/(name+('.exe' if os.name=='nt' else ''))
if not platform.exists() or not tool('aapt2').exists():raise SystemExit('Install Android SDK Platform 35 and Build Tools 35.0.0; pass --sdk PATH.')
platform=platform.resolve();tools=tools.resolve()
build=ROOT/'build';build.mkdir(exist_ok=True)
for name in ['classes','dex','generated']:
 shutil.rmtree(build/name,ignore_errors=True);(build/name).mkdir()
def run(*args):subprocess.run([str(a) for a in args],check=True)
app=ROOT/'app'/'src'/'main'
run(tool('aapt2'),'compile','--dir',app/'res','-o',build/'resources.zip')
run(tool('aapt2'),'link','-I',platform,'--manifest',app/'AndroidManifest.xml','--java',build/'generated','--auto-add-overlay','-o',build/'resources.apk','-A',app/'assets',build/'resources.zip')
sources=list((app/'java').rglob('*.java'))+list((build/'generated').rglob('*.java'))
if args.compiler_jar:run('java','-jar',Path(args.compiler_jar).resolve(),'-encoding','UTF-8','-8','-classpath',platform,'-d',build/'classes',*sources)
else:run('javac','-encoding','UTF-8','-source','8','-target','8','-classpath',platform,'-d',build/'classes',*sources)
with zipfile.ZipFile(build/'classes.jar','w',zipfile.ZIP_DEFLATED) as jar:
 for file in (build/'classes').rglob('*.class'):jar.write(file,str(file.relative_to(build/'classes')))
run('java','-cp',tools/'lib'/'d8.jar','com.android.tools.r8.D8','--min-api','26','--lib',platform,'--output',build/'dex',build/'classes.jar')
unsigned=build/'unsigned.apk';shutil.copy2(build/'resources.apk',unsigned)
with zipfile.ZipFile(unsigned,'a',zipfile.ZIP_DEFLATED) as apk:
 for dex in (build/'dex').glob('*.dex'):apk.write(dex,dex.name)
run(tool('zipalign'),'-f','-p','4',unsigned,build/'aligned.apk')
key=Path(args.keystore).resolve() if args.keystore else ROOT/'debug.keystore'
os.environ.setdefault('ANDROID_KEYSTORE_PASSWORD','android');os.environ.setdefault('ANDROID_KEY_PASSWORD',os.environ['ANDROID_KEYSTORE_PASSWORD'])
if args.keystore and not key.exists():raise SystemExit('The configured signing keystore is missing; refusing to create a different signing key.')
if not key.exists():run('keytool','-genkeypair','-keystore',key,'-alias',args.key_alias,'-storepass:env','ANDROID_KEYSTORE_PASSWORD','-keypass:env','ANDROID_KEY_PASSWORD','-dname','CN=Android Debug,O=Planner Development,C=RU','-keyalg','RSA','-keysize','2048','-validity','10000')
output=Path(args.output).resolve();output.parent.mkdir(parents=True,exist_ok=True)
run('java','-jar',tools/'lib'/'apksigner.jar','sign','--ks',key,'--ks-key-alias',args.key_alias,'--ks-pass','env:ANDROID_KEYSTORE_PASSWORD','--key-pass','env:ANDROID_KEY_PASSWORD','--out',output,build/'aligned.apk')
run('java','-jar',tools/'lib'/'apksigner.jar','verify','--verbose',output)
print('APK:',output)
