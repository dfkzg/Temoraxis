"""Real PostgreSQL + age dump/decrypt/restore, isolated from the production database."""
import os,shutil,subprocess,tempfile,time,unittest,uuid
from pathlib import Path

class BackupRoundtrip(unittest.TestCase):
 def test_dump_encrypt_decrypt_restore(self):
  self.assertIsNotNone(shutil.which('age'));self.assertIsNotNone(shutil.which('age-keygen'))
  name='temoraxis-backup-test-'+uuid.uuid4().hex[:10]
  def docker(*args,input=None):return subprocess.run(['docker','exec','-i','-e','PGPASSWORD=local-test-only',name,*args],input=input,capture_output=True,check=True)
  def sql(text,db='postgres'):return docker('psql','-h','127.0.0.1','-U','postgres','-d',db,'-qAt','-v','ON_ERROR_STOP=1',input=text.encode()).stdout.decode().strip()
  subprocess.run(['docker','run','--rm','-d','--name',name,'-e','POSTGRES_PASSWORD=local-test-only','postgres:17-alpine'],check=True,stdout=subprocess.DEVNULL)
  try:
   for _ in range(100):
    if subprocess.run(['docker','exec',name,'pg_isready','-h','127.0.0.1','-U','postgres'],capture_output=True).returncode==0:break
    time.sleep(.25)
   else:self.fail('PostgreSQL startup failed')
   sql("create schema auth;create schema temoraxis_private;create table auth.users(id int primary key,email text);insert into auth.users values(1,'test@example.invalid');create table public.temoraxis_documents(user_id int references auth.users(id),document jsonb);insert into public.temoraxis_documents values(1,'{\"tasks\":[\"private fixture\"]}');create table temoraxis_private.config(invite_hash text);insert into temoraxis_private.config values('fixture-only');")
   with tempfile.TemporaryDirectory() as tmp:
    folder=Path(tmp);plain=folder/'database.dump';key=folder/'key.txt';encrypted=folder/'database.dump.age';restored=folder/'restored.dump'
    plain.write_bytes(docker('pg_dump','-h','127.0.0.1','-U','postgres','--format=custom','--no-owner','--no-acl','--schema=public','--schema=auth','--schema=temoraxis_private').stdout)
    subprocess.run(['age-keygen','-o',str(key)],capture_output=True,check=True)
    recipient=subprocess.check_output(['age-keygen','-y',str(key)],text=True).strip()
    import importlib.util
    spec=importlib.util.spec_from_file_location('drive_backup',Path(__file__).resolve().parents[1]/'tools/backup/drive_backup.py');backup=importlib.util.module_from_spec(spec);spec.loader.exec_module(backup)
    backup.encrypt_archive(plain,recipient);self.assertFalse(plain.exists())
    self.assertNotIn(b'private fixture',encrypted.read_bytes())
    subprocess.run(['age','-d','-i',str(key),'-o',str(restored),str(encrypted)],capture_output=True,check=True)
    sql('create database restore_test')
    sql('drop schema public','restore_test')
    # Empty local database, never --clean against an existing Supabase instance.
    docker('pg_restore','-h','127.0.0.1','-U','postgres','-d','restore_test','--no-owner','--no-acl',input=restored.read_bytes())
    self.assertEqual(sql('select email from auth.users','restore_test'),'test@example.invalid')
    self.assertIn('private fixture',sql('select document from public.temoraxis_documents','restore_test'))
    self.assertEqual(sql('select invite_hash from temoraxis_private.config','restore_test'),'fixture-only')
  finally:subprocess.run(['docker','stop',name],check=True,stdout=subprocess.DEVNULL)

if __name__=='__main__':unittest.main()
