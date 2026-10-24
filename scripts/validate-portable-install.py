"""Exercise the unmodified native installer/app in an isolated macOS user home.
This is not a clean OS/VM: it intentionally denies host engines, user data and Xcode.
Uses only fictitious data and never reads or prints production session tokens.
"""
import argparse,hashlib,json,os,plistlib,re,secrets,signal,subprocess,tempfile,time,urllib.request
from pathlib import Path

parser=argparse.ArgumentParser();parser.add_argument('--installer',required=True);parser.add_argument('--report',required=True);args=parser.parse_args()
installer=Path(args.installer).resolve();work=Path(tempfile.mkdtemp(prefix='agentic-clean-install-',dir='/private/tmp'));home=work/'empty-user';home.mkdir();(home/'Desktop').mkdir();(work/'tmp').mkdir()
destination=home/'Applications With Spaces';app=destination/'Agentic Studio.app'
blocked=[str(Path.home()),'/Volumes','/opt/homebrew','/usr/local','/Applications/ChatGPT.app','/Applications/oMLX.app','/Applications/Xcode.app','/Applications/Xcode-beta.app','/Library/Developer','/usr/bin/python3']
profile='(version 1)(allow default)'+''.join('(deny file-read* file-write* (subpath '+json.dumps(p)+'))' for p in blocked)
profile+='(deny process-exec (literal "/usr/bin/python3"))'
env={'HOME':str(home),'CFFIXED_USER_HOME':str(home),'PATH':'/usr/bin:/bin:/usr/sbin:/sbin','TMPDIR':str(work/'tmp'),'SSL_CERT_FILE':'/etc/ssl/cert.pem','PYTHONDONTWRITEBYTECODE':'1'}
report={'isolated_user_home':True,'host_user_data_engines_and_xcode_denied':True,'clean_os_or_vm':False,'checks':{},'passed':False}
exe=installer/'Contents/MacOS/Instalar Agentic Studio';log=(work/'native.log').open('w');process=None
try:
 install=subprocess.run(['/usr/bin/sandbox-exec','-p',profile,str(exe),'--destination',str(destination),'--desktop','--no-launch'],env=env,capture_output=True,text=True,timeout=90)
 if install.returncode:raise RuntimeError('Installer failed: '+install.stdout[-500:]+install.stderr[-500:])
 info=plistlib.loads((app/'Contents/Info.plist').read_bytes());assert info['StudioWorkspace']=='@application-support';report['checks']['native_install_and_desktop_link']=(home/'Desktop/Agentic Studio.app').resolve()==app
 assert report['checks']['native_install_and_desktop_link']
 report['checks']['packaged_executables_have_execute_bits']=all(os.access(app/relative,os.X_OK) for relative in ('Contents/MacOS/Agentic Studio','Contents/Resources/python/bin/python3','Contents/Resources/codex/codex'))
 assert report['checks']['packaged_executables_have_execute_bits'],'Packaged executable permissions were lost'
 subprocess.run(['/usr/bin/codesign','--verify','--deep','--strict',str(app)],check=True,capture_output=True)
 process=subprocess.Popen(['/usr/bin/sandbox-exec','-p',profile,str(app/'Contents/MacOS/Agentic Studio')],env=env,stdout=log,stderr=log,start_new_session=True)
 backend=None
 for _ in range(160):
  if process.poll() is not None:raise RuntimeError('Native app exited before startup; see isolated native log.')
  children=subprocess.run(['/usr/bin/pgrep','-P',str(process.pid)],capture_output=True,text=True).stdout.split()
  for child in children:
   command=subprocess.check_output(['/bin/ps','-p',child,'-o','command='],text=True)
   if str(app/'Contents/Resources/prototype/server.py') in command:backend=int(child);break
  if backend:break
  time.sleep(.25)
 if not backend:raise RuntimeError('Native backend did not start.')
 # Read only the random token of this newly created fictitious instance, in memory.
 raw=subprocess.check_output(['/bin/ps','eww','-p',str(backend),'-o','command='],text=True);match=re.search(r'(?:^| )AGENTIC_STUDIO_TOKEN=([a-f0-9]{64})(?: |$)',raw);assert match;token=match.group(1);del raw
 for _ in range(80):
  ports=subprocess.run(['/usr/sbin/lsof','-Pan','-p',str(backend),'-iTCP','-sTCP:LISTEN','-Fn'],capture_output=True,text=True).stdout
  found=re.search(r'n127\.0\.0\.1:(\d+)',ports)
  if found:break
  time.sleep(.25)
 assert found,'Backend did not bind loopback'
 base='http://127.0.0.1:'+found.group(1)
 def api(path,body=None):
  req=urllib.request.Request(base+path,data=None if body is None else json.dumps(body).encode(),headers={'Authorization':'Bearer '+token,'Content-Type':'application/json'})
  with urllib.request.urlopen(req,timeout=40) as response:return json.load(response)
 state=api('/api/state');setup=api('/api/setup')
 assert not state['projects'] and not state['sessions'] and not state['engine']['running'] and state['setup_required']
 assert Path(state['data_path']).is_relative_to(home.resolve())
 assert not setup['detected'] and all(not v['installed'] for v in setup['runtimes'].values())
 assert setup['openai_available']
 report['checks'].update(native_backend_started=True,empty_projects_and_settings=True,data_outside_checkout=True,missing_engines_handled=True,bundled_openai_available=True)
 # The official helper must start without a host ChatGPT installation or saved account.
 status=api('/api/openai/status');assert status['connected'] is False;report['checks']['bundled_codex_clean_status']=True
 pid=api('/api/projects',{'name':'Fictitious portable QA','instructions':''})['id'];api('/api/file',{'project':pid,'path':'probe.txt','content':'PORTABLE-42'});assert api('/api/file?project='+pid+'&path=probe.txt')['content']=='PORTABLE-42'
 report['checks']['project_file_roundtrip']=True
 api('/api/setup',{'roots':[],'complete':True});assert api('/api/setup')['complete'];report['checks']['setup_saved_without_models']=True
 api('/api/memory/reclaim',{})
 process.terminate();process.wait(timeout=30);process=None
 for _ in range(80):
  ports=subprocess.run(['/usr/sbin/lsof','-Pan','-p',str(backend),'-iTCP','-sTCP:LISTEN'],capture_output=True,text=True)
  if not ports.stdout:break
  time.sleep(.25)
 else:raise RuntimeError('Owned backend did not stop after native app exit')
 report['checks']['owned_backend_stopped']=True
 # Updating a closed installation must preserve its data, without signing tools from Xcode.
 database=Path(state['data_path'])/'studio.sqlite3';before=hashlib.sha256(database.read_bytes()).hexdigest()
 update=subprocess.run(['/usr/bin/sandbox-exec','-p',profile,str(exe),'--destination',str(destination),'--update','--no-launch'],env=env,capture_output=True,text=True,timeout=90)
 assert update.returncode==0,update.stdout[-500:]+update.stderr[-500:]
 assert hashlib.sha256(database.read_bytes()).hexdigest()==before
 report['checks']['update_preserves_database']=True
 report['version']=info['CFBundleShortVersionString'];report['passed']=True
finally:
 if process and process.poll() is None:
  process.terminate()
  try:process.wait(timeout=20)
  except subprocess.TimeoutExpired:os.killpg(process.pid,signal.SIGKILL);process.wait()
 log.close();report['isolated_test_directory']=str(work);Path(args.report).write_text(json.dumps(report,indent=2));print(json.dumps(report,indent=2))
