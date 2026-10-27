import sys,tempfile,base64,json,zipfile,io
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
import records_store as s
with tempfile.TemporaryDirectory() as td:
 s.DB=Path(td)/'db.sqlite3'
 raw=Path('/private/tmp/record-export-test.docx').read_bytes();encoded=base64.b64encode(raw).decode()
 parsed=s.parse_docx(raw)['data'];assert parsed['recordNo']=='TEST';assert '原因は未確認' in parsed['response'];assert parsed['methods']==['電話','メール']
 parsed.update(displayDate='令和８年９月２５日',recordNo='',partyOrg='',summaryPlan='',summaryConsultation='乾燥条件について相談した。',summaryResponse='原因は未確認と説明した。')
 first=s.save({'data':parsed,'docx':encoded});assert first['revision']==1
 parsed['remarks']='更新'
 updated=s.save({**first,'data':parsed,'docx':encoded});assert updated['revision']==2;assert len(s.listing()['records'])==1
 try:s.save({**first,'data':parsed});raise AssertionError('conflict not blocked')
 except ValueError:pass
 try:s.save({'data':parsed,'docx':encoded});raise AssertionError('duplicate not blocked')
 except ValueError:pass
 assert s.get(first['id'])['data']['consultationDate']=='2026-09-25'
 assert s.parse_date('令和７年３月３１日')=='2025-03-31';assert s.parse_date('不明')==''
 out=s.monthly('2026-09');Path('/private/tmp/monthly-test.xlsx').write_bytes(out)
 with zipfile.ZipFile(io.BytesIO(out)) as z:assert 'xl/workbook.xml' in z.namelist()
 pdf=s.pdf(raw);assert pdf.startswith(b'%PDF');Path('/private/tmp/records-preview.pdf').write_bytes(pdf)
 print('PASS: DOCX extraction, optional fields, date parsing, create/update/revision conflict, duplicate rejection, XLSX, PDF')
