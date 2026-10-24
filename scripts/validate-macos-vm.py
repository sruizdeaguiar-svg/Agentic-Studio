"""Exercise the public native installer/app in a dedicated disposable macOS VM.
Refuses a physical host or a guest containing developer tools.
Run with the packaged Python using -B and PYTHONDONTWRITEBYTECODE=1.
Uses only fictitious data and never reads or prints production session tokens.
"""
import argparse,hashlib,json,os,plistlib,re,secrets,signal,subprocess,tempfile,time,urllib.request
from pathlib import Path

parser=argparse.ArgumentParser();parser.add_argument('--installer',required=True);parser.add_argument('--report',required=True);args=parser.parse_args()
installer=Path(args.installer).resolve();work=Path(tempfile.mkdtemp(prefix='agentic-real-vm-',dir='/private/tmp'));home=Path.home()
destination=home/'Agentic QA Applications';app=destination/'Agentic Studio.app'
env=dict(os.environ);env.update(PATH='/usr/bin:/bin:/usr/sbin:/sbin',PYTHONDONTWRITEBYTECODE='1')
def shell(*args):return subprocess.run(args,capture_output=True,text=True)
assert shell('/usr/sbin/sysctl','-n','hw.model').stdout.strip().startswith('VirtualMac'),'Requires a real virtual Mac'
assert not list(Path('/Applications').glob('Xcode*.app')) and not list((home/'Applications').glob('Xcode*.app'))
assert not Path('/Library/Developer/CommandLineTools').exists()
assert not Path('/opt/homebrew').exists() and not Path('/usr/local/bin/brew').exists()
assert not Path('/Applications/ChatGPT.app').exists() and not (home/'Applications/ChatGPT.app').exists()
assert shell('/usr/bin/xcode-select','-p').returncode != 0
assert 'enabled' in shell('/usr/sbin/spctl','--status').stdout
report={'real_macos_vm':True,'clean_os_or_vm':True,'guest_os':shell('/usr/bin/sw_vers').stdout,'hardware':shell('/usr/sbin/sysctl','-n','hw.model').stdout.strip(),'xcode_homebrew_chatgpt_absent':True,'gatekeeper_enabled':True,'checks':{},'passed':False}
exe=installer/'Contents/MacOS/Instalar Agentic Studio';log=(work/'native.log').open('w');process=None
try:
 collision=work/'Conflict Install';other=collision/'Agentic Studio.app/Contents';other.mkdir(parents=True);(other/'Info.plist').write_bytes(plistlib.dumps({'CFBundleIdentifier':'invalid.qa.other','CFBundleName':'Other QA App'}))
 reject=subprocess.run([str(exe),'--destination',str(collision),'--no-launch'],env=env,capture_output=True,text=True,timeout=15)
 assert reject.returncode==2,'Installer must reject a different application and exit promptly'
 report['checks']['conflicting_application_rejected']=True
 install=subprocess.run([str(exe),'--destination',str(destination),'--desktop','--no-launch'],env=env,capture_output=True,text=True,timeout=90)
 if install.returncode:raise RuntimeError('Installer failed: '+install.stdout[-500:]+install.stderr[-500:])
 info=plistlib.loads((app/'Contents/Info.plist').read_bytes());assert info['StudioWorkspace']=='@application-support';report['checks']['native_install_and_desktop_link']=(home/'Desktop/Agentic Studio.app').resolve()==app
 assert report['checks']['native_install_and_desktop_link']
 report['checks']['packaged_executables_have_execute_bits']=all(os.access(app/relative,os.X_OK) for relative in ('Contents/MacOS/Agentic Studio','Contents/Resources/python/bin/python3','Contents/Resources/codex/codex'))
 assert report['checks']['packaged_executables_have_execute_bits'],'Packaged executable permissions were lost'
 subprocess.run(['/usr/bin/codesign','--verify','--deep','--strict',str(app)],check=True,capture_output=True)
 process=subprocess.Popen([str(app/'Contents/MacOS/Agentic Studio')],env=env,stdout=log,stderr=log,start_new_session=True)
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
 # The official helper starts in the unchanged product sandbox on the real guest.
 helper_script='import sys,json;sys.path.insert(0,sys.argv[1]);import openai_oauth;c=openai_oauth.Client(sys.argv[2]);print(json.dumps(c.status()));c.close()'
 helper=subprocess.run([str(app/'Contents/Resources/python/bin/python3'),'-c',helper_script,str(app/'Contents/Resources/prototype'),str(home/'isolated-codex')],env=env,capture_output=True,text=True,timeout=45)
 if helper.returncode:raise RuntimeError('Bundled Codex test failed: '+helper.stderr[-800:])
 status=json.loads(helper.stdout);assert status['connected'] is False;report['checks']['bundled_codex_clean_status_in_own_sandbox']=True
 pid=api('/api/projects',{'name':'Fictitious portable QA','instructions':''})['id'];api('/api/file',{'project':pid,'path':'probe.txt','content':'PORTABLE-42'});assert api('/api/file?project='+pid+'&path=probe.txt')['content']=='PORTABLE-42'
 report['checks']['project_file_roundtrip']=True
 api('/api/setup',{'roots':[],'complete':True});assert api('/api/setup')['complete'];report['checks']['setup_saved_without_models']=True
 # Do not invoke global stop: it explicitly controls the user's external LM Studio.
 process.terminate();process.wait(timeout=30);process=None
 for _ in range(80):
  ports=subprocess.run(['/usr/sbin/lsof','-Pan','-p',str(backend),'-iTCP','-sTCP:LISTEN'],capture_output=True,text=True)
  if not ports.stdout:break
  time.sleep(.25)
 else:raise RuntimeError('Owned backend did not stop after native app exit')
 report['checks']['owned_backend_stopped']=True
 # Updating a closed installation must preserve its data, without signing tools from Xcode.
 database=Path(state['data_path'])/'studio.sqlite3';before=hashlib.sha256(database.read_bytes()).hexdigest()
 update=subprocess.run([str(exe),'--destination',str(destination),'--update','--no-launch'],env=env,capture_output=True,text=True,timeout=90)
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
