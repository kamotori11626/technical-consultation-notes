const fs=require('fs'),vm=require('vm'),assert=require('assert');
const root=__dirname+'/../', elements={},listeners={};
class Element{
 constructor(id=''){this.id=id;this.value='';this.checked=false;this.disabled=false;this.handlers={};this.textContent='';this.parentElement={after(){}};}
 set id(v){this._id=v;if(v)elements[v]=this;}
 get id(){return this._id;}
 set innerHTML(s){for(const m of s.matchAll(/id="([^"]+)"/g))elements[m[1]]=new Element(m[1]);}
 addEventListener(k,f){(this.handlers[k]??=[]).push(f);}
 dispatchEvent(e){for(const f of this.handlers[e.type]||[])f(e);for(const f of listeners[e.type]||[])f(e);}
 before(){} after(){} replaceChildren(){} append(){}
 querySelectorAll(){return Object.values(elements).filter(e=>e.id.startsWith('r_'));}
 click(){if(!this.disabled)return this.onclick?.();}
}
const html=fs.readFileSync(root+'index.html','utf8');for(const m of html.matchAll(/id="([^"]+)"/g))elements[m[1]]=new Element(m[1]);
const $=id=>elements[id];let requests=[],delay=null,invalid=false;
const mapping={research:['evidence','answer','findings'],memo:['facts','inference','unknown','memo'],record:['r_subject','r_consultation','r_response','r_remarks']};
const ctx=vm.createContext({document:{getElementById:$,createElement:()=>new Element(),querySelector:()=>new Element(),addEventListener:(k,f)=>(listeners[k]??=[]).push(f)},window:{},confirm:()=>true,Event:class{constructor(type){this.type=type;}},setTimeout,clearTimeout,AbortController,console,navigator:{clipboard:{writeText:async()=>{}}},fetch:async(url,opt)=>{if(url==='/api/status')return{ok:true,json:async()=>({configured:true,token:'test'})};const body=JSON.parse(opt.body);requests.push(body);if(delay)await delay;return{ok:true,json:async()=>({fields:invalid?{}:Object.fromEntries(mapping[body.stage].map(k=>[k,'生成 '+k]))})};}});
vm.runInContext(html.match(/<script>([\s\S]*?)<\/script>/)[1],ctx);vm.runInContext(fs.readFileSync(root+'record.js','utf8'),ctx);vm.runInContext(fs.readFileSync(root+'gemini.js','utf8'),ctx);
(async()=>{
 for(let i=0;i<6;i++)$('r_addStaff').click();assert.equal($('r_addStaff').disabled,true);assert.equal($('r_staffRow4').hidden,false);
 $('r_staffRole1').value='';$('r_staffRole1').onchange();assert.equal($('r_customLabel1').hidden,false);
 $('r_staffPerson2').value='第三担当';$('r_removeStaff1').click();assert.equal($('r_staffPerson1').value,'第三担当');assert.equal($('r_addStaff').disabled,false);assert.equal($('r_staffRow4').hidden,true);
 assert(html!==null);
 $('goal').value='目的';$('question').value='問い';$('conditions').value='条件';
 $('r_sameQuestion').checked=true;$('r_sameQuestion').onchange();
 assert.equal($('r_actualQuestion').value,'【実現したいこと】\n目的\n\n【調べたい問い】\n問い\n\n【分かっている条件】\n条件');
 assert.equal($('r_sameQuestion').checked,true);
 $('r_allowed').checked=true;$('r_reviewed').checked=true;
 $('conditions').dispatchEvent(new ctx.Event('input'));
 assert.equal($('r_sameQuestion').checked,false);assert.equal($('r_allowed').checked,false);assert.equal($('r_reviewed').checked,false);
 const copied=$('r_actualQuestion').value;ctx.confirm=()=>false;$('r_actualQuestion').value='追加相談';$('r_sameQuestion').checked=true;$('r_sameQuestion').onchange();assert.equal($('r_actualQuestion').value,'追加相談');assert.equal($('r_sameQuestion').checked,false);ctx.confirm=()=>true;
 $('r_sameQuestion').checked=true;$('r_sameQuestion').onchange();assert.equal($('r_actualQuestion').value,copied);
 $('r_actualQuestion').dispatchEvent(new ctx.Event('input'));assert.equal($('r_sameQuestion').checked,false);
 await $('ai_memo').click();assert.equal(requests.length,0);
 $('goal').value='目的';$('question').value='問い';$('allowed').checked=true;
 await $('ai_research').click();assert.equal($('evidence').value,'生成 evidence');assert.equal($('decision').value,'pending');
 $('decision').value='checked';$('decision').onchange();$('allowedMemo').checked=true;
 await $('ai_memo').click();assert.equal($('memo').value,'生成 memo');
 $('r_actualQuestion').value='実際の相談';$('r_actualAnswer').value='実際の回答';$('r_answered').checked=true;$('r_allowed').checked=true;$('r_partyName').value='PERSONAL_NAME_SENTINEL';$('r_tel').value='PRIVATE_PHONE_SENTINEL';$('r_reviewed').checked=true;
 await $('ai_record').click();assert.equal($('r_subject').value,'生成 r_subject');assert.equal($('r_reviewed').checked,false);assert(!JSON.stringify(requests).includes('SENTINEL'));
 assert($('r_prompt').value.includes('過去形で記載する'));assert($('r_prompt').value.includes('〜することになった'));assert($('r_prompt').value.includes('未実施の作業を実施済みと解釈しない'));
 let release;delay=new Promise(r=>release=r);const pending=$('ai_record').click();await new Promise(setImmediate);$('r_subject').value='手動編集';$('r_subject').dispatchEvent(new ctx.Event('input'));release();await pending;assert.equal($('r_subject').value,'手動編集');assert($('status').textContent.includes('自動反映しません'));
 delay=null;invalid=true;await $('ai_record').click();assert.equal($('r_subject').value,'手動編集');assert($('status').textContent.includes('出力形式'));
 console.log('PASS: three-stage autofill, review gates, privacy whitelist, concurrent edit protection, invalid output preservation');
})().catch(e=>{console.error(e);process.exitCode=1});
