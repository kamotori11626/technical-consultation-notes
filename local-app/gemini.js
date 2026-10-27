/* Only generated, reviewed-for-disclosure prompts leave this browser. */
(()=>{
 const el=id=>document.getElementById(id), tell=t=>el('status').textContent=t;
 const configs=[
  {stage:'research',copy:'copyPrompt',generate:'generate',prompt:'prompt',dest:['evidence','answer','findings'],valid:()=>el('allowed').checked&&el('goal').value.trim()&&el('question').value.trim()},
  {stage:'memo',copy:'copyMemoPrompt',generate:'generateMemo',prompt:'memoPrompt',dest:['facts','inference','unknown','memo'],valid:()=>el('allowedMemo').checked&&el('decision').value==='checked'&&['evidence','answer','findings'].every(id=>el(id).value.trim())},
  {stage:'record',copy:'r_copy',generate:'r_generate',prompt:'r_prompt',dest:['r_subject','r_consultation','r_response','r_remarks'],valid:()=>el('r_answered').checked&&el('r_allowed').checked&&el('r_actualQuestion').value.trim()&&el('r_actualAnswer').value.trim()}
 ];
 let busy=false,revision=0;
 document.addEventListener('input',()=>revision++);
 document.addEventListener('change',()=>revision++);
 const notice=document.createElement('p');notice.className='note';notice.id='apiNotice';notice.textContent='Gemini接続設定を確認しています。';if(el('usageInfo'))el('usageInfo').append(notice);else document.querySelector('h1').after(notice);
 const sources=document.createElement('div');sources.id='searchAttribution';el('findings').parentElement.after(sources);
 async function getStatus(){const r=await fetch('/api/status');if(!r.ok)throw Error('APIサーバーを起動してください（python3 server.py）。');return r.json();}
 getStatus().then(s=>notice.textContent=s.configured?'Gemini APIキー設定済み／モデル：'+s.model+'。AIが作成した内容は本人が確認してください。':'Gemini APIキー未設定。prototypeフォルダで python3 setup_key.py を実行してください。キーはチャットへ貼らないでください。').catch(()=>notice.textContent='AI連携には prototype フォルダで python3 server.py を起動してください。');
 for(const c of configs){
  const button=document.createElement('button');button.id='ai_'+c.stage;button.textContent='AIに指示する';el(c.copy).before(button);c.button=button;
  button.onclick=async()=>{
   if(busy)return;
   // Regenerate from current whitelisted fields, not a stale editable prompt.
   el(c.generate).click();
   if(!c.valid()||!el(c.prompt).value){if(c.stage==='memo'&&el('decision').value!=='checked')tell('先に「2」で原資料との照合を終えてください。');return;}
   if(c.dest.some(id=>el(id).value.trim())&&!confirm('AIの結果で入力済みの欄を置き換えますか？（処理中に編集した場合は置き換えません）'))return;
   const version=revision, prompt=el(c.prompt).value;
   busy=true;configs.forEach(x=>x.button.disabled=true);button.textContent='AIが処理中…';tell('Geminiで処理しています。入力を変更した場合、結果の自動反映を中止します。');
   const controller=new AbortController(), timer=setTimeout(()=>controller.abort(),170000);
   try{
    const status=await getStatus();
    if(!status.configured)throw Error('APIキーが未設定です。prototypeで python3 setup_key.py を実行してください。');
    const response=await fetch('/api/generate',{method:'POST',headers:{'Content-Type':'application/json','X-App-Token':status.token},body:JSON.stringify({stage:c.stage,prompt}),signal:controller.signal});
    const data=await response.json();if(!response.ok)throw Error(data.error||'AI処理に失敗しました。');
    if(revision!==version||!c.valid()||el(c.prompt).value!==prompt)throw Error('処理中に入力・確認状態が変更されたため、自動反映しませんでした。現在の内容で再実行してください。');
    if(!data.fields||c.dest.some(id=>typeof data.fields[id]!=='string'))throw Error('AIの出力形式が合いません。入力は変更していません。');
    c.dest.forEach(id=>{el(id).value=data.fields[id];el(id).dispatchEvent(new Event('input',{bubbles:true}));});
    if(c.stage==='research'){
     sources.replaceChildren();
     if(data.searchHtml){const frame=document.createElement('iframe');frame.title='Google Searchの検索候補';frame.sandbox='allow-popups allow-popups-to-escape-sandbox';frame.referrerPolicy='no-referrer';frame.style='width:100%;height:180px;border:0';frame.srcdoc=data.searchHtml;sources.append(frame);}
    }
    tell(c.stage==='research'?'「2」へ反映しました。本人が原資料を照合し、現在の判断を選んでください。':c.stage==='memo'?'「3」へ反映しました。内容を確認してから相談者へ回答してください。':'記録簿の4項目へ反映しました。基本情報と文章を確認してから.docxで保存してください。');
   }catch(e){tell(e.name==='AbortError'?'時間切れです。入力は変更していません。':e.message||'接続できませんでした。入力は残っています。');}
   finally{clearTimeout(timer);busy=false;configs.forEach(x=>x.button.disabled=false);button.textContent='AIに指示する';}
  };
 }
})();
