"""Build the public download site without publishing maintenance documents or duplicate assets in Git."""
from pathlib import Path
import html,json,runpy,shutil
ROOT=Path(__file__).resolve().parents[1]
output=ROOT/'dist'/'pages'
if output.exists():shutil.rmtree(output)
output.mkdir(parents=True)
for name in ['index.html','sitemap.xml','.nojekyll']:
    shutil.copy2(ROOT/'docs'/name,output/name)
for name in ['icon.svg','icon-512.png']:
    shutil.copy2(ROOT/'web-source'/name,output/name)
# Build a browser app from the same sources as Android; never maintain another HTML copy.
runpy.run_path(str(ROOT/'stage_web.py'))
app=output/'app';app.mkdir()
for name in ['planner.html','Start_page.html','manifest.webmanifest','sw.js','icon.svg','icon-180.png','icon-192.png','icon-512.png','THIRD-PARTY.txt']:
    shutil.copy2(ROOT/'server'/'web'/name,app/name)
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
(backup_setup/'index.html').write_text('''<!doctype html><html lang="ru"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1"><meta name="robots" content="noindex"><title>Резервные копии Temoraxis</title><style>body{max-width:750px;margin:32px auto;padding:16px;background:#0a0a12;color:#eee;font:16px/1.6 system-ui}a{color:#a5b4ff}li{margin:12px 0}</style></head><body><h1>Резервная копия базы на Google Диск</h1><p>Раздел для владельца сервера. Аккаунт Google может отличаться от аккаунта планёра. Обычным пользователям эта настройка не нужна.</p><p>Ежедневно в 04:23 по Москве; 14 зашифрованных копий данных приложения и пользователей. Старые копии удаляются только после проверенной загрузки новой. Настройки инфраструктуры Supabase и файлы с устройств не входят.</p><ol><li>Сохраните личный ключ расшифровки отдельно от Диска с копиями.</li><li>Создайте Google OAuth-клиент типа Desktop app с доступом drive.file по инструкции. Переведите OAuth-приложение в Production, чтобы тестовый доступ не истёк через 7 дней.</li><li><a href="connect-drive.zip" download>Скачайте помощник подключения Google Диска</a>. Нужен Python 3.10+ на ПК. Распакуйте ZIP, запустите connect_drive.cmd на Windows или connect_drive.py через Python. Выберите нужный Google-аккаунт.</li><li>Сохраните три секрета в настройках GitHub. Не отправляйте их в чат и не загружайте в файлы репозитория.</li><li>Запустите workflow вручную и проверьте появление копии на Диске.</li></ol><p><a href="https://github.com/dfkzg/Temoraxis/blob/main/docs/BACKUPS.md">Полная инструкция и восстановление</a></p><p><a href="https://console.cloud.google.com/">Открыть Google Cloud</a> · <a href="https://github.com/dfkzg/Temoraxis/settings/secrets/actions">Секреты GitHub</a> · <a href="https://github.com/dfkzg/Temoraxis/actions/workflows/backup.yml">Запуски резервного копирования</a></p><p>До подключения доступа и первого успешного запуска резервное копирование не включено. Приватные ключи и данные не содержатся на этой странице или в ZIP помощника.</p></body></html>''')
