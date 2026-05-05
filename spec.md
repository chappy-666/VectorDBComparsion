# ベクトルDB比較ポートフォリオ 仕様書

## プロジェクト概要

ベクトルDB（Qdrant vs pgvector）の性能比較をテーマにしたフルスタックポートフォリオ。  
RAGシステムを実装しつつ、同一クエリに対する2つのDBの検索速度・精度をUIから比較できる。

---

## 目的

- ベクトルDBの性能比較検証（Qdrant vs pgvector）
- フルスタック × AI × インフラ構成のポートフォリオとしてのアピール
- 完全オンプレ・ローカル動作による再現性の確保

---

## システム構成

```
フロント＋プロキシ : Next.js（React）
バックエンド       : Python + LangGraph
ローカルLLM        : Ollama（Apple Silicon対応）
ベクトルDB①       : Qdrant
ベクトルDB②       : pgvector（PostgreSQL拡張）
```

---

## インフラ

- **全サービスをDocker Composeで一括起動**
- 開発環境: Apple M1 Pro / 32GB RAM

### docker-compose サービス一覧

| サービス名 | 技術                  | 備考                               |
| ---------- | --------------------- | ---------------------------------- |
| frontend   | Next.js               | フロント＋APIプロキシ              |
| backend    | Python + LangGraph    | RAGエージェント                    |
| ollama     | Ollama                | ローカルLLM（Metal GPU使用）       |
| qdrant     | Qdrant                | ベクトルDB①（ARM64ネイティブ対応） |
| pgvector   | PostgreSQL + pgvector | ベクトルDB②（ARM64ネイティブ対応） |

---

## 各レイヤーの詳細

### フロントエンド（Next.js）
- React でUI実装
- Next.js の API Route をバックエンドへのプロキシとして使用
- UIから Qdrant / pgvector を**動的に切り替え可能**
- 同一クエリに対する2DBの検索結果・レイテンシを並べて表示

### バックエンド（Python + LangGraph）
- LangGraph によるRAGエージェントの構築
- DB切り替えロジックをバックエンド側で管理
- 検索レイテンシ・スコアを計測してフロントに返す

### ローカルLLM（Ollama）
- Apple Silicon（Metal）を自動使用
- 初回のみ `ollama pull <model>` が必要
- 推奨モデル: `llama3` または `mistral`

### ベクトルDB

#### Qdrant
- 専用ベクトルDB
- ARM64ネイティブ対応
- Dockerで簡単起動

#### pgvector
- PostgreSQL の拡張機能
- ARM64ネイティブ対応
- 汎用RDBとしての運用実績が豊富で求人・認知度が高い

---

## ユースケース（デモ内容）

以下の2つを候補として想定：

### ① RAG（検索拡張生成）
- PDFや文書をアップロードし、自然言語で質問 → LLMが回答
- Qdrant / pgvector それぞれで検索し、速度・精度を比較

### ② セマンティック検索
- 商品・求人などのデータをインポート
- 曖昧なクエリでの検索結果をキーワード検索と比較して表示

---

## ポートフォリオとしての差別化ポイント

- **「専用ベクトルDB vs 汎用DB拡張」** という明確な比較軸
- フルスタック（React/Next.js）× AI（LangGraph/Ollama）× インフラ（Docker）の横断的スキルアピール
- UIから動的にDBを切り替えてリアルタイム比較できるデモ
- 完全オンプレ・ローカル動作で再現性が高い

---

## 技術スタック一覧

| カテゴリ       | 技術                           |
| -------------- | ------------------------------ |
| フロントエンド | React, Next.js, Tailwind CSS   |
| バックエンド   | Python, LangGraph              |
| LLM            | Ollama（llama3 / mistral）     |
| ベクトルDB     | Qdrant, pgvector（PostgreSQL） |
| インフラ       | Docker, Docker Compose         |
| 開発環境       | Apple M1 Pro, 32GB RAM         |

---

## 今後のタスク

- [ ] `docker-compose.yml` の作成
- [ ] 各サービスの疎通確認
- [ ] バックエンドからQdrant/pgvectorへの接続実装
- [ ] LangGraphによるRAGパイプライン構築
- [ ] DB切り替えUIの実装
- [ ] 比較結果（レイテンシ・精度）の可視化