"""Inspect source, embedded templates and reachable Git blobs without printing values."""
import argparse, base64, io, json, os, re, subprocess, sys, zipfile
from pathlib import Path
from xml.etree import ElementTree as ET

parser=argparse.ArgumentParser()
parser.add_argument('--root',type=Path,default=Path(__file__).resolve().parents[1])
parser.add_argument('--history',action='store_true')
args=parser.parse_args();root=args.root.resolve();issues=[];counts={'files':0,'history_blobs':0,'embedded_parts':0}
known=json.loads(os.environ.get('AUDIT_FORBIDDEN_VALUES_JSON','[]'))
if os.environ.get('GEMINI_API_KEY'):known.append(os.environ['GEMINI_API_KEY'])
patterns={
 'google-api-key':re.compile(rb'AIza[0-9A-Za-z_-]{30,}'),
 'github-token':re.compile(rb'(?:gh[pousr]_[A-Za-z0-9]{20,}|github_pat_[A-Za-z0-9_]{30,})'),
 'private-key':re.compile(rb'-----BEGIN (?:RSA |EC |OPENSSH )?PRIVATE KEY-----'),
 'sites-write-token':re.compile(rb'art_v2_[A-Za-z0-9_]{20,}'),
 'deployment-identity':re.compile(rb'appgprj_[0-9a-f]{20,}'),
 'email-contact':re.compile(rb'[A-Za-z0-9_.+-]{1,64}@[A-Za-z0-9.-]{1,253}\.[A-Za-z]{2,24}'),
 'mobile-contact':re.compile(rb'0[789]0-\d{4}-\d{4}'),
}
allowed_emails={'255658513+kamotori11626@users.noreply.github.com'}
def inspect(label,raw,embedded=True):
 for name,pat in patterns.items():
  for match in pat.finditer(raw):
   if name=='email-contact' and match[0].decode(errors='ignore') in allowed_emails:continue
   issues.append((label,name));break
 for value in known:
  if isinstance(value,str) and len(value)>=6 and value.encode() in raw:issues.append((label,'known-private-value'));break
 if not embedded:return
 if raw.startswith(b'PK\x03\x04'):
  try:
   with zipfile.ZipFile(io.BytesIO(raw)) as z:
    for item in z.infolist():
     if item.file_size>30_000_000:issues.append((label,'oversized-archive'));continue
     if item.filename.endswith(('.xml','.rels')):inspect(label+'!'+item.filename,z.read(item),False);counts['embedded_parts']+=1
     if re.search(r'(?:comments|externalLinks|embeddings)/',item.filename):issues.append((label+'!'+item.filename,'review-embedded-content'))
  except zipfile.BadZipFile:issues.append((label,'invalid-archive'))
 if raw.lstrip().startswith(b'window.RECORD_TEMPLATE ='):
  try:
   template=json.loads(raw.decode().split('=',1)[1].strip().removesuffix(';'))
   for name,b64 in template.items():inspect(label+'!'+name,base64.b64decode(b64),False);counts['embedded_parts']+=1
  except (ValueError,KeyError):issues.append((label,'unreadable-template'))
 if label.endswith('.xml'):
  try:
   xml=ET.fromstring(raw)
   for node in xml.iter():
    if node.tag.split('}')[-1] in ('creator','lastModifiedBy','Manager','Company','author') and (node.text or '').strip():issues.append((label,'creator-metadata'))
  except ET.ParseError:issues.append((label,'invalid-xml'))
def path_check(path):
 parts=Path(path).parts
 if any(x in parts for x in ('data','node_modules','.tools','.wrangler')) or Path(path).name in ('.env','.env.keys') or path.endswith(('.sqlite3','.sqlite','.db','.pem','.key')):issues.append((path,'excluded-path'))

tracked=subprocess.check_output(['git','ls-files','--cached','--others','--exclude-standard','-z'],cwd=root).split(b'\0')
for item in tracked:
 if not item:continue
 name=os.fsdecode(item);p=root/name
 path_check(name)
 if p.is_symlink():issues.append((name,'symlink'));continue
 if not p.is_file():continue
 inspect(name,p.read_bytes());counts['files']+=1
if args.history:
 objects=subprocess.check_output(['git','rev-list','--objects','--all'],cwd=root,text=True).splitlines()
 for item in objects:
  oid,_,name=item.partition(' ')
  if subprocess.check_output(['git','cat-file','-t',oid],cwd=root,text=True).strip()!='blob':continue
  path_check(name);inspect('history:'+name,subprocess.check_output(['git','cat-file','blob',oid],cwd=root));counts['history_blobs']+=1
 for commit in subprocess.check_output(['git','rev-list','--all'],cwd=root,text=True).splitlines():
  metadata=subprocess.check_output(['git','show','-s','--format=%an%n%ae%n%cn%n%ce%n%B',commit],cwd=root)
  inspect('commit:'+commit[:10],metadata,False)
unique=sorted(set(issues));print(json.dumps({'result':'PASS' if not unique else 'REVIEW_REQUIRED',**counts,'findings':[{'path':p,'check':c} for p,c in unique]},ensure_ascii=False,indent=2));sys.exit(bool(unique))
