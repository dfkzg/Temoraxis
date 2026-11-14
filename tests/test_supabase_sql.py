"""Test the actual migration in disposable PostgreSQL; no real Supabase credentials used."""
import concurrent.futures,json,subprocess,time,unittest,uuid
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]
class SupabaseSQLTests(unittest.TestCase):
 @classmethod
 def sql(cls,text,check=True):
  p=subprocess.run(['docker','exec','-i','-e','PGPASSWORD=local-test-only',cls.container,'psql','-h','127.0.0.1','-U','postgres','-qAt','-v','ON_ERROR_STOP=1'],input=text,text=True,capture_output=True)
  if check and p.returncode:raise AssertionError(p.stderr)
  return p
 @classmethod
 def setUpClass(cls):
  cls.container='temoraxis-sql-'+uuid.uuid4().hex[:10]
  subprocess.run(['docker','run','--rm','-d','--name',cls.container,'-e','POSTGRES_PASSWORD=local-test-only','postgres:17-alpine'],check=True,stdout=subprocess.DEVNULL)
  try:
   for _ in range(80):
    if subprocess.run(['docker','exec',cls.container,'pg_isready','-h','127.0.0.1','-U','postgres'],capture_output=True).returncode==0:break
    time.sleep(.25)
   else:raise RuntimeError('PostgreSQL did not start')
   cls.sql("""create role anon; create role authenticated; create schema auth;
create table auth.users(id uuid primary key);
create function auth.uid() returns uuid language sql stable as $$ select nullif(current_setting('request.jwt.claim.sub',true),'')::uuid $$;
grant usage on schema auth to anon,authenticated; grant execute on function auth.uid() to anon,authenticated;""")
   result=cls.sql((ROOT/'supabase/schema.sql').read_text()).stdout.strip().splitlines()
   cls.invite=result[-1];assert len(cls.invite)==64
  except BaseException:
   subprocess.run(['docker','stop',cls.container],stdout=subprocess.DEVNULL);raise
 @classmethod
 def tearDownClass(cls):subprocess.run(['docker','stop',cls.container],check=True,stdout=subprocess.DEVNULL)
 def user(self,joined=True):
  uid=str(uuid.uuid4());self.sql("insert into auth.users values('"+uid+"');")
  if joined:self.as_user(uid,"select public.temoraxis_join('"+self.invite+"')")
  return uid
 def as_user(self,uid,statement,check=True,role='authenticated'):
  return self.sql("begin; set local role "+role+"; select set_config('request.jwt.claim.sub','"+uid+"',true); "+statement+"; commit;",check)
 def document(self,title='Test'):
  return {'tasks':[{'id':'task-1','title':title}],'clock':{'overrides':{},'custom':[]},'specialDates':[],'tags':[],'startPage':None}
 def push(self,uid,rev,doc):
  raw=json.dumps(doc).replace("'","''")
  result=self.as_user(uid,"select public.temoraxis_push("+str(rev)+",'"+raw+"'::jsonb)")
  return json.loads(result.stdout.strip().splitlines()[-1])
 def test_owner_isolation_and_no_direct_writes(self):
  a,b=self.user(),self.user();self.assertEqual(self.push(a,0,self.document())['revision'],1)
  self.assertEqual(self.as_user(b,'select count(*) from public.temoraxis_documents').stdout.strip().splitlines()[-1],'0')
  self.assertEqual(self.as_user(a,'select count(*) from public.temoraxis_documents').stdout.strip().splitlines()[-1],'1')
  denied=self.as_user(a,"update public.temoraxis_documents set revision=99",False);self.assertNotEqual(denied.returncode,0);self.assertIn('permission denied',denied.stderr)
  denied=self.as_user(a,'select * from temoraxis_private.config',False);self.assertNotEqual(denied.returncode,0);self.assertIn('permission denied',denied.stderr)
 def test_private_config_has_rls_without_client_policies(self):
  enabled=self.sql("select relrowsecurity from pg_class where oid='temoraxis_private.config'::regclass").stdout.strip()
  self.assertEqual(enabled,'t')
  policies=self.sql("select count(*) from pg_policies where schemaname='temoraxis_private' and tablename='config'").stdout.strip()
  self.assertEqual(policies,'0')
 def test_invitation_and_anonymous_access(self):
  uid=self.user(False)
  denied=self.as_user(uid,"select public.temoraxis_join('incorrect-invitation')",False);self.assertNotEqual(denied.returncode,0)
  denied=self.as_user(uid,"select public.temoraxis_push(0,'{}')",False);self.assertNotEqual(denied.returncode,0)
  denied=self.as_user('',"select public.temoraxis_join('incorrect-invitation')",False,role='anon');self.assertNotEqual(denied.returncode,0);self.assertIn('permission denied',denied.stderr)
  self.assertEqual(self.as_user(uid,"select public.temoraxis_join('"+self.invite+"')").stdout.strip().splitlines()[-1],'t')
  self.assertEqual(self.as_user(uid,"select public.temoraxis_join('')").stdout.strip().splitlines()[-1],'t')
 def test_atomic_creation_updates_and_validation(self):
  uid=self.user()
  with concurrent.futures.ThreadPoolExecutor(2) as pool:result=list(pool.map(lambda text:self.push(uid,0,self.document(text)),['one','two']))
  self.assertEqual(sum(bool(v.get('conflict')) for v in result),1)
  with concurrent.futures.ThreadPoolExecutor(2) as pool:result=list(pool.map(lambda text:self.push(uid,1,self.document(text)),['three','four']))
  self.assertEqual(sum(bool(v.get('conflict')) for v in result),1)
  self.assertEqual(max(v['revision'] for v in result),2)
  bad=self.document();bad['startPage']={'groups':[{'id':'g','name':'g','links':[{'id':'l','name':'l','url':'javascript:alert(1)'}]}]}
  with self.assertRaises(AssertionError):self.push(uid,2,bad)
  duplicate=self.document();duplicate['tasks']*=2
  with self.assertRaises(AssertionError):self.push(uid,2,duplicate)
 def test_migration_repeat_preserves_data_and_invite(self):
  uid=self.user();self.push(uid,0,self.document())
  self.sql((ROOT/'supabase/schema.sql').read_text())
  self.assertEqual(self.as_user(uid,'select count(*) from public.temoraxis_documents').stdout.strip().splitlines()[-1],'1')
  new=self.user(False);self.assertEqual(self.as_user(new,"select public.temoraxis_join('"+self.invite+"')").stdout.strip().splitlines()[-1],'t')
if __name__=='__main__':unittest.main()
