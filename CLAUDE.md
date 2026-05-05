# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## 厳守事項

- 応答は必ず日本語で行うこと
- 無駄な感嘆詞は出さないこと
- 結論から述べること
- わからないことがあれば推論するのではなく、聞くこと

## 起動・開発コマンド

```bash
# 全サービス起動（初回はビルドに数分かかる）
docker compose up -d

# LLMモデルのプル（初回のみ必須）
docker compose run --rm ollama ollama pull llama3.2

# ログ確認
docker compose logs -f backend
docker compose logs -f frontend

# 停止
docker compose down
```

バックエンドは `--reload` 付きで起動するため、`backend/` 内のファイル変更は自動反映される。
フロントエンドも Next.js の HMR が有効。

## アーキテクチャ概要

```
Frontend (Next.js :3000)
  └─ Next.js API Route が /api/* を Backend にプロキシ
Backend (FastAPI/LangGraph :8000)
  ├─ Qdrant (:6333)   ← ベクトルDB①
  ├─ pgvector (:5432) ← ベクトルDB②
  └─ Ollama (:11434)  ← ローカルLLM
```

- **DB切り替えロジックはバックエンド側で管理**。フロントエンドはどちらのDBを使うかをリクエストパラメータで指定する。
- バックエンドのエントリーポイントは `backend/main.py`（`uvicorn main:app`）。
- LangGraph で RAG パイプラインを構築する。検索レイテンシ・スコアを計測してフロントに返す設計。

## データ永続化

`volumes/` 以下の3ディレクトリが Docker のマウント先：

| ディレクトリ        | 内容                      |
| ------------------- | ------------------------- |
| `volumes/ollama/`   | Ollama モデルファイル     |
| `volumes/qdrant/`   | Qdrant ストレージ         |
| `volumes/pgvector/` | PostgreSQL データファイル |

中身は `.gitignore` で除外し、`.gitkeep` でディレクトリ構造のみ管理している。

## コードフォーマット

- **Python**: Black（保存時に自動適用）
- **TypeScript/JS**: Prettier（保存時に自動適用）

## 環境変数

バックエンドの環境変数は `docker-compose.yml` の `backend.environment` で定義：
`OLLAMA_BASE_URL`, `QDRANT_HOST/PORT`, `PGVECTOR_HOST/PORT/USER/PASSWORD/DB`

ローカル上書きが必要な場合は `backend/.env.local` を作成する（`.gitignore` 済み）。
