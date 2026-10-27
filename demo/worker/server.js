const MODEL='gemini-2.5-flash', MONTHLY_LIMIT=5;
const FIELDS={research:['evidence','answer','findings'],memo:['facts','inference','unknown','memo'],record:['r_subject','r_consultation','r_response','r_remarks']};
const enc=new TextEncoder();
async function readLimited(request,max){const reader=request.body?.getReader();if(!reader)return '';const chunks=[];let size=0;while(true){const {done,value}=await reader.read();if(done)break;size+=value.length;if(size>max){await reader.cancel();throw new Error('body-limit');}chunks.push(value);}const bytes=new Uint8Array(size);let offset=0;for(const c of chunks){bytes.set(c,offset);offset+=c.length;}return new TextDecoder().decode(bytes);}
function reply(data,status=200,headers={}){return new Response(typeof data==='string'?data:JSON.stringify(data),{status,headers:{'Content-Type':'application/json; charset=utf-8','Cache-Control':'no-store','X-Content-Type-Options':'nosniff','Referrer-Policy':'same-origin','X-Frame-Options':'DENY','X-Robots-Tag':'noindex, nofollow',...headers}});}
function redirect(path,cookie){return reply('',303,{Location:path,...(cookie?{'Set-Cookie':cookie}:{})});}
async function mac(text,key){const k=await crypto.subtle.importKey('raw',enc.encode(key),{name:'HMAC',hash:'SHA-256'},false,['sign']);return [...new Uint8Array(await crypto.subtle.sign('HMAC',k,enc.encode(text)))].map(b=>b.toString(16).padStart(2,'0')).join('');}
function same(a,b){if(typeof a!=='string'||typeof b!=='string')return false;let d=a.length^b.length;for(let i=0;i<Math.max(a.length,b.length);i++)d|=(a.charCodeAt(i)||0)^(b.charCodeAt(i)||0);return d===0;}
async function session(request,env){const token=request.headers.get('Cookie')?.match(/(?:^|;\s*)__Host-demo=([^;]+)/)?.[1];if(!token||!env.SESSION_SECRET)return null;const [expiry,id,sig]=token.split('.');if(!/^\d+$/.test(expiry)||Number(expiry)<Date.now()||!/^[a-f0-9]{32}$/.test(id||''))return null;return same(sig,await mac(expiry+'.'+id,env.SESSION_SECRET))?{id,token}:null;}
async function reserve(db,key,limit){const r=await db.prepare('INSERT INTO ai_budget (month, attempts) VALUES (?, 1) ON CONFLICT(month) DO UPDATE SET attempts=attempts+1 WHERE attempts < ? RETURNING attempts').bind(key,limit).first();return !!r;}
const month=()=>new Date(Date.now()+9*3600*1000).toISOString().slice(0,7);
async function generate(request,env,s){if(!env.GEMINI_API_KEY||!env.DB)return reply({error:'AI接続を準備中です。見本と文書出力をお試しください。'},503);if(!same(request.headers.get('X-CSRF-Token'),await mac(s.token,env.SESSION_SECRET)))return reply({error:'画面を開き直してください。'},403);
let raw;try{raw=await readLimited(request,18000);}catch{return reply({error:'入力が長すぎます。指示文全体を18,000バイト以内にしてください。'},413);}
let data;try{data=JSON.parse(raw);}catch{return reply({error:'入力形式を確認してください。'},400);}
if(!FIELDS[data.stage]||typeof data.prompt!=='string'||!data.prompt.trim()||Object.keys(data).sort().join(',')!=='prompt,stage')return reply({error:'入力形式を確認してください。'},400);
// Reserve before making any paid request. Failure/timeout still consumes a slot.
if(!await reserve(env.DB,month(),MONTHLY_LIMIT))return reply({error:'今月の実AI利用上限に達しました。見本の確認とDOCX出力は引き続き利用できます。'},429);
const names=FIELDS[data.stage],instruction='\n次のキーだけを持つJSONオブジェクトを返す。値は日本語の文字列とし、配列にしない：'+JSON.stringify(names)+'。架空の相談デモである。原資料で確認できない事実やURLを作らず、未確認と示す。出力は簡潔にする。';
const body={contents:[{role:'user',parts:[{text:data.prompt+instruction}]}],generationConfig:{maxOutputTokens:2048,thinkingConfig:{thinkingBudget:0}}};
if(data.stage==='research')body.tools=[{google_search:{}}];else Object.assign(body.generationConfig,{responseMimeType:'application/json',responseSchema:{type:'OBJECT',properties:Object.fromEntries(names.map(n=>[n,{type:'STRING'}])),required:names}});
try{const count=await fetch('https://generativelanguage.googleapis.com/v1beta/models/'+MODEL+':countTokens',{method:'POST',headers:{'Content-Type':'application/json','x-goog-api-key':env.GEMINI_API_KEY},body:JSON.stringify({contents:body.contents}),signal:AbortSignal.timeout(15000)});
if(!count.ok)return reply({error:'入力の使用量を確認できないため、生成を止めました。'},502);
const usage=await count.json();if(!Number.isFinite(usage.totalTokens)||usage.totalTokens>32000)return reply({error:'予算管理のため入力を短くしてください。'},413);
const response=await fetch('https://generativelanguage.googleapis.com/v1beta/models/'+MODEL+':generateContent',{method:'POST',headers:{'Content-Type':'application/json','x-goog-api-key':env.GEMINI_API_KEY},body:JSON.stringify(body),signal:AbortSignal.timeout(90000)});
if(!response.ok)return reply({error:'AIサービスが応答できませんでした（HTTP '+response.status+'）。入力は変更していません。'},502);
const result=await response.json(),candidate=result.candidates?.[0];if(candidate?.finishReason!=='STOP')return reply({error:'AIの出力が完了しませんでした。入力を短くしてお試しください。'},502);
const text=candidate.content.parts.filter(p=>!p.thought).map(p=>p.text||'').join('').trim().replace(/^```(?:json)?\s*|\s*```$/g,'');let fields;try{fields=JSON.parse(text);}catch{return reply({error:'AIの出力形式が合わないため反映しませんでした。'},502);}
if(!fields||Array.isArray(fields)||Object.keys(fields).sort().join(',')!==[...names].sort().join(',')||names.some(n=>typeof fields[n]!=='string')||!names.some(n=>fields[n].trim()))return reply({error:'AIの出力項目を確認できませんでした。'},502);
if(data.stage==='research'){const refs=(candidate.groundingMetadata?.groundingChunks||[]).flatMap(c=>c.web?.uri?.startsWith('https://')?[(c.web.title||'検索参照先')+'\n'+c.web.uri]:[]);fields.evidence+='\n\n【APIが返した検索参照先・本文を確認した証明ではありません】\n'+(refs.join('\n')||'検索参照先は返りませんでした。出典は未確認です。');}
return reply({fields,model:MODEL,source:'live'});
}catch{return reply({error:'AIへの接続が時間切れ、または失敗しました。入力は変更していません。'},502);}}
export function createHandler(assets){return {async fetch(request,env){try{
const url=new URL(request.url),path=url.pathname;if(!['GET','HEAD','POST'].includes(request.method))return reply({error:'Method not allowed'},405);
if(request.method==='POST'&&request.headers.get('Origin')!==url.origin)return reply({error:'許可されていない接続です。'},403);
if(Number(request.headers.get('Content-Length')||0)>20000)return reply({error:'入力が長すぎます。'},413);
if(path==='/login'&&request.method==='POST'){
 if(!env.DEMO_USER||!env.DEMO_PASSWORD||!env.SESSION_SECRET||!env.DB)return reply({error:'ログイン設定を準備中です。'},503);
 let raw;try{raw=await readLimited(request,1000);}catch{return reply({error:'入力が長すぎます。'},413);}
 const ip=request.headers.get('CF-Connecting-IP')||'unknown',bucket=Math.floor(Date.now()/900000),key='login:'+bucket+':'+(await mac(ip,env.SESSION_SECRET)).slice(0,20);
 if(!await reserve(env.DB,key,15))return reply({error:'ログイン試行が多すぎます。15分ほど置いてお試しください。'},429);
 const form=new URLSearchParams(raw);if(!same(form.get('username'),env.DEMO_USER)||!same(form.get('password'),env.DEMO_PASSWORD))return redirect('/?error=1#demo');
 const expiry=Date.now()+7200000,id=crypto.randomUUID().replaceAll('-',''),text=expiry+'.'+id,token=text+'.'+await mac(text,env.SESSION_SECRET);
 return redirect('/demo','__Host-demo='+token+'; Path=/; HttpOnly; Secure; SameSite=Strict; Max-Age=7200');
}
if(path==='/logout'&&request.method==='POST')return redirect('/','__Host-demo=; Path=/; HttpOnly; Secure; SameSite=Strict; Max-Age=0');
if((path==='/'||path==='/index.html')&&request.method!=='POST')return reply(assets['index.html'],200,{'Content-Type':'text/html; charset=utf-8'});
const s=await session(request,env);if(!s)return path.startsWith('/api/')?reply({error:'ログインが必要です。'},401):redirect('/#demo');
if(path==='/api/status'&&request.method==='GET'){const r=env.DB?await env.DB.prepare('SELECT attempts FROM ai_budget WHERE month = ?').bind(month()).first():null;return reply({model:MODEL,remaining:env.GEMINI_API_KEY&&env.DB?Math.max(0,MONTHLY_LIMIT-(r?.attempts||0)):0,csrf:await mac(s.token,env.SESSION_SECRET)});}
if(path==='/api/generate'&&request.method==='POST')return generate(request,env,s);
if(request.method==='POST')return reply({error:'Not found'},404);
const routes={'/demo':'demo.html','/record.js':'record.js','/record-template.js':'record-template.js','/demo.js':'demo.js','/records.html':'records.html'};const name=routes[path];if(!name)return reply({error:'Not found'},404);
return reply(assets[name],200,{'Content-Type':name.endsWith('.js')?'text/javascript; charset=utf-8':'text/html; charset=utf-8'});
}catch{return reply({error:'処理を完了できませんでした。時間を置いてお試しください。'},503);}}};}
