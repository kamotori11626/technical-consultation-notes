"""Restore print settings omitted by Artifact Tool's XLSX exporter."""
import copy,io,json,re,zipfile
from xml.etree import ElementTree as E
from pathlib import Path
S='http://schemas.openxmlformats.org/spreadsheetml/2006/main'
R='http://schemas.openxmlformats.org/officeDocument/2006/relationships'
NS={'s':S}
def restore(raw,month,count):
    root=Path(__file__).parent/'templates'
    with zipfile.ZipFile(io.BytesIO(raw)) as z:parts={n:z.read(n) for n in z.namelist()}
    with zipfile.ZipFile(root/'monthly.xlsx') as z:original={n:z.read(n) for n in z.namelist()}
    m=int(month[-2:]);name=(str(m).translate(str.maketrans('123456789','１２３４５６７８９')) if m<10 else str(m))+'月'
    meta=json.loads((root/'monthly.json').read_text());delta=max(0,count-(meta[name]['total']-9))
    wb=E.fromstring(parts['xl/workbook.xml']);oldwb=E.fromstring(original['xl/workbook.xml'])
    for i,sh in enumerate(wb.find('s:sheets',NS)):
        path=f'xl/worksheets/sheet{i+1}.xml';sheet=E.fromstring(parts[path]);old=E.fromstring(original[path])
        # The exporter can retain an old error cache for shared IFERROR formulas.
        # IFERROR(...,0) evaluates to zero when that cached expression is an error.
        shared={f.get('si'):f.text for f in sheet.findall('.//s:f',NS) if f.get('t')=='shared' and f.text}
        for cell in sheet.findall('.//s:c',NS):
            formula=cell.find('s:f',NS);value=cell.find('s:v',NS)
            expression=(formula.text or shared.get(formula.get('si'),'') or '') if formula is not None else ''
            if cell.get('t')=='e' and expression.startswith('IFERROR(') and expression.endswith(',0)'):
                cell.attrib.pop('t',None)
                if value is not None:value.text='0'
        # Ordered before drawings, comments and extension lists in SpreadsheetML.
        tags=['printOptions','pageMargins','pageSetup','headerFooter','rowBreaks','colBreaks']
        for tag in tags:
            for child in list(sheet):
                if child.tag=='{'+S+'}'+tag:sheet.remove(child)
        pos=next((j for j,c in enumerate(sheet) if c.tag.split('}')[-1] in ['drawing','legacyDrawing','legacyDrawingHF','picture','oleObjects','controls','webPublishItems','tableParts','extLst']),len(sheet))
        for tag in tags:
            node=old.find('s:'+tag,NS)
            if node is not None:
                node=copy.deepcopy(node);node.attrib.pop('{'+R+'}id',None);sheet.insert(pos,node);pos+=1
        props=sheet.find('s:sheetPr',NS)
        if props is None:props=E.Element('{'+S+'}sheetPr');sheet.insert(0,props)
        setup=E.SubElement(props,'{'+S+'}pageSetUpPr');setup.set('fitToPage','1')
        views=sheet.find('s:sheetViews',NS)
        if views is not None:
            for view in views:view.set('tabSelected','1' if sh.get('name')==name else '0')
        parts[path]=E.tostring(sheet,encoding='utf-8',xml_declaration=True)
    previous=wb.find('s:definedNames',NS)
    if previous is not None:wb.remove(previous)
    names=copy.deepcopy(oldwb.find('s:definedNames',NS))
    if names is not None:
        for n in names:
            if n.get('name')=='_xlnm.Print_Area' and name in (n.text or '') and delta:
                n.text=re.sub(r'(\$[A-Z]+\$)(\d+)$',lambda x:x[1]+str(int(x[2])+delta),n.text)
        wb.insert(list(wb).index(wb.find('s:sheets',NS))+1,names)
    for v in wb.findall('s:bookViews/s:workbookView',NS):v.set('activeTab',str(next(i for i,s in enumerate(wb.find('s:sheets',NS)) if s.get('name')==name)))
    calc=wb.find('s:calcPr',NS)
    if calc is None:calc=E.SubElement(wb,'{'+S+'}calcPr')
    calc.set('fullCalcOnLoad','1');calc.set('forceFullCalc','1')
    parts['xl/workbook.xml']=E.tostring(wb,encoding='utf-8',xml_declaration=True)
    out=io.BytesIO()
    with zipfile.ZipFile(out,'w',zipfile.ZIP_DEFLATED) as z:
        for p,b in parts.items():z.writestr(p,b)
    return out.getvalue()
