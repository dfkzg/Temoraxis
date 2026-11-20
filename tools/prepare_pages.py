"""Build the public download site without publishing maintenance documents or duplicate assets in Git."""
from pathlib import Path
import html,json,os,re,runpy,shutil,urllib.request
ROOT=Path(__file__).resolve().parents[1]
output=ROOT/'dist'/'pages'
if output.exists():shutil.rmtree(output)
output.mkdir(parents=True)
for name in ['index.html','sitemap.xml','.nojekyll']:
    shutil.copy2(ROOT/'docs'/name,output/name)
# Snapshot the actual published release, never an unreleased source version.
if os.environ.get('GH_TOKEN'):
    request=urllib.request.Request('https://api.github.com/repos/dfkzg/Temoraxis/releases/latest',headers={'Authorization':'Bearer '+os.environ['GH_TOKEN'],'Accept':'application/vnd.github+json'})
    with urllib.request.urlopen(request,timeout=30) as response:release=json.load(response)
    if release.get('draft') or release.get('prerelease'):raise ValueError('Expected a published stable release')
    public={key:release.get(key) for key in ['tag_name','published_at','body','draft','prerelease']}
    public['assets']=[{key:asset.get(key) for key in ['name','size','digest','browser_download_url']} for asset in release['assets']]
    windows_meta=json.loads((ROOT/'windows'/'release.json').read_text())
    windows_request=urllib.request.Request('https://api.github.com/repos/dfkzg/Temoraxis/releases/tags/'+windows_meta['tag'],headers={'Authorization':'Bearer '+os.environ['GH_TOKEN'],'Accept':'application/vnd.github+json'})
    with urllib.request.urlopen(windows_request,timeout=30) as response:windows_release=json.load(response)
    if windows_release.get('draft') or windows_release.get('prerelease'):raise ValueError('Windows release is not published')
    windows_asset=next(a for a in windows_release['assets'] if a['name']==windows_meta['asset'])
    snapshot=json.dumps(public,ensure_ascii=False).replace('<','\\u003c').replace('>','\\u003e').replace('&','\\u0026')
    page=output/'index.html'
    page_source=page.read_text().replace('const PUBLISHED_RELEASE=null;','const PUBLISHED_RELEASE='+snapshot+';')
    page_source=re.sub(r'(<a[^>]*id="windows"[^>]*href=")[^"]+(")',lambda match:match[1]+html.escape(windows_asset['browser_download_url'],quote=True)+match[2],page_source)
    page.write_text(page_source)
shutil.copy2(ROOT/'web-source'/'guide.html',output/'guide.html')
for name in ['icon.svg','icon-512.png']:
    shutil.copy2(ROOT/'web-source'/name,output/name)
# Build a browser app from the same sources as Android; never maintain another HTML copy.
runpy.run_path(str(ROOT/'stage_web.py'))
app=output/'app';app.mkdir()
for name in ['planner.html','Start_page.html','manifest.webmanifest','sw.js','icon.svg','icon-180.png','icon-192.png','icon-512.png','THIRD-PARTY.txt']:
    shutil.copy2(ROOT/'server'/'web'/name,app/name)
standalone_html=runpy.run_path(str(ROOT/'tools'/'user_html.py'))['standalone_html']
downloads=output/'downloads';downloads.mkdir()
for name in ['planner.html','Start_page.html']:
    (downloads/name).write_text(standalone_html(name))
# User bundle uses the existing published APK; no new Android build is needed.
if os.environ.get('GH_TOKEN'):
    apk_asset=next(a for a in public['assets'] if a['name']=='temoraxis-android.apk')
    with urllib.request.urlopen(apk_asset['browser_download_url'],timeout=60) as response:apk_bytes=response.read()
    import zipfile,hashlib
    digest=apk_asset.get('digest')
    if digest and digest!='sha256:'+hashlib.sha256(apk_bytes).hexdigest():raise ValueError('APK checksum mismatch')
    with urllib.request.urlopen(windows_asset['browser_download_url'],timeout=120) as response:windows_bytes=response.read()
    if not windows_bytes.startswith(b'MZ'):raise ValueError('Invalid Windows executable')
    if windows_asset.get('digest') and windows_asset['digest']!='sha256:'+hashlib.sha256(windows_bytes).hexdigest():raise ValueError('Windows checksum mismatch')
    with zipfile.ZipFile(downloads/'temoraxis-full-kit.zip' ,'w',zipfile.ZIP_DEFLATED) as archive:
        for name in ['planner.html','Start_page.html']:
            archive.write(downloads/name,'Temoraxis/'+name)
        archive.writestr('Temoraxis/temoraxis-android.apk',apk_bytes)
        archive.write(ROOT/'docs'/'USER-README.txt','Temoraxis/README.txt')
        archive.writestr('Temoraxis/temoraxis-windows.exe',windows_bytes)
for path in app.glob('*.html'):
    source=path.read_text().replace('</head>','<meta name="robots" content="noindex"></head>',1)
    path.write_text(source)
manifest=json.loads((app/'manifest.webmanifest').read_text())
prefix='/Temoraxis/app/'
manifest.update(id=prefix,scope=prefix,start_url=prefix+'planner.html')
for icon in manifest['icons']:icon['src']=prefix+Path(icon['src']).name
(app/'manifest.webmanifest').write_text(json.dumps(manifest,ensure_ascii=False))
(app/'index.html').write_text('<!doctype html><html lang="ru"><head><meta charset="utf-8"><meta name="robots" content="noindex"><meta http-equiv="refresh" content="0;url=planner.html"><title>Temoraxis</title></head><body><a href="planner.html">Открыть планёр</a></body></html>')
# An owner-facing setup page contains public schema only, never invitation codes or credentials.
setup=output/'setup';setup.mkdir()
sql=(ROOT/'supabase'/'schema.sql').read_text()
(setup/'schema.sql').write_text(sql)
(setup/'index.html').write_text('<!doctype html><html lang="ru"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1"><meta name="robots" content="noindex"><title>Настройка синхронизации Temoraxis</title><style>body{max-width:850px;margin:32px auto;padding:16px;background:#0a0a12;color:#eee;font:16px/1.6 system-ui}a{color:#a5b4ff}button{padding:12px;background:#6b85ff;color:white;border:0;border-radius:8px;font:inherit}textarea{width:100%;height:300px;background:#151522;color:#ddd}li{margin:12px 0}</style></head><body><h1>Однократная настройка облака</h1><ol><li>Откройте <a href="https://supabase.com/dashboard/project/udrlbmlofdzevwvzssfw/sql/new" target="_blank" rel="noopener">SQL Editor вашего проекта</a>.</li><li>Скопируйте SQL ниже, вставьте в New query и нажмите Run. Создаются только таблицы Temoraxis, правила доступа и функции. Данные не удаляются.</li><li>В Results появится invitation_code. Сохраните его у себя: он нужен для первого подключения аккаунтов. Не публикуйте код. При повторном запуске схемы старый код не меняется, результат будет пустым.</li><li>Authentication → URL Configuration: Site URL — <code>https://dfkzg.github.io/Temoraxis/app/planner.html</code>. Добавьте этот же адрес в Redirect URLs.</li><li>Для подтверждения email стандартная почта Supabase ограничена адресами участников проекта. Первый тест делайте со своим адресом владельца. Для остальных пользователей настройте SMTP; для закрытого теста по приглашениям можно временно выключить Confirm email в настройках Email, понимая, что адреса тогда не проверяются.</li><li>Откройте <a href="../app/planner.html">планёр на ПК</a>, Настройки → Синхронизация, выберите Облако Temoraxis и создайте аккаунт. Подтвердите email по письму, если требуется, затем войдите с кодом приглашения. На телефоне войдите в тот же аккаунт.</li></ol><button id="copy">Скопировать SQL</button><p id="status" role="status"></p><textarea id="sql" readonly aria-label="SQL настройки">'+html.escape(sql)+'</textarea><p><a href="schema.sql">Открыть SQL отдельным файлом</a></p><script>document.getElementById("copy").onclick=async()=>{const input=document.getElementById("sql");try{await navigator.clipboard.writeText(input.value);document.getElementById("status").textContent="Скопировано. Вставьте в SQL Editor.";}catch(e){input.focus();input.select();document.getElementById("status").textContent="Нажмите Ctrl+C или выберите «Копировать».";}};</script></body></html>')
# Ownership verification files, if supplied by the site owner.
for path in (ROOT/'docs').glob('google*.html'):
    shutil.copy2(path,output/path.name)
print('Public download site built:',output)
# Downloadable owner helper contains code/instructions only, never OAuth or age secrets.
import zipfile
backup_setup=setup/'backups';backup_setup.mkdir()
with zipfile.ZipFile(backup_setup/'connect-drive.zip','w',zipfile.ZIP_DEFLATED) as archive:
    for name in ['connect_drive.py','connect_drive.cmd']:
        archive.write(ROOT/'tools'/'backup'/name,name)
    archive.writestr('README.txt','Temoraxis: Google Drive backup setup\nInstall Python 3.10+ on your PC. Run connect_drive.cmd (Windows) or python connect_drive.py.\nInstructions: https://github.com/dfkzg/Temoraxis/blob/main/docs/BACKUPS.md\nSelect the Google account used for backups; it may differ from your planner account.\nNever publish OAuth credentials or the decryption key.\n')
(backup_setup/'index.html').write_text('''<!doctype html><html lang="ru"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1"><meta name="robots" content="noindex"><title>Резервные копии Temoraxis</title><style>body{max-width:750px;margin:32px auto;padding:16px;background:#0a0a12;color:#eee;font:16px/1.6 system-ui}a{color:#a5b4ff}li{margin:12px 0}input,button{font:inherit;padding:10px;border-radius:8px}input{max-width:90%;width:380px}code{overflow-wrap:anywhere}</style></head><body><h1>Резервная копия базы на Яндекс Диск</h1><p>Раздел для владельца сервера. Аккаунт хранилища может отличаться от аккаунта планёра. Обычным пользователям эта настройка не нужна.</p><p>Ежедневно в 04:23 по Москве; 14 зашифрованных копий данных приложения и пользователей. Старые копии удаляются только после проверенной загрузки новой. Настройки инфраструктуры Supabase и файлы с устройств не входят.</p><ol><li>Используйте уже сохранённый личный ключ age. Сохраните его отдельно от Диска с копиями. Менять ключ при смене хранилища не нужно.</li><li>Откройте <a href="https://oauth.yandex.ru/client/new/" target="_blank" rel="noopener">создание приложения Яндекса для доступа к API</a>. Название — Temoraxis backups, контактный email — свой. Тип — «Для доступа к API или отладки».</li><li>Доступ — только <strong>Доступ к папке приложения на Диске</strong>: <code>cloud_api:disk.app_folder</code>. Доступ ко всему Диску не нужен. Сохраните приложение.</li><li>На странице приложения найдите ClientID. Это публичный идентификатор, его можно вставить ниже. Client secret и токен сюда не вставляйте.</li></ol><label for="client">ClientID приложения Яндекса</label><p><input id="client" autocomplete="off" spellcheck="false" maxlength="32" placeholder="32 символа ClientID"></p><button id="build" type="button">Получить ссылку входа Яндекса</button><p id="link-status" role="status"></p><p><a id="authorize" hidden target="_blank" rel="noopener noreferrer">Открыть Яндекс и разрешить доступ к папке</a></p><p>Генератор работает в браузере, не получает и не сохраняет токен. После входа Яндекс покажет токен: сохраните его только в GitHub Secret <strong>BACKUP_YANDEX_TOKEN</strong>. Не присылайте токен или адрес страницы с ним в чат.</p><p>Ещё два секрета: <strong>BACKUP_AGE_RECIPIENT</strong> — публичный адрес age1… из страницы вашего ключа; <strong>SUPABASE_BACKUP_DB_URL</strong> — строка PostgreSQL Session pooler с портом 5432.</p><p><a href="https://github.com/dfkzg/Temoraxis/blob/main/docs/BACKUPS.md">Полная инструкция и восстановление</a> · <a href="https://github.com/dfkzg/Temoraxis/settings/secrets/actions">Секреты GitHub</a> · <a href="https://github.com/dfkzg/Temoraxis/actions/workflows/backup.yml">Запуски резервного копирования</a></p><details><summary>Дополнительный вариант: Google Диск</summary><p>Если Google Cloud доступен в вашей стране, можно подключить Google Диск вместо Яндекса. <a href="connect-drive.zip" download>Помощник Google Drive</a> требует Python 3.10+ на ПК. Инструкция выше содержит отдельный раздел для Google. Для Яндекс Диска помощник не нужен.</p></details><p>До подключения доступа и первого успешного запуска резервное копирование не включено. Приватные ключи и данные не содержатся на этой странице.</p><script>document.getElementById('build').onclick=()=>{const id=document.getElementById('client').value.trim(),a=document.getElementById('authorize');a.hidden=true;if(!/^[a-f0-9]{32}$/i.test(id)){document.getElementById('link-status').textContent='Нужен ClientID: 32 шестнадцатеричных символа. Токен и Client secret сюда не вставляйте.';return;}a.href='https://oauth.yandex.ru/authorize?response_type=token&client_id='+encodeURIComponent(id);a.hidden=false;document.getElementById('link-status').textContent='Откройте ссылку ниже под аккаунтом с нужным Яндекс Диском.';};</script></body></html>''')
