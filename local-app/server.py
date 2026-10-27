"""Loopback-only Gemini bridge. Keys and consultation text are never logged."""
import records_store as store
import json, os, re, secrets, socket, urllib.request, urllib.error, sys
from pathlib import Path
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

ROOT = Path(__file__).resolve().parent
FIELDS = {'research': ['evidence','answer','findings'], 'memo': ['facts','inference','unknown','memo'], 'summary': ['summaryConsultation','summaryResponse','summaryPlan'], 'record': ['r_subject','r_consultation','r_response','r_remarks']}
PUBLIC = {'/': 'index.html', '/index.html':'index.html', '/record.js':'record.js', '/record-template.js':'record-template.js', '/gemini.js':'gemini.js', '/records.html':'records.html', '/records-ui.js':'records-ui.js', '/archive.js':'archive.js'}
TOKEN = secrets.token_urlsafe(32)

def api_key():
    if os.environ.get('GEMINI_API_KEY'): return os.environ['GEMINI_API_KEY']
    path = ROOT / '.env'
    if path.exists():
        for line in path.read_text().splitlines():
            if line.startswith('GEMINI_API_KEY='):
                value = line.split('=',1)[1].strip().strip('\"\'')
                return '' if value.startswith('encrypted:') else value
    return ''

def model_name():
    path = ROOT / 'config.json'
    config = json.loads(path.read_text()) if path.exists() else {}
    name = os.environ.get('GEMINI_MODEL') or config.get('model', 'gemini-3.6-flash')
    if not isinstance(name, str) or not re.fullmatch(r'gemini-[a-zA-Z0-9.-]+', name):
        raise ValueError('config.jsonのmodelを確認してください。')
    return name

def generate(stage, prompt):
    key = api_key()
    if not key or key == 'your_api_key_here': raise ValueError('APIキーが未設定です。prototypeで python3 setup_key.py を実行してください。キーはチャットに貼らないでください。')
    if stage=='research': prompt+='\n\n'+(ROOT/'支援対応の公開情報.md').read_text()
    names = FIELDS[stage]
    instruction = '\n出力形式だけを変更します。次のキーを持つJSONオブジェクトのみを返してください。各値は欄に記入する日本語の文字列です（配列不可）。見出しの順番とキーは対応します：'+json.dumps(names)+'。空欄にする場合もキーは残してください。'
    body = {'contents':[{'role':'user','parts':[{'text':prompt+instruction}]}], 'generationConfig':{'maxOutputTokens':16000}}
    if stage == 'research':
        body['tools'] = [{'google_search':{}}, {'url_context':{}}]
    else:
        body['generationConfig'].update({'responseMimeType':'application/json','responseSchema':{'type':'OBJECT','properties':{n:{'type':'STRING'} for n in names},'required':names}})
    req = urllib.request.Request('https://generativelanguage.googleapis.com/v1beta/models/'+model_name()+':generateContent', data=json.dumps(body).encode(), headers={'Content-Type':'application/json','x-goog-api-key':key})
    try:
        with urllib.request.urlopen(req,timeout=150) as response: result=json.load(response)
    except urllib.error.HTTPError as e:
        messages={400:'リクエストが受け付けられませんでした。APIキーとモデルの利用条件を確認してください。',401:'APIキーを確認してください。',403:'APIキーまたは利用権限を確認してください。',404:'選択したモデル '+model_name()+' は利用できません（提供終了・利用対象外など）。config.jsonのmodelを変更してください。',503:'Geminiが混雑しています。時間を置いて再実行してください。',429:'利用上限に達しました。時間を置くか、利用枠を確認してください。'}
        raise ValueError('Gemini HTTP '+str(e.code)+'：'+messages.get(e.code,'Geminiでエラーが発生しました。入力は変更していません。')) from None
    except (urllib.error.URLError, TimeoutError, socket.timeout): raise ValueError('Geminiに接続できないか、時間切れになりました。入力は変更していません。') from None
    candidate = (result.get('candidates') or [{}])[0]
    if candidate.get('finishReason') != 'STOP': raise ValueError('AIの出力が完了しませんでした。入力を短くするか、再実行してください。')
    raw=''.join(p.get('text','') for p in candidate.get('content',{}).get('parts',[]) if not p.get('thought'))
    raw=re.sub(r'^```(?:json)?\s*|\s*```$', '', raw.strip())
    try: data=json.loads(raw)
    except ValueError: raise ValueError('AIの出力形式が合わなかったため、入力欄は変更していません。再実行するか指示文をコピーして利用してください。') from None
    if not isinstance(data,dict) or set(data)!=set(names) or any(not isinstance(data[n],str) for n in names) or not any(data.values()): raise ValueError('AIの出力項目が不足しています。入力欄は変更していません。')
    grounding=candidate.get('groundingMetadata',{})
    if stage=='research':
        refs=[]
        for chunk in grounding.get('groundingChunks',[]):
            web=chunk.get('web',{})
            if web.get('uri','').startswith('https://'): refs.append(web.get('title','資料')+'\n'+web['uri'])
        data['evidence']+='\n\n【APIが返した検索参照先（本文閲覧の証明ではありません）】\n'+ ('\n'.join(refs) if refs else '検索参照先は返りませんでした。探索結果・出典は未確認です。')
    return {'fields':data,'searchHtml':grounding.get('searchEntryPoint',{}).get('renderedContent','')}

class Handler(BaseHTTPRequestHandler):
    def log_message(self,*args): pass
    def valid_host(self): return self.headers.get('Host') in (f'127.0.0.1:{self.server.server_port}', f'localhost:{self.server.server_port}')
    def reply(self,code,data,ctype='application/json; charset=utf-8'):
        raw = json.dumps(data,ensure_ascii=False).encode() if isinstance(data,dict) else data
        self.send_response(code);self.send_header('Content-Type',ctype);self.send_header('Content-Length',str(len(raw)));self.send_header('Cache-Control','no-store');self.send_header('X-Content-Type-Options','nosniff');self.end_headers();self.wfile.write(raw)
    def do_GET(self):
        if not self.valid_host(): return self.reply(403,{'error':'許可されていない接続です。'})
        path=self.path.split('?')[0]
        if path.startswith('/api/records'):
            if self.headers.get('X-App-Token')!=TOKEN:return self.reply(403,{'error':'許可されていない接続です。'})
            try:return self.reply(200,store.get(path.rsplit('/',1)[1]) if path!='/api/records' else store.listing())
            except ValueError as e:return self.reply(404,{'error':str(e)})
        if path=='/api/status': return self.reply(200,{'configured':bool(api_key()),'token':TOKEN,'model':model_name()})
        if path not in PUBLIC: return self.reply(404,{'error':'Not found'})
        self.reply(200,(ROOT/PUBLIC[path]).read_bytes(),'text/html; charset=utf-8' if path.endswith('.html') or path=='/' else 'text/javascript; charset=utf-8')
    def do_POST(self):
        origin=self.headers.get('Origin')
        if not self.valid_host() or origin not in (f'http://127.0.0.1:{self.server.server_port}',f'http://localhost:{self.server.server_port}') or self.headers.get('X-App-Token')!=TOKEN: return self.reply(403,{'error':'許可されていない接続です。'})
        if self.path not in ('/api/generate','/api/records/save','/api/records/import','/api/records/pdf','/api/records/monthly'): return self.reply(404,{'error':'Not found'})
        try:
            length=int(self.headers.get('Content-Length','0'))
            if not 0<length<=(200000 if self.path=='/api/generate' else 12000000): return self.reply(413,{'error':'入力が長すぎます。'})
            data=json.loads(self.rfile.read(length))
            if self.path=='/api/records/save': return self.reply(200,store.save(data))
            if self.path=='/api/records/import':return self.reply(200,store.parse_docx(store.decode_docx(data['docx'])))
            if self.path=='/api/records/pdf':return self.reply(200,store.pdf(store.decode_docx(data['docx'])),'application/pdf')
            if self.path=='/api/records/monthly':return self.reply(200,store.monthly(data['month']),'application/vnd.openxmlformats-officedocument.spreadsheetml.sheet')
            if set(data)!={'stage','prompt'} or data['stage'] not in FIELDS or not isinstance(data['prompt'],str) or not data['prompt'].strip(): raise ValueError('入力形式を確認してください。')
            self.reply(200,generate(data['stage'],data['prompt']))
        except (ValueError, TypeError, KeyError):
            import sys
            e=sys.exc_info()[1]
            self.reply(400,{'error':str(e) if isinstance(e,ValueError) and not isinstance(e,json.JSONDecodeError) else '入力形式を確認してください。'})
        except Exception: self.reply(502,{'error':'処理できませんでした。入力は残っています。再実行してください。'})

if __name__=='__main__':
    env_file = ROOT / '.env'
    if not os.environ.get('GEMINI_API_KEY') and env_file.exists() and 'encrypted:' in env_file.read_text():
        dotenvx = ROOT / '.tools/node_modules/.bin/dotenvx'
        if os.environ.get('CONSULTATION_DOTENVX_STARTED') or not dotenvx.exists():
            raise SystemExit('dotenvxによる復号に失敗しました。導入状態と.env.keysを確認してください。')
        child_env = dict(os.environ, CONSULTATION_DOTENVX_STARTED='1')
        os.execvpe(str(dotenvx), [str(dotenvx), 'run', '--strict', '--no-native', '--no-armor', '-f', str(env_file), '-fk', str(ROOT / '.env.keys'), '--', sys.executable, str(ROOT / 'server.py')], child_env)

    server=ThreadingHTTPServer(('127.0.0.1',int(os.environ.get('PORT','8766'))),Handler)
    print(f'技術相談の調査メモ: http://127.0.0.1:{server.server_port}/',flush=True)
    server.serve_forever()
