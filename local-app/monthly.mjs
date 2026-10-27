import fs from 'node:fs/promises';
import {fileURLToPath} from 'node:url';
import {FileBlob,SpreadsheetFile} from '@oai/artifact-tool';
const input=JSON.parse(await fs.readFile(process.argv[2],'utf8'));
const wb=await SpreadsheetFile.importXlsx(await FileBlob.load(fileURLToPath(new URL('./templates/monthly.xlsx',import.meta.url))));
const [year,month]=input.month.split('-').map(Number),fy=year-(month<4?1:0);
const sheetName=month<10?String(month).replace(/[0-9]/g,c=>String.fromCharCode(c.charCodeAt(0)+65248))+'月':month+'月';
const meta=JSON.parse(await fs.readFile(new URL('./templates/monthly.json',import.meta.url),'utf8'));
const originalTotal=meta[sheetName].total,capacity=originalTotal-9;
const sheet=wb.worksheets.getItem(sheetName),records=input.records||[];
const count=Math.max(capacity,records.length),last=8+count,total=last+1,start=total+3,end=start+12,delta=count-capacity;
const literal=v=>typeof v==='string'&&v.startsWith('=')?"'"+v:v;
const put=(cell,value)=>sheet.getRange(cell).values=[[literal(value??'')]];
// Move the template's summary below the last detail row when the month is larger.
if(delta){sheet.getRange(`A${total}:O${end+1}`).copyFrom(sheet.getRange(`A${originalTotal}:O${originalTotal+16}`),'all');for(let r=originalTotal;r<=last;r++)sheet.getRange(`A${r}:O${r}`).copyFrom(sheet.getRange(`A${originalTotal-1}:O${originalTotal-1}`),'all');}
sheet.getRange(`A9:O${last}`).clear({applyTo:'contents'});
put('A2',`令和${fy-2018}年度　技術相談（指導）記録簿（${month}月分）`);
const orgs=[...new Set(records.map(d=>d.staffOrg).filter(Boolean))];
put('I3','研究所名：'+orgs.join('・'));put('I4','部 ・室名：');
const abbreviations={'工業総合研究所':'工総研','弘前工業研究所':'弘工研','八戸工業研究所':'八工研','農林総合研究所':'農総研','野菜研究所':'野菜研','りんご研究所':'りんご研','畜産研究所':'畜産研','林業研究所':'林業研','水産総合研究所':'水総研','内水面研究所':'内水研','食品総合研究所':'食総研','下北ブランド研究所':'下北研','デモ研究所':'農加研'};
for(let i=0;i<records.length;i++){
 const d=records[i],r=i+9;
 const methods=(d.methods||[]).map(x=>x==='WEB'?'Web':x).join('・');
 const party=[d.partyOrg,d.partyName,d.tel?'TEL '+d.tel:'',d.fax?'FAX '+d.fax:''].filter(Boolean).join('\n');
 const date=new Date(d.consultationDate+'T00:00:00Z');
 const values=[d.recordNo||'',date,abbreviations[d.staffOrg]||d.staffOrg||'',d.staffName||'',methods,party,d.address||'',d.summaryConsultation,d.summaryResponse,1,'有','','','',d.summaryPlan||''];
 sheet.getRange(`A${r}:O${r}`).values=[values.map(literal)];
 sheet.getRange(`B${r}`).setNumberFormat('m/d');
 // Expand only populated rows so long summaries, contact information and five staff remain readable.
 const lineCount=(value,width)=>String(value||'').split('\n').reduce((n,line)=>n+Math.max(1,Math.ceil([...line].length/width)),0);
 const lines=Math.max(lineCount(party,9),lineCount(d.staffName,7),lineCount(d.summaryConsultation,17),lineCount(d.summaryResponse,17),lineCount(d.address,6),lineCount(methods,6),lineCount(d.summaryPlan,12));
 sheet.getRange(`A${r}:O${r}`).format.rowHeight=Math.max(44,Math.min(400,lines*14+10));
}
sheet.getRange(`E9:E${last}`).dataValidation={rule:{type:'list',values:['電話','メール','来所','現場','FAX','Web','その他']}};
sheet.getRange(`E${total}`).formulas=[[`=COUNT(B9:B${last})`]];
sheet.getRange(`J${total}`).formulas=[[`=IF(COUNT(J9:J${last})=0,"",SUM(J9:J${last}))`]];
for(let r=start;r<=end;r++){
 sheet.getRange(`C${r}`).formulas=[[`=COUNTIF($C$9:$C$${last},B${r})`]];
 sheet.getRange(`J${r}`).formulas=[[`=IF(COUNT($J$9:$J$${last})=0,"",SUMIF($C$9:$C$${last},I${r},$J$9:$J$${last}))`]];
 if(r<start+7){sheet.getRange(`E${r}`).formulas=[[`=COUNTIF($E$9:$E$${last},"*"&D${r}&"*")`]];sheet.getRange(`L${r}`).formulas=[[`=IF(COUNT($J$9:$J$${last})=0,"",SUMIF($E$9:$E$${last},"*"&K${r}&"*",$J$9:$J$${last}))`]];}
}
for(const c of ['C','E'])sheet.getRange(`${c}${end+1}`).formulas=[[`=SUM(${c}${start}:${c}${end})`]];
for(const c of ['J','L'])sheet.getRange(`${c}${end+1}`).formulas=[[`=IF(COUNT($J$9:$J$${last})=0,"",SUM(${c}${start}:${c}${end}))`]];
// The retained annual summaries must follow the moved monthly totals.
if(delta){for(const name of ['問合せ方法','月別件数、回数']){const target=wb.worksheets.getItem(name),range=target.getUsedRange(),formulas=range.formulas;for(let r=0;r<formulas.length;r++)for(let c=0;c<formulas[r].length;c++){const f=formulas[r][c];if(typeof f!=='string'||!f.includes(sheetName))continue;const fixed=f.replace(new RegExp("('"+sheetName+"'!\\$?[A-Z]+\\$?)([0-9]+)",'g'),(all,prefix,row)=>Number(row)>=originalTotal?prefix+(Number(row)+delta):all);if(fixed!==f)range.getCell(r,c).formulas=[[fixed]];}}}
// Empty months must not produce division-by-zero in the retained annual tables.
for(const name of ['問合せ方法','月別件数、回数']){const range=wb.worksheets.getItem(name).getUsedRange(),fs=range.formulas;for(let r=0;r<fs.length;r++)for(let c=0;c<fs[r].length;c++){const f=fs[r][c];if(typeof f==='string'&&f.startsWith('=')&&f.includes('/')&&!f.startsWith('=IFERROR(')){const cell=range.getCell(r,c);cell.clear({applyTo:'contents'});cell.formulas=[['=IFERROR('+f.slice(1)+',0)']];};}}
wb.recalculate();
if(process.argv[4]){
 for(const [suffix,range] of [['','A1:O11'],['-totals',`B${total}:L${end+1}`]]){
 const image=await wb.render({sheetName,range,scale:1.4});await fs.writeFile(process.argv[4]+suffix+'.png',new Uint8Array(await image.arrayBuffer()));}
}
await (await SpreadsheetFile.exportXlsx(wb)).save(process.argv[3]);
