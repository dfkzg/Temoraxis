"""Backups must fail closed, keep unrelated Drive files, and never leak credentials."""
import base64,hashlib,importlib.util,json,os,tempfile,unittest,urllib.parse,urllib.request
from pathlib import Path
from unittest.mock import patch
ROOT=Path(__file__).resolve().parents[1]
spec=importlib.util.spec_from_file_location('drive_backup',ROOT/'tools/backup/drive_backup.py');backup=importlib.util.module_from_spec(spec);spec.loader.exec_module(backup)

class BackupTests(unittest.TestCase):
 def test_connection_requires_verified_tls_and_session_pooler(self):
  env=backup.postgres_env('postgresql://postgres.project:p%40ss%3Aword@aws-0-eu.pooler.supabase.com:5432/postgres?sslmode=disable')
  self.assertEqual(env['PGPASSWORD'],'p@ss:word');self.assertEqual(env['PGSSLMODE'],'verify-full');self.assertEqual(env['PGSSLROOTCERT'],'system')
  for url in ['postgres://u:p@evil.example:5432/postgres','postgres://u:p@aws-0-eu.pooler.supabase.com:6543/postgres','https://db.project.supabase.co/postgres','postgres://u@db.project.supabase.co/postgres']:
   with self.assertRaises(backup.BackupError):backup.postgres_env(url)
 def file(self,i):
  return {'id':str(i),'name':f'temoraxis-20261115T012300Z-{i:012x}.dump.age','createdTime':f'2026-11-{i+1:02d}T01:23:00Z','appProperties':{'temoraxisBackupSet':backup.SET,'format':'pg-custom-age-v1','sha256':'a'*64}}
 def test_cleanup_paginates_and_never_selects_other_files(self):
  pages=[{'files':[self.file(i) for i in range(10)]+[{'id':'other','name':'family-photo.jpg'}],'nextPageToken':'second'}, {'files':[self.file(i) for i in range(10,16)]}]
  with patch.object(backup,'json_request',side_effect=pages) as listing,patch.object(backup,'request') as deleting:
   self.assertEqual(backup.prune('token','folder','15'),2)
   self.assertEqual([call.args[0].rsplit('/',1)[1] for call in deleting.call_args_list],['1','0'])
   self.assertIn('pageToken=second',listing.call_args_list[1].args[0])
 def test_missing_new_backup_blocks_cleanup(self):
  with patch.object(backup,'list_backups',return_value=[self.file(i) for i in range(16)]),patch.object(backup,'request') as deleting:
   with self.assertRaises(backup.BackupError):backup.prune('token','folder','missing')
   deleting.assert_not_called()
 def test_checksum_failure_never_prunes(self):
  with tempfile.TemporaryDirectory() as tmp:
   f=Path(tmp)/'database.dump.age';f.write_bytes(b'ciphertext')
   env={'BACKUP_GOOGLE_DRIVE_JSON':json.dumps({'folder_id':'folder'}),'SUPABASE_BACKUP_DB_URL':'private-url','BACKUP_AGE_RECIPIENT':'recipient'}
   with patch.dict(os.environ,env),patch.object(backup,'access_token',return_value='token'),patch.object(backup,'dump_database',return_value=f),patch.object(backup,'encrypt_archive',return_value=f),patch.object(backup,'upload',return_value='new'),patch.object(backup,'verify_download',side_effect=backup.BackupError('checksum mismatch')),patch.object(backup,'prune') as pruning:
    with self.assertRaises(backup.BackupError):backup.main()
    pruning.assert_not_called()
 def test_upload_streams_encrypted_file_and_validates_metadata(self):
  with tempfile.TemporaryDirectory() as tmp:
   f=Path(tmp)/'database.dump.age';f.write_bytes(b'age-encrypted-test-content');digest=backup.sha256(f);calls=[]
   def send(url,token,method,data,headers):
    calls.append((url,method))
    if method=='POST':
     self.assertEqual(json.loads(data)['appProperties']['sha256'],digest)
     return 200,{'Location':'https://www.googleapis.com/upload/drive/v3/files?upload_id=test'},b''
    self.assertEqual(data.read(),f.read_bytes())
    return 200,{},json.dumps({'id':'new','size':str(f.stat().st_size),'appProperties':{'sha256':digest}}).encode()
   with patch.object(backup,'request',side_effect=send):self.assertEqual(backup.upload(f,'token','folder','test.dump.age',digest),'new')
   self.assertEqual(len(calls),2)
 def test_redirect_cannot_leak_bearer_token(self):
  with tempfile.TemporaryDirectory() as tmp:
   f=Path(tmp)/'test';f.write_bytes(b'test')
   with patch.object(backup,'request',return_value=(200,{'Location':'https://evil.example/upload'},b'')) as send:
    with self.assertRaises(backup.BackupError):backup.upload(f,'secret-token','folder','test',backup.sha256(f))
    self.assertEqual(send.call_count,1)
 def test_encryption_failure_cannot_upload_plaintext(self):
  with tempfile.TemporaryDirectory() as tmp:
   f=Path(tmp)/'database.dump';f.write_bytes(b'private')
   with self.assertRaises(backup.BackupError):backup.encrypt_archive(f,'invalid-key')
   self.assertEqual(f.read_bytes(),b'private')

class OAuthHelperTests(unittest.TestCase):
 def test_oauth_uses_state_pkce_and_only_app_files(self):
  spec=importlib.util.spec_from_file_location('connect_drive',ROOT/'tools/backup/connect_drive.py');helper=importlib.util.module_from_spec(spec);spec.loader.exec_module(helper)
  authorize={};client={'client_id':'fixture.apps.googleusercontent.com','client_secret':'fixture-only'}
  def open_browser(url):
   authorize.update(urllib.parse.parse_qs(urllib.parse.urlsplit(url).query))
   self.assertEqual(authorize['scope'],[helper.SCOPE]);self.assertEqual(authorize['code_challenge_method'],['S256'])
   callback=authorize['redirect_uri'][0]
   # Wrong state must not complete authorization.
   with self.assertRaises(urllib.error.HTTPError):urllib.request.urlopen(callback+'?state=wrong&code=bad')
   with urllib.request.urlopen(callback+'?'+urllib.parse.urlencode({'state':authorize['state'][0],'code':'fixture-code'})) as r:self.assertEqual(r.status,200)
   return True
  def post(url,body,token=None):
   if url.endswith('/token'):
    self.assertEqual(body['code'],'fixture-code')
    challenge=base64.urlsafe_b64encode(hashlib.sha256(body['code_verifier'].encode()).digest()).rstrip(b'=').decode()
    self.assertEqual(challenge,authorize['code_challenge'][0])
    return {'refresh_token':'fixture-refresh','access_token':'fixture-token','scope':helper.SCOPE}
   self.assertEqual(token,'fixture-token');self.assertEqual(body['mimeType'],'application/vnd.google-apps.folder')
   return {'id':'new-folder'}
  with patch.object(helper,'post',side_effect=post):result=helper.connect(client,open_browser)
  self.assertEqual(result['folder_id'],'new-folder');self.assertEqual(result['refresh_token'],'fixture-refresh')

if __name__=='__main__':unittest.main()
