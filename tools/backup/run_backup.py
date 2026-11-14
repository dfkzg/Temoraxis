"""Choose the configured storage without exposing secrets or requiring a PC to stay on."""
import os,re,tempfile
from datetime import datetime,timezone
from pathlib import Path
import drive_backup as common
import yandex_backup as yandex

def main():
    if not os.environ.get('BACKUP_YANDEX_TOKEN'):
        common.main();return
    os.umask(0o077)
    token=os.environ['BACKUP_YANDEX_TOKEN'].strip()
    if not re.fullmatch(r'[A-Za-z0-9_.-]{20,4096}',token):raise common.BackupError('Invalid Yandex token. Paste only the token, not the entire URL.')
    yandex.ensure_folder(token)
    with tempfile.TemporaryDirectory(prefix='temoraxis-backup-') as tmp:
        archive=common.dump_database(Path(tmp),os.environ['SUPABASE_BACKUP_DB_URL'])
        encrypted=common.encrypt_archive(archive,os.environ['BACKUP_AGE_RECIPIENT'].strip())
        digest=common.sha256(encrypted)
        name='temoraxis-'+datetime.now(timezone.utc).strftime('%Y%m%dT%H%M%SZ')+'-'+digest[:12]+'.dump.age'
        target=yandex.upload(encrypted,token,name,digest)
        yandex.verify_download(token,target,digest)
        removed=yandex.prune(token,target)
    print('Encrypted Yandex Disk backup uploaded and verified. Older copies removed:',removed)

if __name__=='__main__':
    try:main()
    except Exception as error:
        print(str(error) if isinstance(error,common.BackupError) else 'Backup failed. Check private configuration; cleanup requires a verified new copy.')
        raise SystemExit(1) from None
