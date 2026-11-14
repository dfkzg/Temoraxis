"""Local administration: accounts, password reset and consistent SQLite backup."""
import argparse,getpass,re,secrets,sqlite3
from pathlib import Path
import server

def main():
 parser=argparse.ArgumentParser();sub=parser.add_subparsers(dest='command',required=True)
 for command in ['create-user','reset-password']:sub.add_parser(command).add_argument('username')
 sub.add_parser('list-users');sub.add_parser('backup').add_argument('destination')
 args=parser.parse_args();server.init_db()
 if args.command=='backup':
  target=Path(args.destination).resolve()
  if target==server.DB.resolve():raise SystemExit('Backup must use a different file.')
  if target.exists():raise SystemExit('Destination already exists; choose a new filename.')
  target.parent.mkdir(parents=True,exist_ok=True)
  with server.connect() as source,sqlite3.connect(target) as destination:source.backup(destination)
  target.chmod(0o600);print('Backup saved:',target);return
 with server.connect() as db:
  if args.command=='list-users':
   for row in db.execute('SELECT username FROM users ORDER BY username'):print(row[0])
   return
  username=args.username.strip().casefold()
  if not 3<=len(username)<=100 or not re.fullmatch(r'[\w@.+-]+',username):raise SystemExit('Invalid username.')
  password=getpass.getpass('Password (10+ characters): ')
  if not 10<=len(password)<=256 or password!=getpass.getpass('Repeat password: '):raise SystemExit('Passwords differ or password length is invalid.')
  salt=secrets.token_bytes(16);derived=server.password_hash(password,salt)
  if args.command=='create-user':
   try:db.execute('INSERT INTO users VALUES(?,?,?,?)',(secrets.token_hex(16),username,salt,derived))
   except sqlite3.IntegrityError:raise SystemExit('User already exists.')
  else:
   row=db.execute('SELECT id FROM users WHERE username=?',(username,)).fetchone()
   if not row:raise SystemExit('User not found.')
   db.execute('UPDATE users SET salt=?,password=? WHERE id=?',(salt,derived,row[0]));db.execute('DELETE FROM sessions WHERE user_id=?',(row[0],))
 print('Done.')
if __name__=='__main__':main()
