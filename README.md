# ベクトルDB比較ポートフォリオ

Qdrant vs pgvector の性能比較をテーマにしたフルスタックポートフォリオプロジェクト。  
同一クエリに対する2つのベクトルDBの検索速度・精度をUIから比較できるRAGシステム。

---

## アーキテクチャ

```
Frontend (Next.js :3000)
        ↓
Backend (Python + LangGraph :8000)
        ↓
Qdrant (:6333)    │    pgvector / PostgreSQL (:5432)
        └─────────┴─────────┘
              Ollama (:11434)
```

---

## 技術スタック

| カテゴリ | 技術 |
|---|---|
| フロントエンド | React, Next.js, Tailwind CSS |
| バックエンド | Python, LangGraph |
| LLM | Ollama（llama3.2 / mistral） |
| ベクトルDB | Qdrant, pgvector（PostgreSQL拡張） |
| インフラ | Docker, Docker Compose |
| 開発環境 | Apple M1 Pro / 32GB RAM |

---

## セットアップ

### 前提条件

- Docker / Docker Compose
- Apple Silicon (M1/M2/M3) 推奨（Metal GPU 使用）

### 起動手順

```bash
# 1. リポジトリをクローン
git clone https://github.com/chappy-666/VectorDBComparsion.git
cd VectorDBComparsion

# 2. LLMモデルのプル（初回のみ）
docker compose run --rm ollama ollama pull llama3.2

# 3. 全サービスを起動
docker compose up -d

# 4. フロントエンドにアクセス
open http://localhost:3000
```

### サービス一覧

| サービス名 | URL | 説明 |
|---|---|---|
| Frontend | http://localhost:3000 | Next.js フロントエンド |
| Backend | http://localhost:8000 | Python + LangGraph API |
| Ollama | http://localhost:11434 | ローカルLLM |
| Qdrant | http://localhost:6333 | ベクトルDB① |
| pgvector | localhost:5432 | ベクトルDB② (PostgreSQL) |

---

## ユースケース

### RAG（検索拡張生成）

PDFや文書をアップロードし、自然言語で質問 → LLMが回答。  
Qdrant / pgvector それぞれで検索し、速度・精度を並べて比較。

### セマンティック検索

曖昧なクエリでの検索結果をキーワード検索と比較して表示。  
UIからQdrant / pgvector を動的に切り替え可能。

---

## ポートフォリオとしての差別化ポイント

- **「専用ベクトルDB vs 汎用DB拡張」** という明確な比較軸
- フルスタック（React/Next.js）× AI（LangGraph/Ollama）× インフラ（Docker）の横断的スキル
- UIから動的にDBを切り替えてリアルタイム比較できるデモ
- 完全オンプレ・ローカル動作で再現性が高い
