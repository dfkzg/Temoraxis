import argparse,re,subprocess
from pathlib import Path
p=argparse.ArgumentParser();p.add_argument('apk');p.add_argument('--sdk',required=True);args=p.parse_args()
root=Path(__file__).resolve().parents[1];tools=Path(args.sdk)/'build-tools/35.0.0/lib/apksigner.jar'
if not tools.exists():tools=Path(args.sdk)/'android-15/lib/apksigner.jar'
output=subprocess.check_output(['java','-jar',str(tools),'verify','--print-certs',args.apk],text=True)
match=re.search(r'certificate SHA-256 digest: (\S+)',output)
expected=(root/'android/signing-certificate.sha256').read_text().strip().lower()
if not match or match.group(1).lower()!=expected:raise SystemExit('Signing certificate differs from the installed app. Refusing to publish an incompatible update.')
print('APK signature is valid and matches previous versions.')
