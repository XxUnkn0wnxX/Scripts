from __future__ import annotations
import json, os, plistlib, shutil, subprocess
from pathlib import Path
import pytest

ROOT = Path(__file__).resolve().parents[2]
SCRIPT = ROOT / "shell/prowlarr_bigsur.zsh"
ZSH = shutil.which("zsh")

def app(path: Path, marker="old"):
    exe = path / "Contents/MacOS/Prowlarr"
    exe.parent.mkdir(parents=True)
    exe.write_text(marker, encoding="utf-8")
    exe.chmod(0o755)
    info = path / "Contents/Info.plist"
    info.parent.mkdir(parents=True, exist_ok=True)
    info.write_bytes(plistlib.dumps({"CFBundleIdentifier":"com.osx.prowlarr.com","CFBundleExecutable":"Prowlarr","LSMinimumSystemVersion":"10.15","LSMinimumSystemVersionByArchitecture":{"x86_64":"10.15"}}))
    return path

@pytest.fixture
def env(tmp_path):
    home=tmp_path/"home"; home.mkdir(); (home/"Downloads").mkdir()
    fakebin=tmp_path/"fakebin"; fakebin.mkdir()
    log=tmp_path/"commands.log"
    for name,body in TOOLS.items():
        p=fakebin/name; p.write_text(body,encoding="utf-8"); p.chmod(0o755)
    return {"root":tmp_path,"home":home,"bin":fakebin,"log":log}

def run(env,*args,extra=None):
    if not any(arg in ("-h", "--help") for arg in args):
        assert args and not (args[0] == "--dl" and all(arg in ("--dl", "stable", "pre") for arg in args)), "actionable fixtures require an explicit temporary app path"
        for arg in args:
            if arg.endswith(".app"):
                assert (env["root"] / arg).resolve().is_relative_to(env["root"]), "fixture app paths must stay inside the temporary root"
    variables=os.environ.copy()
    variables.update({"HOME":str(env["home"]),"PATH":f'{env["bin"]}:{os.environ["PATH"]}',"CALL_LOG":str(env["log"]),"PROWLARR_MANAGE_LAUNCH_AGENT":"false","PROWLARR_LAUNCH_AGENT":"Prowlarr","PROWLARR_BACKUP_ZIP":str(env["root"] / "Prowlarr.backup.zip")})
    if extra: variables.update(extra)
    assert Path(variables["PROWLARR_BACKUP_ZIP"]).absolute().parent.resolve().is_relative_to(env["root"]), "fixture backup paths must stay inside the temporary root"
    return subprocess.run([ZSH or "zsh","-f",str(SCRIPT),*args],cwd=env["root"],env=variables,text=True,capture_output=True,timeout=20)

TOOLS={
 "PlistBuddy":'''#!/bin/sh
printf 'PlistBuddy %s\\n' "$*" >> "$CALL_LOG"
if [ -x /usr/libexec/PlistBuddy ]; then exec /usr/libexec/PlistBuddy "$@"; fi
exec python3 - "$@" <<'PY'
import plistlib,sys
try:
 obj=plistlib.load(open(sys.argv[-1],"rb"))
 for k in sys.argv[2].removeprefix("Print :").split(":"):
  obj=obj[int(k)] if isinstance(obj,list) else obj[k]
 if isinstance(obj,(dict,list)): raise ValueError()
 print(obj)
except Exception: raise SystemExit(1)
PY
''',
 "plutil":'''#!/bin/sh
printf 'plutil %s\\n' "$*" >> "$CALL_LOG"
if [ -x /usr/libexec/PlistBuddy ]; then exec /usr/bin/plutil "$@"; fi
exec python3 - "$@" <<'PY'
import plistlib,sys
try:
 a=sys.argv[1:]; assert a[0] in ("-replace", "-insert") and a[2]=="-string"
 path=a[-1]; obj=plistlib.load(open(path,"rb")); keys=a[1].split("."); cur=obj
 for k in keys[:-1]: cur=cur[k]
 assert (keys[-1] in cur) == (a[0]=="-replace")
 cur[keys[-1]]=a[3]
 with open(path,"wb") as f: plistlib.dump(obj,f)
except Exception: raise SystemExit(1)
PY
''',
 "osascript":'''#!/usr/bin/env python3
import os,sys
src,dst=sys.argv[-2:]
exclusive=", 4)" in sys.argv[4]
log=os.environ["CALL_LOG"]
with open(log,"a") as f: f.write(("rename " if exclusive else "publish ")+src+" -> "+dst+"\\n")
if not exclusive:
 if os.environ.get("FAIL_PUBLISH_KIND") and os.environ["FAIL_PUBLISH_KIND"] in os.path.basename(src): raise SystemExit(1)
 os.replace(src,dst); raise SystemExit(0)
count=sum(line.startswith("rename ") for line in open(log))
if os.environ.get("SECOND_SIGNAL_AT")==str(count):
 import signal
 os.kill(os.getppid(),signal.SIGINT)
if os.environ.get("INTERRUPT_RENAME_AT")==str(count):
 import signal
 os.kill(os.getppid(),getattr(signal, "SIG" + os.environ.get("INTERRUPT_SIGNAL", "TERM")))
 raise SystemExit(1)
if os.environ.get("FAIL_RENAME_AT")==str(count):
 if os.environ.get("CREATE_UNEXPECTED"): os.mkdir(dst)
 raise SystemExit(1)
if os.path.lexists(dst): raise SystemExit(1)
if os.environ.get("SWAP_SOURCE_AT_RENAME")==str(count):
 os.rename(src,src+".displaced-candidate")
 os.mkdir(src)
 with open(os.path.join(src,"user-data"),"w") as f: f.write("preserve this replacement")
os.rename(src,dst)
if os.environ.get("INTERRUPT_AFTER_RENAME_AT")==str(count):
 import signal
 os.kill(os.getppid(),getattr(signal, "SIG" + os.environ.get("INTERRUPT_SIGNAL", "TERM")))
 raise SystemExit(1)
''',
 "sleep":'''#!/bin/sh
exit 0
''',
 "lipo":'''#!/bin/sh
echo "lipo $*" >> "$CALL_LOG"
echo x86_64
''',
 "otool":'''#!/bin/sh
echo "otool $*" >> "$CALL_LOG"
if [ -n "${OTOOL_FIXTURE:-}" ]; then cat "$OTOOL_FIXTURE"; exit 0; fi
case "$2" in *.patched) min=11;; *) min=${OTOOL_MIN:-11};; esac
cat <<EOF
Load command 1
      cmd LC_BUILD_VERSION
  platform 1
       minos $min
         sdk 14.0
       ntools 1
         tool 3
      version 100.1
EOF
case "$2" in *.patched) [ "${FAIL_PATCHED_OTOOL:-0}" = 0 ] || exit 1;; esac
''',
 "vtool":'''#!/bin/sh
echo "vtool $*" >> "$CALL_LOG"
out=; src=; prev=
for arg in "$@"; do [ "$prev" = out ] && out=$arg; prev=; [ "$arg" = -output ] && prev=out; src=$arg; done
cp "$src" "$out"
''',
 "codesign":'''#!/bin/sh
echo "codesign $*" >> "$CALL_LOG"
last=
for arg in "$@"; do last=$arg; done
case "$*" in
 *--force*) [ "${FAIL_SIGN:-0}" = 0 ] && touch "$last/.signed";;
 *) if [ -n "${MUTATE_ORIGINAL:-}" ] && [ "${last##*/}" != candidate.app ]; then
      for original in "${last%/*}"/.Prowlarr.app.txn.*/original/Prowlarr.app; do
       [ -d "$original" ] || continue
       mv "$original" "$original.displaced"
       [ "$MUTATE_ORIGINAL" != substitute ] || mkdir "$original"
      done
      exit 1
    fi
    if [ "${FAIL_INSTALLED_VERIFY:-0}" = 1 ] && [ "${last##*/}" != candidate.app ]; then exit 1; fi
    [ "${FAIL_VERIFY:-0}" = 0 ] && [ -f "$last/.signed" ];;
esac
''',
 "ditto":'''#!/bin/sh
if [ "$1" = -c ] && [ -x /usr/bin/ditto ]; then
 printf 'ditto %s\\n' "$*" >> "$CALL_LOG"
 [ -z "${FAIL_BACKUP_CREATE:-}" ] || exit 1
 exec /usr/bin/ditto "$@"
fi
exec python3 - "$@" <<'PY'
import os,shutil,sys,zipfile
open(os.environ["CALL_LOG"],"a").write("ditto "+" ".join(sys.argv[1:])+"\\n")
a=sys.argv[1:]
if a[0]=="-c":
 if os.environ.get("FAIL_BACKUP_CREATE"): raise SystemExit(1)
 src,dst=a[-2:]
 with zipfile.ZipFile(dst,"w") as z:
  for root,dirs,files in os.walk(src):
   for name in files:
    path=os.path.join(root,name); z.write(path,os.path.relpath(path,os.path.dirname(src)))
elif a[0]=="-x":
 if os.environ.get("FAIL_EXTRACT"): raise SystemExit(1)
 os.makedirs(a[-1],exist_ok=True)
 shutil.copytree(os.environ["DOWNLOAD_APP"],os.path.join(a[-1],"Prowlarr.app"))
else: shutil.copytree(a[0],a[1])
PY
''',
 "unzip":'''#!/bin/sh
[ -z "${FAIL_BACKUP_CHECK:-}" ] || exit 1
if [ -x /usr/bin/unzip ]; then exec /usr/bin/unzip "$@"; fi
exec python3 - "$@" <<'PY'
import os,sys,zipfile
if os.environ.get("FAIL_BACKUP_CHECK"): raise SystemExit(1)
try:
 with zipfile.ZipFile(sys.argv[-1]) as z:
  assert z.testzip() is None
except Exception: raise SystemExit(1)
PY
''',
 "lsof":'''#!/bin/sh
echo "lsof $*" >> "$CALL_LOG"
[ "${BUSY:-0}" = 0 ] || echo 4242
''',
 "shasum":'''#!/usr/bin/env python3
import hashlib,os,sys
open(os.environ["CALL_LOG"],"a").write("shasum "+" ".join(sys.argv[1:])+"\\n")
print(hashlib.sha256(open(sys.argv[-1],"rb").read()).hexdigest(),sys.argv[-1])
if os.environ.get("FAIL_DOWNLOAD_HASH") and os.path.basename(sys.argv[-1]).startswith(".prowlarr-download."): raise SystemExit(1)
''',
 "lsregister":'''#!/bin/sh
echo "lsregister $*" >> "$CALL_LOG"
''',
 "launchctl":'''#!/usr/bin/env python3
import os,sys
a=sys.argv[1:]
open(os.environ["CALL_LOG"],"a").write("launchctl "+" ".join(a)+"\\n")
state=os.environ.get("JOB_STATE_FILE","")
loaded=bool(state and os.path.exists(state) and open(state).read()=="loaded")
if a[0]=="print":
 if os.environ.get("UNKNOWN_JOB_ERROR")=="1":
  print("unexpected launchctl error",file=sys.stderr); raise SystemExit(1)
 if loaded and a[1].startswith(os.environ.get("JOB_DOMAIN", "gui")+"/"):
  print("  program = " + os.environ.get("LOADED_EXEC",""))
  print("  arguments = " + os.environ.get("EXTRA_ARGUMENT", ""))
  raise SystemExit(0)
 print("Could not find service",file=sys.stderr); raise SystemExit(1)
if a[0]=="bootout":
 if os.environ.get("FAIL_UNLOAD")=="after":
  open(state,"w").write("unloaded"); raise SystemExit(1)
 if os.environ.get("FAIL_UNLOAD")=="before": raise SystemExit(1)
 open(state,"w").write("unloaded"); raise SystemExit(0)
if a[0]=="bootstrap":
 if os.environ.get("INTERRUPT_BOOTSTRAP"):
  import signal
  os.kill(os.getppid(),signal.SIGINT)
  raise SystemExit(1)
 if os.environ.get("FAIL_BOOTSTRAP")=="1": raise SystemExit(1)
 open(state,"w").write("loaded"); raise SystemExit(0)
raise SystemExit(1)
''',
 "mv":'''#!/usr/bin/env python3
import os,subprocess,sys
log=os.environ["CALL_LOG"]
open(log,"a").write("mv "+" ".join(sys.argv[1:])+"\\n")
count=sum(line.startswith("mv ") for line in open(log))
if os.environ.get("FAIL_MV_AT")==str(count): raise SystemExit(1)
raise SystemExit(subprocess.call(["/bin/mv",*sys.argv[1:]]))
''',
 "curl":'''#!/bin/sh
echo "curl $*" >> "$CALL_LOG"
out=
prev=
url=
for arg in "$@"; do [ "$prev" = out ] && out=$arg; prev=; [ "$arg" = -o ] && prev=out; case "$arg" in https://*) url=$arg;; esac; done
case "$url" in
 https://api.github.com/*) [ "${FAIL_CURL:-}" != metadata ] || exit 22; page=$(printf '%s' "$url" | sed 's/.*page=//'); cp "$METADATA_DIR/page$page.json" "$out" ;;
 https://github.com/Prowlarr/Prowlarr/releases/download/*) [ "${FAIL_CURL:-}" != archive ] || exit 22; printf '%s' "$ARCHIVE_CONTENT" > "$out" ;;
 *) exit 1 ;;
esac
''',
}
