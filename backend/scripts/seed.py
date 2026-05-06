#!/usr/bin/env python3
"""Seed both Qdrant and pgvector with dummy documents for testing."""

import sys
import os

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from db import qdrant_client as qdrant_db
from db import pgvector_client as pg_db
from pipeline.indexer import index_documents

DOCUMENTS = [
    {
        "content": (
            "Qdrantは、高性能なベクトル類似度検索に特化したオープンソースのベクトルデータベースエンジンです。"
            "Rustで実装されており、大規模なベクトルデータに対して低レイテンシかつ高スループットな検索を実現します。"
            "フィルタリングや分散構成にも対応しており、本番環境での運用に適しています。"
        ),
        "metadata": {"category": "vector_db", "title": "Qdrantの概要"},
    },
    {
        "content": (
            "pgvectorはPostgreSQLの拡張機能で、リレーショナルデータベース上でベクトル類似度検索を可能にします。"
            "既存のPostgreSQLインフラをそのまま活用できるため、追加サービスなしでベクトル検索を導入できます。"
            "IVFFlatインデックスやHNSWインデックスによる近似最近傍探索もサポートしています。"
        ),
        "metadata": {"category": "vector_db", "title": "pgvectorの概要"},
    },
    {
        "content": (
            "専用ベクトルDBと汎用DB拡張の比較では、用途によって最適な選択肢が異なります。"
            "Qdrantは純粋なベクトル検索に最適化されており、大規模データで特に速度面で優位です。"
            "一方pgvectorは既存のPostgreSQLエコシステムと統合できるため、運用コストを抑えられます。"
        ),
        "metadata": {"category": "vector_db", "title": "ベクトルDB比較"},
    },
    {
        "content": (
            "RAG（Retrieval-Augmented Generation）は、LLMの知識をベクトル検索で外部文書から補強する手法です。"
            "ユーザーのクエリをベクトル化し、意味的に近い文書を検索してLLMのプロンプトに追加することで、"
            "ハルシネーションを抑制しながら最新情報に基づいた回答を生成できます。"
        ),
        "metadata": {"category": "machine_learning", "title": "RAGの仕組み"},
    },
    {
        "content": (
            "埋め込みベクトル（Embedding）は、テキストや画像などのデータを高次元の実数ベクトルで表現したものです。"
            "意味的に近いデータは埋め込み空間でも近い位置に配置されるため、"
            "コサイン類似度やユークリッド距離で類似度を数値的に計算できます。"
        ),
        "metadata": {"category": "machine_learning", "title": "埋め込みベクトルとは"},
    },
    {
        "content": (
            "大規模言語モデル（LLM）は、大量のテキストデータで事前学習されたニューラルネットワークです。"
            "GPT、LLaMA、Mistralなどが代表的なモデルです。"
            "自然言語の生成・要約・翻訳・コード生成など多様なタスクをこなせます。"
        ),
        "metadata": {"category": "machine_learning", "title": "LLMの概要"},
    },
    {
        "content": (
            "Ollamaは、LLaMA・Mistral・Gemmaなどのオープンソースモデルをローカル環境で簡単に実行できるツールです。"
            "Apple Silicon（Metal）やNVIDIA GPU（CUDA）に対応しており、"
            "APIサーバーとして起動すればOpenAI互換のエンドポイントとしても利用できます。"
        ),
        "metadata": {"category": "machine_learning", "title": "Ollamaの使い方"},
    },
    {
        "content": (
            "コサイン類似度は、2つのベクトルがなす角度のコサイン値で類似度を計算する指標です。"
            "値は-1から1の範囲を取り、1に近いほど意味的に近いことを示します。"
            "ベクトルの大きさではなく方向の近さを測るため、文書の長さに依存しない比較が可能です。"
        ),
        "metadata": {"category": "machine_learning", "title": "コサイン類似度"},
    },
    {
        "content": (
            "Dockerは、アプリケーションとその依存関係をコンテナとしてパッケージ化するプラットフォームです。"
            "「自分のマシンでは動く」問題を解消し、開発・テスト・本番環境の一致を実現します。"
            "軽量で起動が速く、仮想マシンよりも効率的にリソースを活用できます。"
        ),
        "metadata": {"category": "infrastructure", "title": "Dockerの概要"},
    },
    {
        "content": (
            "Docker Composeは、複数コンテナで構成されるアプリケーションを単一のYAMLファイルで定義・管理するツールです。"
            "`docker compose up -d` で全サービスをバックグラウンド起動でき、"
            "サービス間のネットワークやボリュームも自動設定されます。"
        ),
        "metadata": {"category": "infrastructure", "title": "Docker Composeの使い方"},
    },
    {
        "content": (
            "FastAPIは、Pythonで高性能なWeb APIを構築するためのモダンなフレームワークです。"
            "Pydanticによる型安全なリクエスト/レスポンスの定義、自動生成されるOpenAPIドキュメント、"
            "async/awaitによる非同期処理に対応しており、開発効率と実行速度を両立しています。"
        ),
        "metadata": {"category": "programming", "title": "FastAPIの特徴"},
    },
    {
        "content": (
            "LangGraphは、LLMを活用した複雑なエージェントワークフローをグラフ構造で表現・実行するライブラリです。"
            "ノードとエッジでステートマシンを定義し、条件分岐・ループ・並列実行を宣言的に記述できます。"
            "LangChainエコシステムと統合されており、RAGパイプラインの構築にも広く使われています。"
        ),
        "metadata": {"category": "programming", "title": "LangGraphの概要"},
    },
    {
        "content": (
            "Pythonは、シンプルな構文と豊富なライブラリエコシステムで、AIエンジニアリングのデファクトスタンダードです。"
            "NumPy・Pandas・PyTorchなどの数値計算ライブラリと、"
            "LangChain・LlamaIndex・Hugging Faceなどのすぐに使えるAIフレームワークが揃っています。"
        ),
        "metadata": {"category": "programming", "title": "PythonとAI開発"},
    },
    {
        "content": (
            "Next.jsは、Reactベースのフルスタックフレームワークで、SSR・SSG・ISRを柔軟に選択できます。"
            "App RouterによるサーバーコンポーネントとAPI Routeによるバックエンドプロキシ機能を持ち、"
            "フロントエンドとBFFを単一リポジトリで管理できます。"
        ),
        "metadata": {"category": "web_development", "title": "Next.jsの特徴"},
    },
    {
        "content": (
            "セマンティック検索は、キーワードの完全一致ではなく意味的な近さに基づいて検索結果を返す手法です。"
            "「安いスニーカー」と検索すると「低価格のランニングシューズ」なども上位に来るように、"
            "ユーザーの意図を理解した検索が可能になります。ECサイトや求人検索での活用が進んでいます。"
        ),
        "metadata": {"category": "machine_learning", "title": "セマンティック検索の活用"},
    },
]


def main() -> None:
    print(f"Connecting to Qdrant and pgvector...")
    qdrant = qdrant_db.get_client()
    qdrant_db.ensure_collection(qdrant)

    pg_conn = pg_db.get_connection()
    pg_db.ensure_table(pg_conn)

    print(f"Indexing {len(DOCUMENTS)} documents into both DBs...")
    stats = index_documents(DOCUMENTS, qdrant, pg_conn)
    print(f"Done. Indexed {stats['chunks']} chunks.")

    pg_conn.close()


if __name__ == "__main__":
    main()
