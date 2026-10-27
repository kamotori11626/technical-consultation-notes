import sys,json,unittest,io,threading,urllib.request,urllib.error
from pathlib import Path
from unittest.mock import patch
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
import server
class GeminiTests(unittest.TestCase):
 def fake(self,stage,**extra):
  candidate={'finishReason':'STOP','content':{'parts':[{'text':json.dumps({k:'テスト' for k in server.FIELDS[stage]})}]},**extra}
  return io.BytesIO(json.dumps({'candidates':[candidate]}).encode())
 def test_three_stages(self):
  for stage in server.FIELDS:
   with patch.object(server,'api_key',return_value='dummy'),patch.object(server.urllib.request,'urlopen',return_value=self.fake(stage)) as call:
    out=server.generate(stage,'指示')
    self.assertEqual(set(out['fields']),set(server.FIELDS[stage]))
    payload=json.loads(call.call_args.args[0].data)
    self.assertEqual('tools' in payload,stage=='research')
 def test_missing_key(self):
  with patch.object(server,'api_key',return_value=''),self.assertRaisesRegex(ValueError,'未設定'):server.generate('memo','指示')
 def test_bad_json(self):
  c={'candidates':[{'finishReason':'STOP','content':{'parts':[{'text':'not json'}]}}]}
  with patch.object(server,'api_key',return_value='dummy'),patch.object(server.urllib.request,'urlopen',return_value=io.BytesIO(json.dumps(c).encode())),self.assertRaisesRegex(ValueError,'出力形式'):server.generate('record','指示')
 def test_timeout(self):
  with patch.object(server,'api_key',return_value='dummy'),patch.object(server.urllib.request,'urlopen',side_effect=TimeoutError()),self.assertRaisesRegex(ValueError,'時間切れ'):server.generate('memo','指示')
 def test_http_boundary(self):
  http=server.ThreadingHTTPServer(('127.0.0.1',0),server.Handler);threading.Thread(target=http.serve_forever,daemon=True).start();base=f'http://127.0.0.1:{http.server_port}'
  try:
   for path in ['/.env','/server.py','/%2eenv','/../.env']:
    with self.assertRaises(urllib.error.HTTPError) as e:urllib.request.urlopen(base+path)
    self.assertEqual(e.exception.code,404)
   req=urllib.request.Request(base+'/api/generate',data=b'{}',headers={'Origin':'https://evil.example'})
   with self.assertRaises(urllib.error.HTTPError) as e:urllib.request.urlopen(req)
   self.assertEqual(e.exception.code,403)
  finally:http.shutdown();http.server_close()
if __name__=='__main__':unittest.main()
