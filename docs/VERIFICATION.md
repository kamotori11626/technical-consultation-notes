# 検証結果

この移行でコピーしたコードを対象に再実行した結果です。外部の有料AIは実行していません。

| 確認 | 結果 | 実際に確認した範囲 |
|---|---|---|
| `cd demo && npm test` | PASS | 認証、CSRF、保護対象の画面・API、秘密値・実DBへのアクセス拒否、5回の同時実行制限、DOCX生成、和暦変換 |
| `cd demo && npm run build && npm run validate` | PASS | Worker成果物の構築、ESM構文とfetch入口 |
| `node local-app/tests/gemini-client.cjs` | PASS | 3段階の欄反映、確認ゲート、基本情報のAI送信除外、処理中の編集保護、不正な出力時の入力保持 |
| `node local-app/tests/record-export.cjs` | PASS | 架空データによるDOCX生成、特殊文字、ファイル名、基本メタデータ |
| `cd local-app && python3 tests/test_gemini.py` | 5件 OK | モックAI応答、未設定キー、不正JSON、タイムアウト、localhostのHTTP境界 |
| `cd local-app && python3 tests/test_records.py` | PASS | 架空DOCX取込、一時DBの保存・更新・版競合、重複拒否、日付、月次Excel、PDF |
| `python3 scripts/audit_repository.py` | PASS | コピー対象の禁止パス、キー形式・連絡先、埋込DOCX XML、Excel XMLと作成者メタデータ |

PDF・Excelテストは、元のMacで利用可能なCodex同梱Node・LibreOffice・Artifact Toolを一時的に参照して実行しました。依存ライブラリの実体やMacのフォントはコミットしません。任意のPCでのPDF・Excel実行を確認した結果ではありません。

元の暗号化設定ファイルにある秘密値とコピー対象も、値を表示せずに照合しました。復号したAPIキーとの照合と、到達可能なGit履歴の検査は `scripts/audit_repository.py --history` で行います。

元のSites用履歴には既存サイト識別子や個人メールの作成者情報があるため、履歴を丸ごと複製せず、新しいGit履歴として取り込みます。コミット作成者・更新者はGitHubハンドルとnoreplyアドレスに限定します。

## 確認済みと扱わないこと

- 公開サイトでの有料AI生成の成功：以前にモデル利用不可を確認し、未修正。
- AI回答の技術的正確性、資料閲覧の完全性、製品の安全性。
- 業務導入、作業時間短縮、利用者評価などの効果。
- 月100円の円建て請求上限の保証。
- 一般のPCでのPDF・Excel実行環境。

既存の公開サイトはSites版2のままです。本移行ではホスティング配備、秘密設定、利用回数表、実相談DBを変更していません。

## 一般公開時の再確認（2026年10月28日）

ユーザーが白紙DOCX・Excel様式の一般公開・再配布を許可しました。コードと到達可能な履歴、埋め込み様式を再監査し、本番の秘密値や実相談DBは検出していません。公開準備の説明更新コミットに個人メールが付いたため、履歴内容を保って作成者・更新者をnoreplyへ統一します。元の履歴はローカルで保全します。
