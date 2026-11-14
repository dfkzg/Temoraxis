"""Yandex Disk REST adapter. A token with only disk.app_folder scope is sufficient."""
import hashlib,json,re,time,urllib.parse,urllib.request
from drive_backup import BackupError,NAME,SET,request

API='https://cloud-api.yandex.net/v1/disk'
FOLDER='app:/Temoraxis-backups'

def api(token,endpoint='',method='GET',body=None,**params):
    url=API+endpoint+('?' + urllib.parse.urlencode(params) if params else '')
    _,_,raw=request(url,method=method,data=None if body is None else json.dumps(body).encode(),headers={'Authorization':'OAuth '+token,'Content-Type':'application/json'})
    return json.loads(raw) if raw else None

def storage_url(link,method):
    href=link.get('href','');u=urllib.parse.urlsplit(href)
    try:valid_port=u.port in (None,443)
    except ValueError:valid_port=False
    if u.scheme!='https' or not u.hostname or not any(u.hostname.endswith(suffix) for suffix in ('.yandex.net','.yandex.ru','.yandex.com')) or not valid_port or u.username or u.password or u.fragment or link.get('method')!=method or link.get('templated'):
        raise BackupError('Unexpected Yandex storage address; no file was transferred.')
    return href

def ensure_folder(token):
    try:api(token,'/resources',method='PUT',path=FOLDER)
    except BackupError as e:
        if e.status!=409:raise
        if api(token,'/resources',path=FOLDER).get('type')!='dir':raise BackupError('Backup folder is not a directory.')

def upload(path,token,name,digest):
    if not NAME.fullmatch(name):raise BackupError('Invalid backup name.')
    target=FOLDER+'/'+name
    link=api(token,'/resources/upload',path=target,overwrite='false')
    href=storage_url(link,'PUT')
    # Signed storage URL grants this one upload. Never forward the OAuth token there.
    with path.open('rb') as data:
        status,_,_=request(href,method='PUT',data=data,headers={'Content-Type':'application/octet-stream','Content-Length':str(path.stat().st_size)})
    if status not in (201,202):raise BackupError('Yandex did not accept the backup.')
    for attempt in range(15):
        try:item=api(token,'/resources',path=target)
        except BackupError as e:
            if e.status!=404:raise
            item={}
        if item.get('sha256')==digest and item.get('size')==path.stat().st_size:break
        if item.get('sha256') and item.get('sha256')!=digest:raise BackupError('Yandex checksum mismatch; old backups were retained.')
        time.sleep(2)
    else:raise BackupError('Backup metadata is not ready; old backups were retained.')
    api(token,'/resources',method='PATCH',path=target,body={'custom_properties':{'temoraxisBackupSet':SET,'format':'pg-custom-age-v1'}})
    return target

def verify_download(token,target,expected):
    href=storage_url(api(token,'/resources/download',path=target),'GET')
    try:
        with urllib.request.urlopen(href,timeout=180) as response:actual=hashlib.file_digest(response,'sha256').hexdigest()
    except (OSError,TimeoutError):raise BackupError('Yandex read-back failed; old backups were retained.') from None
    if actual!=expected:raise BackupError('Yandex read-back checksum mismatch; old backups were retained.')

def list_backups(token):
    items=[];offset=0
    while True:
        result=api(token,'/resources',path=FOLDER,limit=1000,offset=offset)
        page=result.get('_embedded',{});batch=page.get('items',[])
        for item in batch:
            name=item.get('name','');props=item.get('custom_properties',{});digest=item.get('sha256','')
            if item.get('type')=='file' and NAME.fullmatch(name) and props.get('temoraxisBackupSet')==SET and props.get('format')=='pg-custom-age-v1' and re.fullmatch('[0-9a-f]{64}',digest) and name.endswith('-'+digest[:12]+'.dump.age'):
                items.append(item)
        offset+=len(batch)
        total=page.get('total')
        if total is None:raise BackupError('Yandex returned incomplete folder metadata; cleanup stopped.')
        if offset>=total:break
        if not batch:raise BackupError('Yandex pagination stopped; cleanup was cancelled.')
    return sorted(items,key=lambda item:item['name'],reverse=True)

def prune(token,new_target,keep=14):
    items=list_backups(token)
    if new_target not in {FOLDER+'/'+item['name'] for item in items[:keep]}:raise BackupError('New Yandex backup not found among retained copies; cleanup cancelled.')
    for item in items[keep:]:
        result=api(token,'/resources',method='DELETE',path=FOLDER+'/'+item['name'],permanently='true',force_async='false')
        if result and result.get('href'):
            # Deletion may be asynchronous, but it must stay within the authenticated API.
            url=urllib.parse.urlsplit(result['href'])
            if url.scheme!='https' or url.netloc!='cloud-api.yandex.net' or not url.path.startswith('/v1/disk/operations/') or url.query or url.fragment:raise BackupError('Unexpected deletion operation address.')
            for _ in range(15):
                status=api(token,url.path.removeprefix('/v1/disk')).get('status')
                if status=='success':break
                if status!='in-progress':raise BackupError('Yandex did not complete old-backup removal.')
                time.sleep(2)
            else:raise BackupError('Yandex cleanup is still pending; new backup is verified.')
    return len(items[keep:])
