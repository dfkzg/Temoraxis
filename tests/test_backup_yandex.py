"""Yandex API contract tests without real tokens or access to production files."""
import io,json,os,sys,tempfile,unittest,urllib.error
from pathlib import Path
from unittest.mock import patch
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'tools/backup'))
import drive_backup as common
import yandex_backup as yandex
import run_backup as runner

class YandexBackupTests(unittest.TestCase):
 def file(self,i):
  digest=f'{i:064x}';return {'name':f'temoraxis-202611{i+1:02d}T012300Z-{digest[:12]}.dump.age','type':'file','sha256':digest,'custom_properties':{'temoraxisBackupSet':common.SET,'format':'pg-custom-age-v1'}}
 def test_storage_links_must_be_yandex_https_and_never_accept_credentials(self):
  valid='https://uploader1d.dst.yandex.net:443/upload-target/fixture'
  self.assertEqual(yandex.storage_url({'href':valid,'method':'PUT'},'PUT'),valid)
  for url in ['http://uploader.yandex.net/file','https://evil.example/file','https://yandex.net.evil.example/file','https://name:password@uploader.yandex.net/file','https://uploader.yandex.net:123/file']:
   with self.assertRaises(common.BackupError):yandex.storage_url({'href':url,'method':'PUT'},'PUT')
 def test_existing_folder_must_be_directory(self):
  with patch.object(yandex,'api',side_effect=[common.BackupError('exists',409),{'type':'dir'}]):yandex.ensure_folder('token')
  with patch.object(yandex,'api',side_effect=[common.BackupError('exists',409),{'type':'file'}]):
   with self.assertRaises(common.BackupError):yandex.ensure_folder('token')
 def test_upload_validates_hash_before_marking_and_never_forwards_token(self):
  with tempfile.TemporaryDirectory() as tmp:
   path=Path(tmp)/'cipher.dump.age';path.write_bytes(b'age-ciphertext');digest=common.sha256(path);name='temoraxis-20261115T012300Z-'+digest[:12]+'.dump.age'
   responses=[{'href':'https://uploader.yandex.net/file','method':'PUT'},{'sha256':digest,'size':path.stat().st_size},{}]
   with patch.object(yandex,'api',side_effect=responses) as api,patch.object(yandex,'request',return_value=(201,{},b'')) as request:
    self.assertEqual(yandex.upload(path,'secret-token',name,digest),yandex.FOLDER+'/'+name)
    args,kwargs=request.call_args;self.assertEqual(args,('https://uploader.yandex.net/file',));self.assertNotIn('Authorization',kwargs['headers']);self.assertNotIn('token',kwargs)
    self.assertEqual(api.call_args_list[-1].kwargs['method'],'PATCH')
   responses[1]={'sha256':'b'*64,'size':path.stat().st_size}
   with patch.object(yandex,'api',side_effect=responses) as api,patch.object(yandex,'request',return_value=(201,{},b'')):
    with self.assertRaises(common.BackupError):yandex.upload(path,'secret-token',name,digest)
    self.assertEqual(api.call_count,2)
 def test_cleanup_filters_files_and_cannot_follow_returned_paths(self):
  files=[self.file(i) for i in range(16)];files[0]['path']='disk:/personal/important.txt'
  unrelated=self.file(20);unrelated['custom_properties']={'temoraxisBackupSet':'another-project'}
  pages=[{'_embedded':{'items':files[:10]+[unrelated,{'name':'family.jpg','type':'file'}],'total':18}}, {'_embedded':{'items':files[10:],'total':18}},None,None]
  with patch.object(yandex,'api',side_effect=pages) as api:
   self.assertEqual(yandex.prune('token',yandex.FOLDER+'/'+files[-1]['name']),2)
   deleted=[c.kwargs['path'] for c in api.call_args_list if c.kwargs.get('method')=='DELETE']
   self.assertEqual(deleted,[yandex.FOLDER+'/'+files[1]['name'],yandex.FOLDER+'/'+files[0]['name']])
   self.assertTrue(all(c.kwargs['permanently']=='true' for c in api.call_args_list if c.kwargs.get('method')=='DELETE'))
 def test_missing_new_backup_and_bad_pagination_stop_deletion(self):
  for page in [{'_embedded':{'items':[self.file(i) for i in range(16)],'total':16}},{'_embedded':{'items':[],'total':4}}]:
   with patch.object(yandex,'api',return_value=page) as api:
    with self.assertRaises(common.BackupError):yandex.prune('token',yandex.FOLDER+'/missing')
    self.assertTrue(all(c.kwargs.get('method')!='DELETE' for c in api.call_args_list))
 def test_readback_mismatch_blocks_verification(self):
  with patch.object(yandex,'api',return_value={'href':'https://downloader.disk.yandex.ru/file','method':'GET'}),patch.object(yandex.urllib.request,'urlopen',return_value=io.BytesIO(b'wrong-ciphertext')):
   with self.assertRaises(common.BackupError):yandex.verify_download('token','app:/file','a'*64)
 def test_failed_verification_never_deletes_old_copies(self):
  with tempfile.TemporaryDirectory() as tmp:
   path=Path(tmp)/'cipher.dump.age';path.write_bytes(b'ciphertext')
   env={'BACKUP_YANDEX_TOKEN':'fixture-yandex-token-only','SUPABASE_BACKUP_DB_URL':'private','BACKUP_AGE_RECIPIENT':'public'}
   with patch.dict(os.environ,env),patch.object(common,'dump_database',return_value=path),patch.object(common,'encrypt_archive',return_value=path),patch.object(yandex,'ensure_folder'),patch.object(yandex,'upload',return_value='app:/fixture'),patch.object(yandex,'verify_download',side_effect=common.BackupError('mismatch')),patch.object(yandex,'prune') as cleanup:
    with self.assertRaises(common.BackupError):runner.main()
    cleanup.assert_not_called()
 def test_whole_token_url_is_rejected_without_network(self):
  with patch.dict(os.environ,{'BACKUP_YANDEX_TOKEN':'https://oauth.yandex.ru/verification_code#access_token=secret'}),patch.object(yandex,'ensure_folder') as api:
   with self.assertRaises(common.BackupError):runner.main()
   api.assert_not_called()
 def test_google_remains_optional_when_yandex_not_configured(self):
  with patch.dict(os.environ,{'BACKUP_YANDEX_TOKEN':''}),patch.object(common,'main') as google:runner.main();google.assert_called_once()

if __name__=='__main__':unittest.main()
