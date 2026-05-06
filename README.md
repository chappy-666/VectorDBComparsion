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

## テストデータの投入と動作確認

### 1. シードデータの投入

15件のダミー文書（ベクトルDB・機械学習・インフラ等）を Qdrant・pgvector 双方に格納します。

```bash
docker compose exec backend python scripts/seed.py
# => Done. Indexed 15 chunks.
```

### 2. ベクトル検索API（`/search`）

同一クエリで両DBを検索し、結果とレイテンシを比較します。

```bash
curl -s -X POST http://localhost:8000/search \
  -H "Content-Type: application/json" \
  -d '{"query": "ベクトルデータベースの比較", "db": "both", "top_k": 3}' \
  | python3 -m json.tool
```

レスポンス例（抜粋）:

```json
{
  "query": "ベクトルデータベースの比較",
  "qdrant": [
    {"doc_id": "...", "content": "コサイン類似度は...", "score": 0.565, "metadata": {"title": "コサイン類似度"}}
  ],
  "pgvector": [
    {"doc_id": "...", "content": "コサイン類似度は...", "score": 0.565, "metadata": {"title": "コサイン類似度"}}
  ],
  "qdrant_latency_ms": 22.0,
  "pgvector_latency_ms": 11.6
}
```

`db` パラメータは `"qdrant"` / `"pgvector"` / `"both"` で切り替え可能。

### 3. RAGエージェントAPI（`/rag`）

LangGraphによるRAGエージェントを使って、検索結果をもとにOllamaが自然言語で回答を生成します。

```bash
curl -s -X POST http://localhost:8000/rag \
  -H "Content-Type: application/json" \
  -d '{"query": "ベクトルDBの選び方を教えてください", "db": "both", "top_k": 3}' \
  | python3 -m json.tool
```

レスポンス例（抜粋）:

```json
{
  "query": "ベクトルDBの選び方を教えてください",
  "answer": "ベクトルデータベースを選択する際は、次のような要素を考慮することが重要です。\n- Qdrantはフィルタリングと近似最近傍探索を組み合わせた高速な検索を提供します...",
  "sources": [
    {"doc_id": "...", "content": "Qdrantは、高性能な...", "score": 0.569, "metadata": {"title": "Qdrantの概要"}}
  ],
  "retry_count": 0,
  "qdrant_latency_ms": 4.3,
  "pgvector_latency_ms": 4.7
}
```

#### グラフの処理フロー

```
query_analyzer → retriever → evaluator ─→ generator → 回答返却
                               ↑___________↙
                         (スコア平均 < 0.5 かつリトライ上限未達の場合、
                          LLMがクエリを言い換えて再検索。最大2回)
```

| フィールド | 説明 |
|---|---|
| `answer` | 検索結果をコンテキストとしてOllamaが生成した回答 |
| `sources` | 回答の根拠となった検索結果（スコア降順） |
| `retry_count` | クエリの言い換えと再検索を行った回数（最大2） |
| `qdrant_latency_ms` | Qdrant検索にかかった時間（ms） |
| `pgvector_latency_ms` | pgvector検索にかかった時間（ms） |

---

## ユースケース

### RAG（検索拡張生成）

PDFや文書をアップロードし、自然言語で質問 → LLMが回答。  
Qdrant / pgvector それぞれで検索し、速度・精度を並べて比較。

### セマンティック検索

曖昧なクエリでの検索結果をキーワード検索と比較して表示。  
UIからQdrant / pgvector を動的に切り替え可能。

---

## 比較条件

### 公平性の担保

性能比較の公平性を確保するため、以下の条件を両DB間で統一しています。

- **同一データ**: 同じチャンク分割済みドキュメントを両DBに格納
- **同一ベクトル**: Embeddingは1回だけ生成し、同じベクトルを両DBに投入
- **同一クエリ**: 検索リクエストごとに同じクエリベクトルを両DBに送信
- **同一環境**: 同一ホスト上のDockerコンテナとして実行（Apple M1 Pro / 32GB RAM）

### インデックス設定

インデックスの設定は検索性能に大きく影響するため、比較において最も重要な要素です。

| | Qdrant | pgvector |
|---|---|---|
| インデックス種別 | HNSW | HNSW |
| 探索方式 | 近似最近傍探索（ANN） | 近似最近傍探索（ANN） |
| 備考 | デフォルトでHNSW有効 | 明示的にインデックス作成が必要 |

pgvectorはインデックスを作成しない場合、逐次スキャン（正確な最近傍探索）にフォールバックします。これは精度は高いものの大幅に低速になるため、比較の公平性を保つために両DBともHNSWを使用しています。

### 計測項目

| 項目 | 説明 |
|---|---|
| レイテンシ（ms） | 検索リクエスト送信から結果取得までの所要時間 |
| Top-K 検索結果 | 返却されたドキュメントとその類似度スコア |
| 結果の重複率 | 両DBの検索結果に共通して含まれるドキュメントの割合 |

### 制約事項

- 単一マシン上での実行のため、CPU・メモリのリソース競合がレイテンシに影響する可能性がある
- 小規模データセットでの検証のため、本番規模でのスケーラビリティは未検証
- Ollama（LLM）が同一ホストで稼働しており、RAGクエリ時のレイテンシ計測に影響する可能性がある
- QdrantのIDを `hash()` で生成しているため、ハッシュ衝突によりQdrant側の実効データ件数が減少するリスクがある

---

## ポートフォリオとしての差別化ポイント

- **「専用ベクトルDB vs 汎用DB拡張」** という明確な比較軸
- フルスタック（React/Next.js）× AI（LangGraph/Ollama）× インフラ（Docker）の横断的スキル
- UIから動的にDBを切り替えてリアルタイム比較できるデモ
- 完全オンプレ・ローカル動作で再現性が高い