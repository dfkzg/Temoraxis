"""Encrypted application database backups. Credentials only enter through environment."""
import hashlib,json,os,re,subprocess,tempfile,urllib.error,urllib.parse,urllib.request
from datetime import datetime,timezone
from pathlib import Path

API='https://www.googleapis.com/drive/v3/files'
SET='temoraxis-udrlbmlofdzevwvzssfw-v1'
NAME=re.compile(r'temoraxis-\d{8}T\d{6}Z-[0-9a-f]{12}\.dump\.age\Z')
SCHEMAS=('public','temoraxis_private','auth')

class BackupError(Exception):pass

def request(url,token=None,method='GET',data=None,headers=None):
    h=dict(headers or {})
    if token:h['Authorization']='Bearer '+token
    req=urllib.request.Request(url,data=data,headers=h,method=method)
    try:
        with urllib.request.urlopen(req,timeout=180) as r:return r.status,r.headers,r.read()
    except urllib.error.HTTPError as e:
        # Never print server responses: they may contain identifiers/credentials.
        if e.code==308:return e.code,e.headers,b''
        raise BackupError('Cloud request failed (HTTP '+str(e.code)+').') from None
    except (OSError,TimeoutError):raise BackupError('Cloud request failed; no old backups were removed.') from None

def json_request(url,token=None,method='GET',body=None):
    data=None if body is None else json.dumps(body).encode()
    _,_,raw=request(url,token,method,data,{'Content-Type':'application/json'})
    return json.loads(raw) if raw else None

def access_token(config):
    body=urllib.parse.urlencode({k:config[k] for k in ('client_id','client_secret','refresh_token')}|{'grant_type':'refresh_token'}).encode()
    _,_,raw=request('https://oauth2.googleapis.com/token',method='POST',data=body,headers={'Content-Type':'application/x-www-form-urlencoded'})
    return json.loads(raw)['access_token']

def postgres_env(url):
    try:
        u=urllib.parse.urlsplit(url)
        if u.scheme not in ('postgres','postgresql') or not u.hostname or not re.fullmatch(r'[a-z0-9.-]+\.(?:supabase\.co|pooler\.supabase\.com)',u.hostname):raise ValueError()
        if (u.port or 5432)!=5432 or not u.username or not u.password or u.fragment:raise ValueError()
        return {'PGHOST':u.hostname,'PGPORT':'5432','PGDATABASE':urllib.parse.unquote(u.path.lstrip('/')) or 'postgres','PGUSER':urllib.parse.unquote(u.username),'PGPASSWORD':urllib.parse.unquote(u.password),'PGSSLMODE':'verify-full','PGSSLROOTCERT':'system','PGCONNECT_TIMEOUT':'30'}
    except ValueError:raise BackupError('Use the Supabase session-pooler connection URI on port 5432, with a URL-encoded password.') from None

def dump_database(folder,url):
    env={**os.environ,**postgres_env(url)}
    cmd=['docker','run','--rm','--network','host']
    for key in postgres_env(url):cmd+=['--env',key]
    cmd+=['--volume',str(folder)+':/backup','postgres:17-alpine','pg_dump','--format=custom','--no-owner','--no-acl','--file=/backup/database.dump']
    for schema in SCHEMAS:cmd+=['--schema='+schema]
    # Connection strings, passwords and database errors must not enter public CI logs.
    result=subprocess.run(cmd,env=env,capture_output=True)
    if result.returncode:raise BackupError('Database dump failed. Check credentials, pooler, TLS and PostgreSQL version; nothing was uploaded.')
    archive=folder/'database.dump'
    if not archive.is_file() or archive.stat().st_size<100:raise BackupError('Database dump is empty.')
    result=subprocess.run(['docker','run','--rm','--volume',str(folder)+':/backup:ro','postgres:17-alpine','pg_restore','--list','/backup/database.dump'],capture_output=True,text=True)
    if result.returncode or any(not re.search(r'\bSCHEMA - '+schema+r'\b',result.stdout) for schema in SCHEMAS):raise BackupError('Dump validation failed: required schemas are missing.')
    return archive

def sha256(path):
    with path.open('rb') as f:return hashlib.file_digest(f,'sha256').hexdigest()

def encrypt_archive(archive,recipient):
    if not re.fullmatch(r'age1[023456789acdefghjklmnpqrstuvwxyz]{58}',recipient):raise BackupError('Invalid age public recipient.')
    encrypted=archive.with_suffix('.dump.age')
    result=subprocess.run(['age','--recipient',recipient,'--output',str(encrypted),str(archive)],capture_output=True)
    if result.returncode:raise BackupError('Encryption failed; nothing was uploaded.')
    archive.unlink()
    return encrypted

def upload(path,token,folder_id,name,digest):
    metadata={'name':name,'parents':[folder_id],'appProperties':{'temoraxisBackupSet':SET,'sha256':digest,'format':'pg-custom-age-v1'}}
    _,headers,_=request(API.replace('/drive/v3/','/upload/drive/v3/')+'?uploadType=resumable&fields=id,size,appProperties',token,'POST',json.dumps(metadata).encode(),{'Content-Type':'application/json','X-Upload-Content-Type':'application/octet-stream','X-Upload-Content-Length':str(path.stat().st_size)})
    location=headers.get('Location','');parsed=urllib.parse.urlsplit(location)
    if parsed.scheme!='https' or parsed.hostname!='www.googleapis.com' or not parsed.path.startswith('/upload/drive/v3/'):raise BackupError('Unexpected upload address.')
    # A resumable upload is not published until the complete stream reaches Drive.
    # If the upload fails, retain all previous backups and retry the whole job later.
    with path.open('rb') as data:
        status,_,raw=request(location,token,'PUT',data,{'Content-Length':str(path.stat().st_size),'Content-Type':'application/octet-stream'})
    if status not in (200,201):raise BackupError('Upload did not complete; old backups were retained.')
    item=json.loads(raw)
    if str(item.get('size'))!=str(path.stat().st_size) or item.get('appProperties',{}).get('sha256')!=digest:raise BackupError('Uploaded backup metadata did not match.')
    return item['id']

def verify_download(token,file_id,expected):
    req=urllib.request.Request(API+'/'+urllib.parse.quote(file_id,safe='')+'?alt=media',headers={'Authorization':'Bearer '+token})
    try:
        with urllib.request.urlopen(req,timeout=180) as response:actual=hashlib.file_digest(response,'sha256').hexdigest()
    except (OSError,TimeoutError):raise BackupError('Backup read-back failed; old backups were retained.') from None
    if actual!=expected:raise BackupError('Backup checksum mismatch; old backups were retained.')

def list_backups(token,folder_id):
    if not re.fullmatch(r'[A-Za-z0-9_-]+',folder_id):raise BackupError('Invalid Drive folder ID.')
    q="'"+folder_id+"' in parents and trashed = false and appProperties has { key='temoraxisBackupSet' and value='"+SET+"' }"
    items=[];page=None
    while True:
        params={'q':q,'fields':'nextPageToken,files(id,name,createdTime,appProperties)','pageSize':'1000'}
        if page:params['pageToken']=page
        result=json_request(API+'?'+urllib.parse.urlencode(params),token)
        items.extend(f for f in result['files'] if NAME.fullmatch(f.get('name','')) and f.get('appProperties',{}).get('temoraxisBackupSet')==SET and f.get('appProperties',{}).get('format')=='pg-custom-age-v1' and re.fullmatch(r'[a-f0-9]{64}',f.get('appProperties',{}).get('sha256','')))
        page=result.get('nextPageToken')
        if not page:return sorted(items,key=lambda f:(f['createdTime'],f['id']),reverse=True)

def prune(token,folder_id,new_id,keep=14):
    items=list_backups(token,folder_id)
    if new_id not in {f['id'] for f in items[:keep]}:raise BackupError('New backup not found among retained copies; nothing was removed.')
    for item in items[keep:]:request(API+'/'+urllib.parse.quote(item['id'],safe=''),token,'DELETE')
    return len(items[keep:])

def main():
    os.umask(0o077)
    config=json.loads(os.environ['BACKUP_GOOGLE_DRIVE_JSON'])
    folder=config['folder_id']
    if not re.fullmatch(r'[A-Za-z0-9_-]+',folder):raise BackupError('Invalid Drive folder ID.')
    token=access_token(config)
    with tempfile.TemporaryDirectory(prefix='temoraxis-backup-') as tmp:
        folder_path=Path(tmp)
        archive=dump_database(folder_path,os.environ['SUPABASE_BACKUP_DB_URL'])
        encrypted=encrypt_archive(archive,os.environ['BACKUP_AGE_RECIPIENT'].strip())
        digest=sha256(encrypted)
        name='temoraxis-'+datetime.now(timezone.utc).strftime('%Y%m%dT%H%M%SZ')+'-'+digest[:12]+'.dump.age'
        new_id=upload(encrypted,token,folder,name,digest)
        verify_download(token,new_id,digest)
        removed=prune(token,folder,new_id)
    print('Encrypted database backup uploaded and verified. Older copies removed:',removed)

if __name__=='__main__':
    try:main()
    except Exception as error:
        print(str(error) if isinstance(error,BackupError) else 'Backup failed. Check private configuration; prior copies were retained until upload verification.')
        raise SystemExit(1) from None
