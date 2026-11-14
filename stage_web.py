from pathlib import Path
import json,shutil
ROOT=Path(__file__).resolve().parent
SOURCE=ROOT/'web-source'
css=(SOURCE/'sync.css').read_text()
common=(SOURCE/'cloud-config.js').read_text()+'\n'+(SOURCE/'supabase.js').read_text()+'\n'+(SOURCE/'sync.js').read_text().replace("/*SYNC_CSS*/''",json.dumps(css,ensure_ascii=False))
for name in ['planner.html','Start_page.html']:
 s=(SOURCE/name).read_text()
 s=s.replace('<meta charset="UTF-8">','<meta charset="UTF-8">\n<link rel="manifest" href="manifest.webmanifest">\n<link rel="icon" href="icon.svg" type="image/svg+xml">\n<link rel="apple-touch-icon" href="icon-180.png">\n<meta name="theme-color" content="#0a0a12">',1)
 s=s.replace('Удалить все задачи, расписания, шаблоны, настройки и сохранённые звуки планёра? Это действие нельзя отменить.', 'Удалить все задачи, расписания, шаблоны, настройки и сохранённые звуки планёра? Если подключена синхронизация, удаление будет передано другим устройствам аккаунта. Это действие нельзя отменить.',1)
 s=s.replace('</body>','<script>\n'+common+'\n</script>\n</body>',1)
 if name=='planner.html':
  s=s.replace("e.target.checked?'Напоминания включены. Для системных уведомлений разрешите их в браузере.'","e.target.checked?(window.PlannerAndroid?'Напоминания включены. Разрешения Android доступны в меню ⋮.':'Напоминания включены. Для системных уведомлений разрешите их в браузере.')",1)
  s=s.replace('function checkTaskReminders() {\n  cleanPlannerHistory();','function checkTaskReminders() {\n  cleanPlannerHistory();\n  if(window.PlannerAndroid)return;',1)
  s=s.replace("const permission='Notification' in window?Notification.permission:'unsupported';", "const permission=window.PlannerAndroid?'native':('Notification' in window?Notification.permission:'unsupported');")
  s=s.replace("{granted:'Уведомления браузера разрешены.'", "{native:'Уведомления Android. Разрешения можно проверить в меню приложения ⋮.',granted:'Уведомления браузера разрешены.'",1)
  s=s.replace("bind('settingsNotificationPermission','click',async()=>{if(!('Notification'in window))return;", "bind('settingsNotificationPermission','click',async()=>{if(window.PlannerAndroid){PlannerAndroid.requestNotifications();return;}if(!('Notification'in window))return;",1)
  s=s.replace('function downloadPlannerJSON(value,name) {', "function downloadPlannerJSON(value,name) {\n  if(window.PlannerAndroid){PlannerAndroid.exportDocument(name,JSON.stringify(value,null,2));return;}",1)
  a=s.index('function hardDeleteTask(');b=s.index('\n}',a)
  s=s[:a]+'''function hardDeleteTask(id) {
  const tasks=getAllTasks(true).map(task=>task.id===id?{...task,deleted:true,updatedAt:now()}:task);
  return saveAllTasks(tasks);'''+s[b:]
  s=s.replace("if (!getTask(TasksUI.selectedId)","if (!getTask(TasksUI.selectedId)")
  # Native alarm reconciliation also follows JSON import and reset, which replace keys directly.
  s=s.replace('function refreshPlannerViews() {', "function refreshPlannerViews(options = {}) {\n  if(window.PlannerSync)PlannerSync.scheduleNative(true);",1)
  s=s.replace('closeTaskModal();closeTaskDetail();','if(!options.preserveDetail){closeTaskModal();closeTaskDetail();}',1)
  s=s.replace('renderTasks();populateSoundSelect();','renderTasks();populateSoundSelect();if(options.preserveDetail&&TasksUI.selectedId)openTaskDetail(TasksUI.selectedId,true,TasksUI.selectedDate);',1)
 else:
  s=s.replace("let uidCounter = 0; function uid() { return 'id_' + (++uidCounter).toString(36); }", "function uid() { return 'id_' + Date.now().toString(36) + '_' + Math.random().toString(36).slice(2,10); }")
  s=s.replace('href="${escapeAttr(link.url)}"','href="${escapeAttr(/^https?:\\/\\//i.test(link.url)?link.url:\'#\')}"')
  s=s.replace("if (!q) { document.getElementById('imageInput').click(); return false; }","if (!q) { if(window.PlannerAndroid){PlannerAndroid.openExternal('https://lens.google/');return false;} document.getElementById('imageInput').click(); return false; }",1)
  s=s.replace('function exportData() {', "function exportData() {\n  if(window.PlannerAndroid){PlannerAndroid.exportDocument('startpage-backup.json',JSON.stringify(data,null,2));return;}",1)
  s=s.replace("if (!parsed.groups) throw new Error('Неверный формат');", """if(!parsed||!Array.isArray(parsed.groups)||parsed.groups.some(g=>!g||!/^[A-Za-z0-9_-]{1,128}$/.test(g.id)||typeof g.name!=='string'||!Array.isArray(g.links)||g.links.some(l=>!l||!/^[A-Za-z0-9_-]{1,128}$/.test(l.id)||typeof l.name!=='string'||typeof l.url!=='string'||!/^https?:\\/\\//i.test(l.url))))throw new Error('Неверный формат ссылок или групп');""",1)
 for folder in [ROOT/'server'/'web',ROOT/'android'/'app'/'src'/'main'/'assets']:
  folder.mkdir(parents=True,exist_ok=True);(folder/name).write_text(s)
for name in ['manifest.webmanifest','sw.js','icon.svg','icon-180.png','icon-192.png','icon-512.png']:
 for folder in [ROOT/'server'/'web',ROOT/'android'/'app'/'src'/'main'/'assets']:
  shutil.copy2(SOURCE/name,folder/name)

# Include attribution in distributed APK/resources, not just in the source repository.
notices=(ROOT/'docs'/'THIRD-PARTY.md').read_text()+'\n\n'+(ROOT/'docs'/'licenses'/'Feather-MIT.txt').read_text()
for folder in [ROOT/'server'/'web',ROOT/'android'/'app'/'src'/'main'/'assets']:
 (folder/'THIRD-PARTY.txt').write_text(notices)
