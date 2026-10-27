# 実行手順

## 採用向けデモ

Node.js 22以降、Python 3.10以降（秘密情報監査用）、Gitを使用します。`demo/` のNode処理にはnpmライブラリの追加インストールは不要です。

```sh
cd demo
npm test
npm run build
npm run validate
npm run dev
```

プレビューは `127.0.0.1:8776` に限定します。停止はCtrl+Cです。ポートが使用中なら、既存プロセスの目的を確認してから停止するか、`scripts/preview.mjs` のポートを変更してください。

本番の実API接続は、既存公開版で未修正のモデル利用不可があるため、成功確認済みとは扱いません。ローカルプレビューでは秘密値が不要で、実AIも無効です。

`demo/.openai/hosting.json` は移植用に `d1`・`r2` の論理名だけを残しています。既存サイトのプロジェクトIDは含めません。ビルドとローカルテストはできますが、この設定だけで既存サイトへ再配備できるものではありません。既存ホスティングを変更する手順や自動配備ワークフローは追加していません。

## ローカルPython版

```sh
cd local-app
python3 server.py
```

Python標準ライブラリだけでHTTPサーバー、SQLite保存、DOCX取込のコードを実行できます。ブラウザ内のDOCX生成も追加ライブラリ不要です。初回保存時に `local-app/data/records.sqlite3` が新しく作られます。既存の実DBをコピーしないでください。

APIキーは `local-app/.env.example` を参考に、Git管理しない `.env` またはプロセスの `GEMINI_API_KEY` へ設定します。モデル名は `config.json` または `GEMINI_MODEL` で設定します。実APIの可用性・料金・権限は各自のアカウントで確認が必要です。元の暗号化された.envやdotenvxの秘密ファイルは移行していません。

基本テスト：

```sh
node tests/gemini-client.cjs
node tests/record-export.cjs
python3 tests/test_gemini.py
```

`test_gemini.py` はGeminiへの通信をモックに置き換えます。HTTP境界テストでlocalhostの一時ポートを使います。制限された環境ではポートを開けないため、その場合はネットワーク利用が許されたローカル環境で実行してください。

## PDFと月次Excel

元の `records_store.py` は、Codex同梱ランタイムのNode・LibreOfficeと、Macの日本語フォントを参照します。一般のPython・NodeだけではPDFと月次Excelの実行環境はそろいません。`@oai/artifact-tool` とLibreOffice本体をこのリポジトリへ同梱していません。

利用可能な環境では、`tests/record-export.cjs` で架空DOCXを作成した後、`python3 tests/test_records.py` で一時DBの保存・版競合・DOCX取込・月次Excel・PDFを検証できます。出力はOSの一時フォルダに保存します。実DBをテストに使いません。

月次テンプレートは過去の明細と作成者メタデータを除いた白紙版です。元の16シートと印刷設定を使用します。2026年10月28日、ユーザーから白紙様式の一般公開・再配布が可能である旨を確認しました。
