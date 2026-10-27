/* Local-only archive requests. Personal form fields never go to Gemini. */
window.localRecords={
 async request(path,data){const s=await(await fetch('/api/status')).json();const r=await fetch(path,{method:data?'POST':'GET',headers:{'X-App-Token':s.token,'Content-Type':'application/json'},body:data?JSON.stringify(data):undefined});if(!r.ok){const e=await r.json();throw Error(e.error||'処理に失敗しました。');}return r;},
 async base64(blob){return new Promise((resolve,reject)=>{const reader=new FileReader();reader.onload=()=>resolve(reader.result.split(',')[1]);reader.onerror=reject;reader.readAsDataURL(blob);});},
 download(blob,name){const u=URL.createObjectURL(blob),a=document.createElement('a');a.href=u;a.download=name;a.click();setTimeout(()=>URL.revokeObjectURL(u),30000);}
};
(async()=>{
 if(!window.recordForm)return;
 const $=id=>document.getElementById(id),tell=t=>$('status').textContent=t;
 const link=document.createElement('a');link.href='/records.html';link.target='_blank';link.textContent='保存済み記録・月次集計を開く';if($('appTools'))$('appTools').prepend(link);else document.querySelector('h1').after(link);
 let identity={id:null,revision:0},extra={};
 const saved=document.createElement('p');$('r_export').after(saved);
 for(const key of ['partyName','tel','fax','address']){
  const input=$('r_'+key),original=input.parentElement,field=document.createElement('div'),heading=document.createElement('div'),title=document.createElement('label'),label=document.createElement('label'),check=document.createElement('input');
  field.className='record-input-field';heading.className='record-field-heading';title.htmlFor=input.id;title.textContent=original.firstChild.textContent;label.className='record-unknown';check.type='checkbox';check.id=input.id+'_unknown';check.setAttribute('aria-label',title.textContent+'が不明');label.append(check,document.createTextNode('不明'));heading.append(title,label);original.replaceWith(field);field.append(heading,input);let previous='';
  check.onchange=()=>{if(check.checked){previous=input.value;input.value='不明';}else if(input.value==='不明')input.value=previous;input.dispatchEvent(new Event('input',{bubbles:true}));};
  input.addEventListener('input',()=>check.checked=input.value==='不明');
 }
 window.saveRecordExport=async(data,blob)=>{const d={...extra,...data};for(const [src,sum] of [['consultation','summaryConsultation'],['response','summaryResponse']])if(extra[src]!==data[src])delete d[sum];if(extra.response!==data.response||extra.remarks!==data.remarks)delete d.summaryPlan;const result=await(await localRecords.request('/api/records/save',{...identity,data:d,docx:await localRecords.base64(blob)})).json();identity=result;extra=d;saved.textContent='保存済み（版 '+result.revision+'）。内容を変更して再出力するとこの記録を更新します。';history.replaceState(null,'','/?record='+encodeURIComponent(result.id));};
 const preview=document.createElement('button');preview.textContent='PDFプレビューを出力';$('r_export').before(preview);
 preview.onclick=async()=>{preview.disabled=true;tell('PDFを作成しています。');try{const blob=buildRecordDocx(window.recordForm.collect());const r=await localRecords.request('/api/records/pdf',{docx:await localRecords.base64(blob)});localRecords.download(await r.blob(),'記録簿_プレビュー.pdf');tell('PDFプレビューを出力しました。データベースにはまだ保存していません。');}catch(e){tell(e.message);}finally{preview.disabled=false;}};
 const id=new URLSearchParams(location.search).get('record');if(id){try{const record=await(await localRecords.request('/api/records/'+encodeURIComponent(id))).json();identity={id:record.id,revision:record.revision};extra=record.data;window.recordForm.restore(record.data);for(const key of ['partyName','tel','fax','address'])$('r_'+key).dispatchEvent(new Event('input',{bubbles:true}));saved.textContent='保存済み記録を編集中（版 '+record.revision+'）。再出力すると更新します。';tell('保存済み記録を読み込みました。回答済み・内容確認を再確認して出力してください。');}catch(e){tell(e.message);$('r_export').disabled=true;}}
})();
