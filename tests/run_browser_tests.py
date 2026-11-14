import os,socket,subprocess,sys,tempfile,time,urllib.request
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]
with tempfile.TemporaryDirectory() as folder:
 sock=socket.socket();sock.bind(('127.0.0.1',0));port=sock.getsockname()[1];sock.close()
 env={**os.environ,'PLANNER_DB':str(Path(folder)/'test.sqlite'),'PLANNER_PORT':str(port),'PLANNER_ALLOW_HTTP':'1','PLANNER_INVITE_CODE':'local-test-invite','PLANNER_TEST_URL':f'http://127.0.0.1:{port}'}
 server=subprocess.Popen([sys.executable,str(ROOT/'server'/'server.py')],env=env,stdout=subprocess.DEVNULL)
 try:
  for attempt in range(100):
   try:urllib.request.urlopen(env['PLANNER_TEST_URL']+'/api/health',timeout=.2);break
   except Exception:time.sleep(.05)
  else:raise RuntimeError('Test server did not start')
  for name in ['browser_sync.cjs','browser_accounts.cjs','browser_native_offline.cjs','browser_drafts.cjs','browser_calendar_overlay.cjs','browser_mobile_nav.cjs','browser_reminder_reschedule.cjs','browser_supabase.cjs']:
   subprocess.run(['node',str(ROOT/'tests'/name)],env=env,check=True,timeout=120)
 finally:server.terminate();server.wait()
