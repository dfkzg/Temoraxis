import concurrent.futures, json, os, socket, subprocess, sys, tempfile, time, unittest, urllib.request, urllib.error
from pathlib import Path

ROOT=Path(__file__).resolve().parents[1]
class ServerTests(unittest.TestCase):
 @classmethod
 def setUpClass(cls):
  cls.temp=tempfile.TemporaryDirectory(); sock=socket.socket();sock.bind(('127.0.0.1',0));cls.port=sock.getsockname()[1];sock.close();cls.url=f'http://127.0.0.1:{cls.port}'
  env={**os.environ,'PLANNER_DB':str(Path(cls.temp.name)/'test.sqlite'),'PLANNER_PORT':str(cls.port),'PLANNER_ALLOW_HTTP':'1','PLANNER_INVITE_CODE':'test-invite-only'}
  cls.process=subprocess.Popen([sys.executable,str(ROOT/'server'/'server.py')],env=env,stdout=subprocess.DEVNULL)
  for _ in range(100):
   try:urllib.request.urlopen(cls.url+'/api/health',timeout=.2);break
   except Exception:time.sleep(.05)
  else:raise RuntimeError('Server did not start')
 @classmethod
 def tearDownClass(cls):cls.process.terminate();cls.process.wait();cls.temp.cleanup()
 def api(self,path,method='GET',value=None,token=None,origin=None):
  headers={'Content-Type':'application/json'}
  if token:headers['Authorization']='Bearer '+token
  if origin:headers['Origin']=origin
  request=urllib.request.Request(self.url+path,data=json.dumps(value).encode() if value is not None else None,method=method,headers=headers)
  try:
   with urllib.request.urlopen(request,timeout=10) as response:return response.status,json.loads(response.read()),dict(response.headers)
  except urllib.error.HTTPError as error:return error.code,json.loads(error.read()),dict(error.headers)
 def register(self,username):
  code,result,_=self.api('/api/register','POST',{'username':username,'password':'a-long-test-password','inviteCode':'test-invite-only'})
  self.assertEqual(code,200,result);return result['token']
 def doc(self,title='Test'):
  return {'tasks':[{'id':'task-1','title':title}],'clock':{'overrides':{},'custom':[]},'specialDates':[],'tags':[],'startPage':None}
 def test_accounts_isolated_and_revision_conflicts(self):
  first=self.register('user-first');second=self.register('user-second')
  self.assertEqual(self.api('/api/sync')[0],401)
  self.assertEqual(self.api('/api/sync',token=first)[1]['revision'],0)
  code,result,_=self.api('/api/sync','PUT',{'expectedRevision':0,'document':self.doc()},first);self.assertEqual(code,200);self.assertEqual(result['revision'],1)
  self.assertIsNone(self.api('/api/sync',token=second)[1]['document'])
  self.assertEqual(self.api('/api/sync','PUT',{'expectedRevision':0,'document':self.doc('stale')},first)[0],409)
  self.assertEqual(self.api('/api/sync',token=first)[1]['document']['tasks'][0]['title'],'Test')
 def test_login_logout_and_invite(self):
  token=self.register('login-user')
  self.assertEqual(self.api('/api/login','POST',{'username':'login-user','password':'wrong-password'})[0],401)
  self.assertEqual(self.api('/api/register','POST',{'username':'bad-user','password':'a-long-test-password','inviteCode':'wrong'})[0],403)
  code,result,_=self.api('/api/login','POST',{'username':'LOGIN-USER','password':'a-long-test-password'});self.assertEqual(code,200)
  self.assertEqual(self.api('/api/logout','POST',{},result['token'])[0],200)
  self.assertEqual(self.api('/api/sync',token=result['token'])[0],401)
  self.assertEqual(self.api('/api/sync',token=token)[0],200)
 def test_cors_validation_and_concurrent_writes(self):
  token=self.register('concurrent-user')
  self.assertEqual(self.api('/api/sync',token=token,origin='https://evil.invalid')[0],403)
  code,_,headers=self.api('/api/sync',token=token,origin='https://appassets.androidplatform.net');self.assertEqual(code,200);self.assertEqual(headers['Access-Control-Allow-Origin'],'https://appassets.androidplatform.net')
  bad=self.doc();bad['startPage']={'groups':[{'id':'g','name':'g','links':[{'id':'l','name':'l','url':'javascript:alert(1)'}]}]}
  self.assertEqual(self.api('/api/sync','PUT',{'expectedRevision':0,'document':bad},token)[0],400)
  with concurrent.futures.ThreadPoolExecutor(2) as pool:codes=list(pool.map(lambda title:self.api('/api/sync','PUT',{'expectedRevision':0,'document':self.doc(title)},token)[0],['one','two']))
  self.assertEqual(sorted(codes),[200,409])
 def test_static_routes_do_not_expose_data(self):
  self.assertEqual(self.api('/data/planner.sqlite')[0],404)
  self.assertEqual(self.api('/../server.py')[0],404)

if __name__=='__main__':unittest.main()
