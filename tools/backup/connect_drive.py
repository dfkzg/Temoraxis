"""Run on the owner's PC: authorize only app-created Drive files, never the whole Drive."""
import base64,hashlib,http.server,json,os,secrets,threading,urllib.parse,urllib.request,webbrowser
from pathlib import Path

SCOPE='https://www.googleapis.com/auth/drive.file'

def post(url,body,token=None):
    headers={'Content-Type':'application/json' if token else 'application/x-www-form-urlencoded'}
    if token:headers['Authorization']='Bearer '+token
    raw=json.dumps(body).encode() if token else urllib.parse.urlencode(body).encode()
    with urllib.request.urlopen(urllib.request.Request(url,data=raw,headers=headers),timeout=60) as response:return json.load(response)

def connect(client,open_browser=webbrowser.open):
    state=secrets.token_urlsafe(32);verifier=secrets.token_urlsafe(64)
    challenge=base64.urlsafe_b64encode(hashlib.sha256(verifier.encode()).digest()).rstrip(b'=').decode()
    result={};ready=threading.Event()
    class Callback(http.server.BaseHTTPRequestHandler):
        def log_message(self,*args):pass
        def do_GET(self):
            url=urllib.parse.urlsplit(self.path);params=urllib.parse.parse_qs(url.query)
            if url.path!='/' or not secrets.compare_digest(params.get('state',[''])[0],state):
                self.send_error(400);return
            result['code']=params.get('code',[''])[0];result['error']=params.get('error',[''])[0]
            self.send_response(200);self.send_header('Content-Type','text/html; charset=utf-8');self.end_headers()
            self.wfile.write('<meta charset="utf-8"><p>Можно закрыть эту вкладку и вернуться к настройке Temoraxis.</p>'.encode());ready.set()
    server=http.server.ThreadingHTTPServer(('127.0.0.1',0),Callback)
    redirect='http://127.0.0.1:'+str(server.server_port)+'/'
    thread=threading.Thread(target=server.serve_forever,daemon=True);thread.start()
    url='https://accounts.google.com/o/oauth2/v2/auth?'+urllib.parse.urlencode({'client_id':client['client_id'],'redirect_uri':redirect,'response_type':'code','scope':SCOPE,'access_type':'offline','prompt':'consent select_account','state':state,'code_challenge':challenge,'code_challenge_method':'S256'})
    try:
        if not open_browser(url):raise RuntimeError('Не удалось открыть браузер.')
        if not ready.wait(300) or result.get('error') or not result.get('code'):raise RuntimeError('Подключение отменено или время ожидания истекло.')
    finally:server.shutdown();server.server_close();thread.join()
    session=post('https://oauth2.googleapis.com/token',{'client_id':client['client_id'],'client_secret':client['client_secret'],'code':result['code'],'code_verifier':verifier,'redirect_uri':redirect,'grant_type':'authorization_code'})
    if not session.get('refresh_token'):raise RuntimeError('Google не выдал постоянный доступ. Повторите подключение с согласием.')
    if SCOPE not in session.get('scope','').split():raise RuntimeError('Google не подтвердил право создавать файлы резервных копий.')
    folder=post('https://www.googleapis.com/drive/v3/files?fields=id',{'name':'Temoraxis — резервные копии','mimeType':'application/vnd.google-apps.folder'},session['access_token'])
    return {'client_id':client['client_id'],'client_secret':client['client_secret'],'refresh_token':session['refresh_token'],'folder_id':folder['id']}

def main():
    from tkinter import Tk,filedialog,messagebox
    os.umask(0o077);root=Tk();root.withdraw()
    try:
        messagebox.showinfo('Temoraxis','Выберите JSON-файл OAuth-клиента Google типа Desktop app. В браузере выберите аккаунт с нужным Google Диском. Пароль Google программа не запрашивает.')
        selected=filedialog.askopenfilename(title='JSON OAuth-клиента Google',filetypes=[('JSON','*.json')])
        if not selected:return
        client=json.loads(Path(selected).read_text()).get('installed')
        if not client:raise RuntimeError('Нужен OAuth-клиент типа Desktop app, не service account и не Web application.')
        if not client.get('client_id','').endswith('.apps.googleusercontent.com') or not client.get('client_secret'):raise RuntimeError('Некорректный OAuth-клиент.')
        config=connect(client)
        target=filedialog.asksaveasfilename(title='Сохранить секрет для GitHub — не публикуйте файл',initialfile='google-drive-secret.json',defaultextension='.json')
        if not target:return
        path=Path(target)
        with path.open('w',encoding='utf-8') as f:json.dump(config,f,ensure_ascii=False,indent=2)
        path.chmod(0o600)
        webbrowser.open('https://drive.google.com/drive/folders/'+config['folder_id'])
        messagebox.showinfo('Готово','Создана папка на выбранном Google Диске. Содержимое сохранённого файла добавьте в GitHub Secret BACKUP_GOOGLE_DRIVE_JSON. Не присылайте файл в чат и не загружайте в репозиторий.')
    except Exception as e:
        messagebox.showerror('Не удалось подключить',str(e) if isinstance(e,RuntimeError) else 'Подключение не завершено. Проверьте интернет, JSON OAuth-клиента и настройки Google Cloud. Не публикуйте файл настроек.')
    finally:root.destroy()

if __name__=='__main__':main()
