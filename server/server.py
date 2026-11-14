"""Planner sync server. Python 3.11+, SQLite, no external dependencies."""
import hashlib, hmac, json, os, re, secrets, sqlite3, subprocess, sys, threading, time
from http.server import ThreadingHTTPServer, BaseHTTPRequestHandler
from pathlib import Path
from urllib.parse import urlsplit, unquote

os.umask(0o077)
ROOT=Path(__file__).resolve().parent
DB=Path(os.environ.get('PLANNER_DB',str(ROOT/'data'/'planner.sqlite')))
DB.parent.mkdir(parents=True,exist_ok=True)
MAX_BODY=5*1024*1024
ORIGINS={item.strip() for item in os.environ.get('PLANNER_ORIGINS','https://appassets.androidplatform.net').split(',') if item.strip()}
RATE_LOCK=threading.Lock()
ATTEMPTS={}

def connect():
    db=sqlite3.connect(DB,timeout=15)
    db.execute('PRAGMA journal_mode=WAL')
    db.execute('PRAGMA foreign_keys=ON')
    return db

def init_db():
    with connect() as db:
        db.executescript('''CREATE TABLE IF NOT EXISTS users(id TEXT PRIMARY KEY, username TEXT UNIQUE NOT NULL, salt BLOB NOT NULL, password BLOB NOT NULL);
CREATE TABLE IF NOT EXISTS sessions(token_hash TEXT PRIMARY KEY,user_id TEXT NOT NULL REFERENCES users(id),expires INTEGER NOT NULL);
CREATE TABLE IF NOT EXISTS documents(user_id TEXT PRIMARY KEY REFERENCES users(id),revision INTEGER NOT NULL,document TEXT NOT NULL,updated INTEGER NOT NULL);''')

def password_hash(password,salt):
    return hashlib.scrypt(password.encode(),salt=salt,n=16384,r=8,p=1,dklen=32)

def valid_document(value):
    if not isinstance(value,dict) or set(value)!={'tasks','clock','specialDates','tags','startPage'}:return False
    tasks=value.get('tasks');clock=value.get('clock');dates=value.get('specialDates');tags=value.get('tags');start=value.get('startPage')
    if not isinstance(tasks,list) or len(tasks)>10000 or not isinstance(clock,dict) or not isinstance(dates,list) or not isinstance(tags,list):return False
    if not all(isinstance(tag,str) and len(tag)<=200 for tag in tags):return False
    for task in tasks:
        if not isinstance(task,dict) or not isinstance(task.get('id'),str) or not re.fullmatch(r'[A-Za-z0-9_-]{1,128}',task['id']) or not isinstance(task.get('title'),str):return False
    if len({t['id'] for t in tasks})!=len(tasks):return False
    for entry in dates:
        if not isinstance(entry,dict) or not isinstance(entry.get('name'),str) or not isinstance(entry.get('date'),str):return False
    if start is not None:
        if not isinstance(start,dict) or not isinstance(start.get('groups'),list):return False
        for group in start['groups']:
            if not isinstance(group,dict) or not isinstance(group.get('id'),str) or not re.fullmatch(r'[A-Za-z0-9_-]{1,128}',group['id']) or not isinstance(group.get('name'),str) or not isinstance(group.get('links'),list):return False
            for link in group['links']:
                if not isinstance(link,dict) or not isinstance(link.get('id'),str) or not re.fullmatch(r'[A-Za-z0-9_-]{1,128}',link['id']) or not isinstance(link.get('name'),str) or not isinstance(link.get('url'),str) or urlsplit(link['url']).scheme not in ('http','https'):return False
    return True

class Handler(BaseHTTPRequestHandler):
    server_version='Planner/0.1'
    def setup(self):
        super().setup();self.connection.settimeout(15)
    def log_message(self,format,*args): pass
    def origin_allowed(self):
        origin=self.headers.get('Origin')
        if not origin:return True
        own='https://'+self.headers.get('Host','')
        local='http://'+self.headers.get('Host','')
        return origin in ORIGINS or origin==own or (os.environ.get('PLANNER_ALLOW_HTTP')=='1' and origin==local)
    def headers_common(self):
        self.send_header('X-Content-Type-Options','nosniff')
        self.send_header('Referrer-Policy','no-referrer')
        self.send_header('Cross-Origin-Resource-Policy','same-origin')
        origin=self.headers.get('Origin')
        if origin and self.origin_allowed():self.send_header('Access-Control-Allow-Origin',origin);self.send_header('Vary','Origin')
    def reply(self,status,body):
        raw=json.dumps(body,ensure_ascii=False,separators=(',',':')).encode()
        self.send_response(status);self.headers_common();self.send_header('Cache-Control','no-store');self.send_header('Content-Type','application/json; charset=utf-8');self.send_header('Content-Length',str(len(raw)));self.end_headers();self.wfile.write(raw)
    def body(self):
        try:length=int(self.headers.get('Content-Length','0'))
        except ValueError:raise ValueError('Неверный размер запроса.')
        if length<1 or length>MAX_BODY:raise ValueError('Запрос слишком большой или пустой.')
        if self.headers.get('Content-Type','').split(';')[0]!='application/json':raise ValueError('Нужен JSON.')
        value=json.loads(self.rfile.read(length))
        if not isinstance(value,dict):raise ValueError('Нужен JSON-объект.')
        return value
    def user(self):
        auth=self.headers.get('Authorization','')
        if not auth.startswith('Bearer ') or len(auth)>256:return None
        key=hashlib.sha256(auth[7:].encode()).hexdigest()
        with connect() as db:
            record=db.execute('SELECT user_id FROM sessions WHERE token_hash=? AND expires>?',(key,int(time.time()))).fetchone()
        return record[0] if record else None
    def rate_limited(self):
        ip=self.client_address[0]
        if os.environ.get('PLANNER_TRUST_PROXY')=='1':ip=self.headers.get('X-Forwarded-For',ip).split(',')[0].strip()[:128]
        now=time.time()
        with RATE_LOCK:
            history=[stamp for stamp in ATTEMPTS.get(ip,[]) if now-stamp<600]
            if len(history)>=30:return True
            history.append(now);ATTEMPTS[ip]=history
            if len(ATTEMPTS)>10000:ATTEMPTS.clear()
        return False
    def do_OPTIONS(self):
        if not self.origin_allowed():return self.reply(403,{'error':'Источник запроса не разрешён.'})
        self.send_response(204);self.headers_common();self.send_header('Access-Control-Allow-Methods','GET,POST,PUT,OPTIONS');self.send_header('Access-Control-Allow-Headers','Authorization,Content-Type');self.end_headers()
    def do_GET(self):
        path=urlsplit(self.path).path
        if path=='/api/health':return self.reply(200,{'ok':True,'version':1})
        if path=='/api/sync':
            if not self.origin_allowed():return self.reply(403,{'error':'Источник запроса не разрешён.'})
            user=self.user()
            if not user:return self.reply(401,{'error':'Войдите в аккаунт.'})
            with connect() as db:row=db.execute('SELECT revision,document,updated FROM documents WHERE user_id=?',(user,)).fetchone()
            return self.reply(200,{'revision':row[0] if row else 0,'document':json.loads(row[1]) if row else None,'updatedAt':row[2] if row else None})
        files={'/':'planner.html','/planner.html':'planner.html','/Start_page.html':'Start_page.html','/manifest.webmanifest':'manifest.webmanifest','/sw.js':'sw.js','/icon.svg':'icon.svg','/icon-180.png':'icon-180.png','/icon-192.png':'icon-192.png','/icon-512.png':'icon-512.png'}
        filename=files.get(path)
        if not filename:return self.reply(404,{'error':'Не найдено.'})
        target=ROOT/'web'/filename
        if not target.is_file():return self.reply(404,{'error':'Файлы интерфейса не установлены.'})
        raw=target.read_bytes();mime={'html':'text/html; charset=utf-8','js':'application/javascript','webmanifest':'application/manifest+json','svg':'image/svg+xml','png':'image/png'}[filename.rsplit('.',1)[-1]]
        self.send_response(200);self.headers_common();self.send_header('Content-Type',mime);self.send_header('Cache-Control','no-cache');self.send_header('Content-Length',str(len(raw)));self.send_header('Content-Security-Policy',"default-src 'self'; script-src 'self' 'unsafe-inline'; style-src 'self' 'unsafe-inline'; img-src 'self' data: blob: https:; media-src 'self' blob: data:; connect-src 'self' https:; object-src 'none'; frame-src 'none'; base-uri 'self'");self.end_headers();self.wfile.write(raw)
    def do_POST(self):
        if not self.origin_allowed():return self.reply(403,{'error':'Источник запроса не разрешён.'})
        path=urlsplit(self.path).path
        if path=='/api/logout':
            auth=self.headers.get('Authorization','')
            if auth.startswith('Bearer '):
                with connect() as db:db.execute('DELETE FROM sessions WHERE token_hash=?',(hashlib.sha256(auth[7:].encode()).hexdigest(),))
            return self.reply(200,{'ok':True})
        if path not in ('/api/register','/api/login'):return self.reply(404,{'error':'Не найдено.'})
        if self.rate_limited():return self.reply(429,{'error':'Слишком много попыток. Повторите через 10 минут.'})
        try:
            value=self.body();username=value.get('username','').strip().casefold();password=value.get('password','')
            if not isinstance(username,str) or not 3<=len(username)<=100 or not re.fullmatch(r'[\w@.+-]+',username):return self.reply(400,{'error':'Логин: от 3 до 100 букв, цифр или символов @ . + - _.'})
            if not isinstance(password,str) or not 10<=len(password)<=256:return self.reply(400,{'error':'Пароль: от 10 до 256 символов.'})
            with connect() as db:
                if path=='/api/register':
                    invite=os.environ.get('PLANNER_INVITE_CODE','')
                    if not invite or len(invite)<16 or invite.startswith('replace-'):return self.reply(503,{'error':'Регистрация отключена: настройте код приглашения на сервере.'})
                    if not isinstance(value.get('inviteCode'),str) or not hmac.compare_digest(value['inviteCode'],invite):return self.reply(403,{'error':'Неверный код приглашения.'})
                    user=secrets.token_hex(16);salt=secrets.token_bytes(16)
                    try:db.execute('INSERT INTO users VALUES(?,?,?,?)',(user,username,salt,password_hash(password,salt)))
                    except sqlite3.IntegrityError:return self.reply(409,{'error':'Этот логин уже занят.'})
                else:
                    record=db.execute('SELECT id,salt,password FROM users WHERE username=?',(username,)).fetchone()
                    derived=password_hash(password,record[1] if record else bytes(16))
                    if not record or not hmac.compare_digest(derived,record[2]):return self.reply(401,{'error':'Неверный логин или пароль.'})
                    user=record[0]
                token=secrets.token_urlsafe(48);db.execute('DELETE FROM sessions WHERE expires<?',(int(time.time()),));db.execute('INSERT INTO sessions VALUES(?,?,?)',(hashlib.sha256(token.encode()).hexdigest(),user,int(time.time())+30*86400))
            return self.reply(200,{'token':token,'username':username,'expiresIn':30*86400})
        except (ValueError,TypeError,AttributeError,RecursionError,json.JSONDecodeError):return self.reply(400,{'error':'Некорректный запрос.'})
    def do_PUT(self):
        if urlsplit(self.path).path!='/api/sync':return self.reply(404,{'error':'Не найдено.'})
        if not self.origin_allowed():return self.reply(403,{'error':'Источник запроса не разрешён.'})
        user=self.user()
        if not user:return self.reply(401,{'error':'Войдите в аккаунт.'})
        try:
            value=self.body();revision=value.get('expectedRevision');document=value.get('document')
            if type(revision) is not int or revision<0 or not valid_document(document):return self.reply(400,{'error':'Некорректные данные синхронизации.'})
            raw=json.dumps(document,ensure_ascii=False,separators=(',',':'));now=int(time.time())
            with connect() as db:
                db.execute('BEGIN IMMEDIATE')
                row=db.execute('SELECT revision FROM documents WHERE user_id=?',(user,)).fetchone();current=row[0] if row else 0
                if current!=revision:return self.reply(409,{'error':'Данные на другом устройстве изменились.','revision':current})
                next_revision=current+1
                db.execute('INSERT INTO documents VALUES(?,?,?,?) ON CONFLICT(user_id) DO UPDATE SET revision=excluded.revision,document=excluded.document,updated=excluded.updated',(user,next_revision,raw,now))
            return self.reply(200,{'revision':next_revision,'updatedAt':now})
        except (ValueError,TypeError,AttributeError,RecursionError,json.JSONDecodeError):return self.reply(400,{'error':'Некорректный запрос.'})

if __name__=='__main__':
    if not (ROOT/'web'/'planner.html').is_file():
        subprocess.run([sys.executable,str(ROOT.parent/'stage_web.py')],check=True)
    init_db();host=os.environ.get('PLANNER_HOST','127.0.0.1');port=int(os.environ.get('PLANNER_PORT','8080'))
    print(f'Planner server listening on {host}:{port}',flush=True)
    ThreadingHTTPServer((host,port),Handler).serve_forever()
