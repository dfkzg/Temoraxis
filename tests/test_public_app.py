"""Serve the real Pages build under its project prefix and test offline installation."""
import os,socket,subprocess,sys,tempfile,time,urllib.request
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]
subprocess.run([sys.executable,str(ROOT/'tools/prepare_pages.py')],check=True)
with tempfile.TemporaryDirectory() as directory:
 (Path(directory)/'Temoraxis').symlink_to(ROOT/'dist/pages',target_is_directory=True)
 sock=socket.socket();sock.bind(('127.0.0.1',0));port=sock.getsockname()[1];sock.close()
 server=subprocess.Popen([sys.executable,'-m','http.server',str(port),'--bind','127.0.0.1','--directory',directory],stdout=subprocess.DEVNULL,stderr=subprocess.DEVNULL)
 try:
  address=f'http://127.0.0.1:{port}'
  for _ in range(100):
   try:urllib.request.urlopen(address+'/Temoraxis/');break
   except Exception:time.sleep(.05)
  else:raise RuntimeError('Pages test server did not start')
  subprocess.run(['node',str(ROOT/'tests/browser_public_app.cjs')],env={**os.environ,'PAGES_TEST_URL':address},check=True,timeout=120)
 finally:server.terminate();server.wait()
