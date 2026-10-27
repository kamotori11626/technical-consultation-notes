"""Local record storage, bounded DOCX parsing, PDF preview and monthly export."""
import base64, datetime as dt, hashlib, io, json, os, re, sqlite3, subprocess, tempfile, uuid, zipfile
from pathlib import Path
from xml.etree import ElementTree as ET
ROOT=Path(__file__).resolve().parent
DB=ROOT/'data'/'records.sqlite3'
RUNTIME=Path.home()/'.cache/codex-runtimes/codex-primary-runtime/dependencies'
W='{http://schemas.openxmlformats.org/wordprocessingml/2006/main}'

def connect():
    DB.parent.mkdir(mode=0o700,parents=True,exist_ok=True)
    c=sqlite3.connect(DB,timeout=20);c.row_factory=sqlite3.Row
    c.execute('CREATE TABLE IF NOT EXISTS records(id TEXT PRIMARY KEY, revision INTEGER, data TEXT, docx BLOB, hash TEXT, updated TEXT)')
    c.execute('CREATE TABLE IF NOT EXISTS history(id TEXT, revision INTEGER, data TEXT, docx BLOB, updated TEXT, PRIMARY KEY(id,revision))')
    os.chmod(DB,0o600)
    return c

def decode_docx(value):
    try: raw=base64.b64decode(value,validate=True)
    except Exception: raise ValueError('DOCXデータが不正です。')
    if len(raw)>8_000_000: raise ValueError('DOCXは8MB以下にしてください。')
    try:
        with zipfile.ZipFile(io.BytesIO(raw)) as z:
            if len(z.infolist())>500 or sum(i.file_size for i in z.infolist())>30_000_000: raise ValueError('展開サイズが大きすぎます。')
            if 'word/vbaProject.bin' in z.namelist(): raise ValueError('マクロ付き文書は取り込めません。')
            xml=z.read('word/document.xml')
            if b'<!DOCTYPE' in xml or b'<!ENTITY' in xml: raise ValueError('このXML形式は取り込めません。')
            ET.fromstring(xml)
    except (zipfile.BadZipFile,KeyError,ET.ParseError): raise ValueError('所定のDOCX文書を選択してください。')
    return raw

def text(el):
    return ''.join(e.text or '' if e.tag==W+'t' else '\n' if e.tag in (W+'br',W+'cr') else '\t' if e.tag==W+'tab' else '' for e in el.iter())

def parse_docx(raw):
    with zipfile.ZipFile(io.BytesIO(raw)) as z: root=ET.fromstring(z.read('word/document.xml'))
    paragraphs=[text(p).strip() for p in root.iter(W+'p')]
    d={};warnings=[]
    for p in paragraphs:
        if '年度' in p and '技術相談' in p:
            m=re.search(r'(令和[０-９\d元]+)年度',p)
            if m:d['fiscalYear']=m[1]
        if p.startswith('対応者所属'): d['staffOrg']=re.sub(r'^対応者所属[：:]\s*','',p)
        if p.startswith('職・氏名'): d['staffName']=re.sub(r'^職・氏名[：:]\s*','',p)
        if not d.get('displayDate') and parse_date(p):d['displayDate']=p
    labelmap={'件名':'subject','所在地':'address','対応方法':'method','相談内容':'consultation','対応内容':'response','備考':'remarks','加工機器整備状況':'equipment','製造許可取得状況':'license','販売先の有無':'outlets','販売予定時期':'salesPlan','販売実績':'salesResults','販売先':'salesDestination','商品の特徴':'features','製造者／住所':'manufacturer','販売者／住所':'seller','活用した政策支援':'support','課題':'issues','フォロー':'follow'}
    for table in root.iter(W+'tbl'):
        rows=table.findall(W+'tr')
        if rows and re.sub(r'\s','',text(rows[0])).startswith('記録簿No') and len(rows)>1:d['recordNo']=text(rows[1]).strip()
        if rows and len(rows)>1 and re.sub(r'\s','',text(rows[0])).startswith('日にち対応内容'):
            cells=rows[1].findall(W+'tc')
            if len(cells)>1:d['historyDate']=text(cells[0]);d['historyResponse']=text(cells[1])
        for row in rows:
            cells=row.findall(W+'tc'); vals=['\n'.join(text(p) for p in c.findall(W+'p')).strip() for c in cells]
            if len(vals)<2:continue
            label=re.sub(r'\s','',vals[0])
            if label=='相手方名':
                for v in vals[1:]:
                    if '所属' in v:d['partyOrg']=re.sub(r'^.*?（所属）\s*','',v)
                    if '職・氏名' in v:d['partyName']=re.sub(r'^.*?（職・氏名）\s*','',v)
            elif label=='TEL':
                d['tel']=vals[1]
                if len(vals)>3:d['fax']=vals[3]
            elif label=='商品名':
                d['product']=vals[1]
                if len(vals)>3:d['price']=vals[3]
            elif label in labelmap:
                key=labelmap[label]
                if key=='remarks' and key in d:key='surroundRemarks'
                d[key]=vals[1]
                if label in ('対応方法','相談内容'):
                    selected=[text(r) for r in cells[1].iter(W+'r') if r.find(W+'rPr/'+W+'bdr') is not None]
                    known=['電話','来所','現場','メール','FAX','WEB','その他'] if label=='対応方法' else ['新商品開発','商品改良','加工実習','依頼分析','その他']
                    selected+=re.findall(r'【([^】]+)】',vals[1])
                    other=re.search(r'その他[】]?\s*[（(](.*?)[）)]',vals[1].split('\n')[0])
                    if other:d['methodOther' if label=='対応方法' else 'categoryOther']=other[1]
                    d['methods' if label=='対応方法' else 'categories']=[v for v in known if v in selected]
                    if label=='相談内容' and all(v in vals[1].split('\n')[0] for v in known[:2]):d[key]='\n'.join(vals[1].split('\n')[1:])
    if not d.get('subject') or 'consultation' not in d or 'response' not in d:raise ValueError('所定の記録簿様式を認識できませんでした。自動保存せず中止しました。')
    if d.get('staffName'):d['staffName']=d['staffName'].replace('\t','　')
    warnings.append('抽出結果を原本と照合してください。月次分類には右上の日付を使います。読み取れない日付は未設定になります。')
    return {'data':d,'warnings':warnings}

def parse_date(value):
    import unicodedata
    value=unicodedata.normalize('NFKC',value).strip().replace(' ','')
    m=re.fullmatch(r'令和(元|\d+)年(\d+)月(\d+)日',value)
    if m:parts=[2018+(1 if m[1]=='元' else int(m[1])),int(m[2]),int(m[3])]
    else:
        m=re.fullmatch(r'(\d{4})[-/年](\d{1,2})[-/月](\d{1,2})日?',value)
        if not m:return ''
        parts=list(map(int,m.groups()))
    try:return dt.date(*parts).isoformat()
    except ValueError:return ''

def save(payload):
    d=payload.get('data');rid=payload.get('id') or str(uuid.uuid4());rev=payload.get('revision',0)
    if not isinstance(d,dict) or len(json.dumps(d))>200000:raise ValueError('記録データを確認してください。')
    d=dict(d)
    d['consultationDate']=parse_date(d.get('displayDate',''))
    date=d.get('consultationDate','')
    if date:
        try:dt.date.fromisoformat(date)
        except ValueError:raise ValueError('相談対応日を確認してください。')
    for key in ('summaryConsultation','summaryResponse','summaryPlan'):
        if len(d.get(key,''))>100:raise ValueError('月次要約は100文字以内にしてください。')
    raw=decode_docx(payload['docx']) if payload.get('docx') else None
    encoded=json.dumps(d,ensure_ascii=False);now=dt.datetime.now().isoformat(timespec='seconds')
    with connect() as c:
        c.execute('BEGIN IMMEDIATE')
        old=c.execute('SELECT * FROM records WHERE id=?',(rid,)).fetchone()
        if old and old['revision']!=rev:raise ValueError('別の画面で更新されています。一覧から最新の記録を開き直してください。')
        if not old and rev:raise ValueError('記録が見つかりません。')
        digest=hashlib.sha256(raw).hexdigest() if raw else None
        if not old and digest:
            same=c.execute('SELECT id FROM records WHERE hash=?',(digest,)).fetchone()
            if same:raise ValueError('同じDOCXは保存済みです。一覧から編集してください。')
        if old:c.execute('INSERT INTO history VALUES(?,?,?,?,?)',(rid,rev,old['data'],old['docx'],old['updated']))
        # Editing text invalidates the stored document until it is exported again.
        newrev=rev+1
        c.execute('INSERT OR REPLACE INTO records VALUES(?,?,?,?,?,?)',(rid,newrev,encoded,raw,digest,now))
    return {'id':rid,'revision':newrev,'updated':now}

def listing():
    with connect() as c:return {'records':[{'id':r['id'],'revision':r['revision'],'updated':r['updated'],'data':json.loads(r['data'])} for r in c.execute('SELECT * FROM records ORDER BY updated DESC')]}

def get(rid):
    with connect() as c:r=c.execute('SELECT * FROM records WHERE id=?',(rid,)).fetchone()
    if not r:raise ValueError('記録が見つかりません。')
    return {'id':r['id'],'revision':r['revision'],'data':json.loads(r['data'])}

def pdf(raw):
    with tempfile.TemporaryDirectory(prefix='consultation-pdf-') as folder:
        p=Path(folder);(p/'input.docx').write_bytes(raw)
        # Use a private profile; never run macros or access external document links.
        profile=p/'profile/user';profile.mkdir(parents=True)
        (profile/'registrymodifications.xcu').write_text('''<?xml version="1.0"?><oor:items xmlns:oor="http://openoffice.org/2001/registry"><item oor:path="/org.openoffice.Office.Common/Security/Scripting"><prop oor:name="MacroSecurityLevel" oor:op="fuse"><value>3</value></prop></item><item oor:path="/org.openoffice.Office.Writer/Content/Update"><prop oor:name="Link" oor:op="fuse"><value>2</value></prop></item></oor:items>''')
        fonts=p/'fonts.conf';fonts.write_text('<?xml version="1.0"?><!DOCTYPE fontconfig SYSTEM "urn:fontconfig:fonts.dtd"><fontconfig><dir>/System/Library/Fonts</dir><dir>/System/Library/Fonts/Supplemental</dir><dir>/Applications/Microsoft Word.app/Contents/Resources/DFonts</dir><cachedir>'+str(p/'fonts-cache')+'</cachedir></fontconfig>')
        cmd=[str(RUNTIME/'bin/override/soffice'),'-env:UserInstallation='+ (p/'profile').as_uri(),'--headless','--convert-to','pdf','--outdir',folder,str(p/'input.docx')]
        result=subprocess.run(cmd,stdout=subprocess.PIPE,stderr=subprocess.PIPE,timeout=60,env={**os.environ,'FONTCONFIG_FILE':str(fonts)})
        if result.returncode or not (p/'input.pdf').exists():raise ValueError('PDF変換に失敗しました。DOCXの内容・変換環境を確認してください。')
        return (p/'input.pdf').read_bytes()

def monthly(month):
    if not re.fullmatch(r'\d{4}-\d{2}',month):raise ValueError('対象月を選んでください。')
    rows=[]
    for r in listing()['records']:
        d=r['data']
        if not d.get('consultationDate','').startswith(month):continue
        if any(not d.get(k) for k in ('summaryConsultation','summaryResponse')):raise ValueError('対象月の記録すべてに月次要約を入力・保存してください。')
        if 'summaryPlan' not in d:raise ValueError('対象月の記録で今後の対応予定を確認し、月次要約を保存してください。予定がない場合は空欄で保存できます。')
        rows.append(d)
    rows.sort(key=lambda d:(d['consultationDate'],int(d.get('recordNo','')) if d.get('recordNo','').isdigit() else 999999))
    with tempfile.TemporaryDirectory(prefix='consultation-xlsx-') as folder:
        p=Path(folder);(p/'input.json').write_text(json.dumps({'month':month,'records':rows},ensure_ascii=False))
        result=subprocess.run([str(RUNTIME/'node/bin/node'),str(ROOT/'monthly.mjs'),str(p/'input.json'),str(p/'out.xlsx')],capture_output=True,timeout=90)
        if result.returncode:raise ValueError('Excel出力に失敗しました。出力環境を確認してください。')
        from monthly_layout import restore
        return restore((p/'out.xlsx').read_bytes(),month,len(rows))
