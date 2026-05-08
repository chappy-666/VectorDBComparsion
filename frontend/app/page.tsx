'use client';

import { useState } from 'react';

// ─── Types ────────────────────────────────────────────────────────────────────

type DB = 'qdrant' | 'pgvector' | 'both';
type Mode = 'search' | 'rag';
type StreamStatus = 'idle' | 'streaming' | 'done' | 'error';

interface StepEvent {
  step: string;
  message: string;
  db?: string;
  latency_ms?: number;
}

interface ResultItem {
  doc_id: string;
  content: string;
  score: number;
  metadata?: {
    title?: string;
    category?: string;
    source_db?: string;
    [key: string]: unknown;
  };
}

interface SearchResponse {
  query: string;
  qdrant?: ResultItem[];
  pgvector?: ResultItem[];
  qdrant_latency_ms?: number;
  pgvector_latency_ms?: number;
}

interface RAGResponse {
  query: string;
  answer: string;
  sources: ResultItem[];
  retry_count: number;
  qdrant_latency_ms?: number;
  pgvector_latency_ms?: number;
}

// ─── SSE Parser ───────────────────────────────────────────────────────────────

function parseSSEEvents(raw: string): Array<{ event: string; data: string }> {
  return raw
    .split('\n\n')
    .filter(Boolean)
    .flatMap((block) => {
      let event = '';
      const dataLines: string[] = [];
      for (const line of block.split('\n')) {
        if (line.startsWith('event: ')) event = line.slice(7).trim();
        else if (line.startsWith('data: ')) dataLines.push(line.slice(6));
      }
      if (!event || dataLines.length === 0) return [];
      return [{ event, data: dataLines.join('\n') }];
    });
}

// ─── Sub-components ───────────────────────────────────────────────────────────

function ScoreBadge({ score }: { score: number }) {
  const cls =
    score >= 0.6
      ? 'bg-green-100 text-green-700'
      : score >= 0.45
      ? 'bg-yellow-100 text-yellow-700'
      : 'bg-red-100 text-red-700';
  return (
    <span className={`shrink-0 px-2 py-0.5 rounded-full text-xs font-mono font-semibold ${cls}`}>
      {score.toFixed(3)}
    </span>
  );
}

function ResultCard({ item, rank }: { item: ResultItem; rank: number }) {
  const sourceDb = item.metadata?.source_db as string | undefined;
  return (
    <div className="p-4 bg-white rounded-lg border border-gray-200 hover:border-indigo-300 transition-colors">
      <div className="flex items-start justify-between gap-2 mb-2">
        <div className="flex items-center gap-2 min-w-0">
          <span className="text-xs font-bold text-gray-400 shrink-0">#{rank}</span>
          {item.metadata?.title && (
            <span className="text-sm font-semibold text-gray-700 truncate">
              {item.metadata.title as string}
            </span>
          )}
          {sourceDb && (
            <span
              className={`shrink-0 text-xs px-1.5 py-0.5 rounded font-medium ${
                sourceDb === 'qdrant' ? 'bg-orange-50 text-orange-500' : 'bg-blue-50 text-blue-500'
              }`}
            >
              {sourceDb}
            </span>
          )}
        </div>
        <ScoreBadge score={item.score} />
      </div>
      <p className="text-sm text-gray-600 leading-relaxed line-clamp-3">{item.content}</p>
      {item.metadata?.category && (
        <span className="mt-2 inline-block text-xs px-2 py-0.5 bg-indigo-50 text-indigo-500 rounded">
          {item.metadata.category as string}
        </span>
      )}
    </div>
  );
}

function LatencyChart({ qdrant, pgvector }: { qdrant?: number; pgvector?: number }) {
  if (qdrant === undefined && pgvector === undefined) return null;
  const max = Math.max(qdrant ?? 0, pgvector ?? 0, 1);

  const bars = [
    qdrant !== undefined
      ? { label: 'Qdrant', value: qdrant, bar: 'bg-orange-400', text: 'text-orange-600' }
      : null,
    pgvector !== undefined
      ? { label: 'pgvector', value: pgvector, bar: 'bg-blue-400', text: 'text-blue-600' }
      : null,
  ].filter(Boolean) as { label: string; value: number; bar: string; text: string }[];

  const faster = bars.reduce((a, b) => (a.value <= b.value ? a : b));

  return (
    <div className="bg-white rounded-xl border border-gray-200 shadow-sm p-5">
      <h3 className="text-xs font-semibold text-gray-400 uppercase tracking-widest mb-4">
        レイテンシ比較
      </h3>
      <div className="space-y-3">
        {bars.map((bar) => (
          <div key={bar.label} className="flex items-center gap-3">
            <span className={`text-sm font-semibold w-20 shrink-0 ${bar.text}`}>{bar.label}</span>
            <div className="flex-1 bg-gray-100 rounded-full h-5 overflow-hidden">
              <div
                className={`h-full ${bar.bar} rounded-full transition-all duration-700`}
                style={{ width: `${Math.max((bar.value / max) * 100, 6)}%` }}
              />
            </div>
            <div className="flex items-center gap-1.5 w-28 justify-end">
              <span className="text-sm font-mono text-gray-700">{bar.value.toFixed(1)} ms</span>
              {bar.label === faster.label && bars.length > 1 && (
                <span className="text-xs bg-green-100 text-green-600 px-1.5 py-0.5 rounded font-medium">
                  速い
                </span>
              )}
            </div>
          </div>
        ))}
      </div>
      {bars.length === 2 && (
        <p className="mt-3 text-xs text-gray-400">
          差: {Math.abs((qdrant ?? 0) - (pgvector ?? 0)).toFixed(1)} ms
        </p>
      )}
    </div>
  );
}

// ノード名 → 表示スタイル
const STEP_STYLE: Record<string, { label: string; color: string }> = {
  query_analyzer: { label: 'QueryAnalyzer', color: 'text-purple-600' },
  retriever:      { label: 'Retriever',     color: 'text-gray-700'   },
  evaluator:      { label: 'Evaluator',     color: 'text-yellow-600' },
  generator:      { label: 'Generator',     color: 'text-indigo-600' },
};

function StepPanel({ steps, status }: { steps: StepEvent[]; status: StreamStatus }) {
  if (steps.length === 0 && status === 'idle') return null;

  return (
    <div className="bg-gray-900 rounded-xl border border-gray-700 p-4 font-mono text-sm">
      <div className="flex items-center gap-2 mb-3">
        <span className="text-xs font-semibold text-gray-400 uppercase tracking-widest">
          処理ステップ
        </span>
        {status === 'streaming' && (
          <span className="w-2 h-2 rounded-full bg-green-400 animate-pulse" />
        )}
      </div>
      <div className="space-y-1.5">
        {steps.map((step, i) => {
          const isLast = i === steps.length - 1;
          const isRunning = isLast && status === 'streaming' && step.latency_ms === undefined;
          const style = STEP_STYLE[step.step] ?? { label: step.step, color: 'text-gray-400' };
          const dbColor =
            step.db === 'qdrant' ? 'text-orange-400' : step.db === 'pgvector' ? 'text-blue-400' : '';

          return (
            <div key={i} className="flex items-center gap-2">
              {isRunning ? (
                <span className="w-3.5 h-3.5 border-2 border-indigo-500 border-t-transparent rounded-full animate-spin shrink-0" />
              ) : (
                <span className="text-green-400 shrink-0 text-xs">✓</span>
              )}
              <span className={`${dbColor || style.color}`}>{step.message}</span>
              {step.latency_ms !== undefined && (
                <span className="ml-auto text-gray-500 text-xs">{step.latency_ms.toFixed(1)}ms</span>
              )}
            </div>
          );
        })}
        {status === 'streaming' && steps.length === 0 && (
          <div className="flex items-center gap-2 text-gray-500">
            <span className="w-3.5 h-3.5 border-2 border-indigo-500 border-t-transparent rounded-full animate-spin shrink-0" />
            <span>起動中...</span>
          </div>
        )}
      </div>
    </div>
  );
}

function StreamingAnswer({ text, status }: { text: string; status: StreamStatus }) {
  if (!text && status !== 'streaming') return null;
  return (
    <div className="bg-white rounded-xl border border-gray-200 shadow-sm p-6">
      <h2 className="text-xs font-semibold text-gray-400 uppercase tracking-widest mb-3">回答</h2>
      <p className="text-gray-800 leading-relaxed whitespace-pre-wrap text-sm">
        {text}
        {status === 'streaming' && (
          <span className="inline-block w-0.5 h-[1.1em] bg-indigo-500 animate-pulse ml-0.5 translate-y-[2px]" />
        )}
      </p>
    </div>
  );
}

// ─── Main Page ────────────────────────────────────────────────────────────────

export default function Home() {
  const [query, setQuery] = useState('');
  const [mode, setMode] = useState<Mode>('search');
  const [db, setDb] = useState<DB>('both');
  const [topK, setTopK] = useState(5);

  // 検索モード用
  const [loading, setLoading] = useState(false);
  const [searchResult, setSearchResult] = useState<SearchResponse | null>(null);
  const [error, setError] = useState<string | null>(null);

  // RAG ストリーミング用
  const [streamStatus, setStreamStatus] = useState<StreamStatus>('idle');
  const [streamSteps, setStreamSteps] = useState<StepEvent[]>([]);
  const [streamAnswer, setStreamAnswer] = useState('');
  const [ragResult, setRagResult] = useState<RAGResponse | null>(null);

  function resetResults() {
    setSearchResult(null);
    setRagResult(null);
    setStreamSteps([]);
    setStreamAnswer('');
    setStreamStatus('idle');
    setError(null);
  }

  async function handleSubmit(e: React.FormEvent) {
    e.preventDefault();
    if (!query.trim()) return;

    resetResults();
    setLoading(true);

    if (mode === 'search') {
      try {
        const res = await fetch('/api/search', {
          method: 'POST',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify({ query: query.trim(), db, top_k: topK }),
        });
        if (!res.ok) throw new Error(`HTTP ${res.status}`);
        setSearchResult(await res.json() as SearchResponse);
      } catch (err) {
        setError(err instanceof Error ? err.message : '不明なエラーが発生しました');
      } finally {
        setLoading(false);
      }
      return;
    }

    // ── RAG ストリーミング ──────────────────────────────────────────────────────
    setStreamStatus('streaming');

    try {
      const res = await fetch('/api/rag', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ query: query.trim(), db, top_k: topK }),
      });
      if (!res.ok || !res.body) throw new Error(`HTTP ${res.status}`);

      const reader = res.body.getReader();
      const decoder = new TextDecoder();
      let buffer = '';

      while (true) {
        const { done, value } = await reader.read();
        if (done) break;

        buffer += decoder.decode(value, { stream: true });
        const cutAt = buffer.lastIndexOf('\n\n') + 2;
        if (cutAt < 2) continue;

        const chunk = buffer.slice(0, cutAt);
        buffer = buffer.slice(cutAt);

        for (const { event, data } of parseSSEEvents(chunk)) {
          try {
            const payload = JSON.parse(data);
            if (event === 'step') {
              setStreamSteps((prev) => [...prev, payload as StepEvent]);
            } else if (event === 'token') {
              setStreamAnswer((prev) => prev + (payload as { token: string }).token);
            } else if (event === 'done') {
              setRagResult(payload as RAGResponse);
              setStreamStatus('done');
            } else if (event === 'error') {
              throw new Error((payload as { message: string }).message);
            }
          } catch (parseErr) {
            if (parseErr instanceof SyntaxError) continue;
            throw parseErr;
          }
        }
      }
    } catch (err) {
      setError(err instanceof Error ? err.message : '不明なエラーが発生しました');
      setStreamStatus('error');
    } finally {
      setLoading(false);
      setStreamStatus((prev) => (prev === 'streaming' ? 'done' : prev));
    }
  }

  const isRAGActive = streamStatus !== 'idle';

  return (
    <div className="min-h-screen bg-gray-50">
      {/* Header */}
      <header className="bg-gradient-to-r from-indigo-900 via-indigo-800 to-indigo-700 text-white shadow-lg">
        <div className="max-w-5xl mx-auto px-4 py-6">
          <h1 className="text-2xl font-bold tracking-tight">VectorDB Benchmark</h1>
          <p className="text-indigo-300 text-sm mt-0.5">
            Qdrant vs pgvector — 検索パフォーマンス比較
          </p>
        </div>
      </header>

      <main className="max-w-5xl mx-auto px-4 py-8 space-y-5">
        {/* ── Search Form ── */}
        <div className="bg-white rounded-xl shadow-sm border border-gray-200 p-6">
          {/* Mode Tabs */}
          <div className="flex gap-1 mb-5 bg-gray-100 p-1 rounded-lg w-fit">
            {(['search', 'rag'] as Mode[]).map((m) => (
              <button
                key={m}
                type="button"
                onClick={() => { setMode(m); resetResults(); }}
                className={`px-4 py-1.5 text-sm font-medium rounded-md transition-colors ${
                  mode === m
                    ? 'bg-white text-indigo-700 shadow-sm'
                    : 'text-gray-500 hover:text-gray-700'
                }`}
              >
                {m === 'search' ? '検索モード' : 'RAGモード'}
              </button>
            ))}
          </div>

          <form onSubmit={handleSubmit} className="space-y-4">
            <div className="flex gap-3">
              <input
                type="text"
                value={query}
                onChange={(e) => setQuery(e.target.value)}
                placeholder={
                  mode === 'rag'
                    ? 'ベクトルDBの選び方を教えてください...'
                    : 'ベクトルデータベースの比較...'
                }
                className="flex-1 px-4 py-2.5 border border-gray-300 rounded-lg text-sm focus:outline-none focus:ring-2 focus:ring-indigo-400 focus:border-transparent"
              />
              <button
                type="submit"
                disabled={loading || streamStatus === 'streaming' || !query.trim()}
                className="px-6 py-2.5 bg-indigo-600 text-white text-sm font-semibold rounded-lg hover:bg-indigo-700 disabled:opacity-40 disabled:cursor-not-allowed transition-colors"
              >
                {loading || streamStatus === 'streaming' ? '処理中...' : '検索'}
              </button>
            </div>

            <div className="flex flex-wrap items-center gap-6 pt-1">
              <div className="flex items-center gap-4">
                <span className="text-sm font-medium text-gray-500">DB:</span>
                {(
                  [
                    { value: 'qdrant',   label: 'Qdrant',   color: 'text-orange-600' },
                    { value: 'pgvector', label: 'pgvector', color: 'text-blue-600'   },
                    { value: 'both',     label: '両方',     color: 'text-gray-700'   },
                  ] as { value: DB; label: string; color: string }[]
                ).map(({ value, label, color }) => (
                  <label key={value} className="flex items-center gap-1.5 cursor-pointer">
                    <input
                      type="radio"
                      name="db"
                      value={value}
                      checked={db === value}
                      onChange={() => setDb(value)}
                      className="accent-indigo-600"
                    />
                    <span className={`text-sm font-medium ${color}`}>{label}</span>
                  </label>
                ))}
              </div>
              <div className="flex items-center gap-2">
                <span className="text-sm font-medium text-gray-500">Top-K:</span>
                <input
                  type="number"
                  min={1}
                  max={20}
                  value={topK}
                  onChange={(e) => setTopK(Math.max(1, Number(e.target.value)))}
                  className="w-16 px-2 py-1.5 border border-gray-300 rounded-lg text-sm text-center focus:outline-none focus:ring-2 focus:ring-indigo-400"
                />
              </div>
            </div>
          </form>
        </div>

        {/* ── Error ── */}
        {error && (
          <div className="bg-red-50 border border-red-200 text-red-700 px-4 py-3 rounded-lg text-sm">
            エラー: {error}
          </div>
        )}

        {/* ── Search Mode: Spinner ── */}
        {loading && mode === 'search' && (
          <div className="flex flex-col items-center py-16 gap-3 text-gray-400">
            <div className="w-10 h-10 border-4 border-indigo-100 border-t-indigo-500 rounded-full animate-spin" />
            <p className="text-sm">検索中...</p>
          </div>
        )}

        {/* ── Search Mode: Latency Chart ── */}
        {!loading && searchResult && (
          <LatencyChart
            qdrant={searchResult.qdrant_latency_ms}
            pgvector={searchResult.pgvector_latency_ms}
          />
        )}

        {/* ── Search Mode: Results ── */}
        {!loading && searchResult && (
          <div className={`grid gap-4 ${db === 'both' ? 'grid-cols-1 md:grid-cols-2' : 'grid-cols-1'}`}>
            {searchResult.qdrant && (
              <div>
                <div className="flex items-center gap-2 mb-3">
                  <span className="w-2.5 h-2.5 rounded-full bg-orange-400" />
                  <span className="text-sm font-bold uppercase tracking-wide text-orange-600">Qdrant</span>
                  <span className="text-xs text-gray-400">{searchResult.qdrant.length}件</span>
                </div>
                <div className="space-y-2">
                  {searchResult.qdrant.map((item, i) => (
                    <ResultCard key={item.doc_id} item={item} rank={i + 1} />
                  ))}
                </div>
              </div>
            )}
            {searchResult.pgvector && (
              <div>
                <div className="flex items-center gap-2 mb-3">
                  <span className="w-2.5 h-2.5 rounded-full bg-blue-400" />
                  <span className="text-sm font-bold uppercase tracking-wide text-blue-600">pgvector</span>
                  <span className="text-xs text-gray-400">{searchResult.pgvector.length}件</span>
                </div>
                <div className="space-y-2">
                  {searchResult.pgvector.map((item, i) => (
                    <ResultCard key={item.doc_id} item={item} rank={i + 1} />
                  ))}
                </div>
              </div>
            )}
          </div>
        )}

        {/* ── RAG Mode: Step Panel ── */}
        {isRAGActive && (
          <StepPanel steps={streamSteps} status={streamStatus} />
        )}

        {/* ── RAG Mode: Streaming Answer ── */}
        {isRAGActive && (
          <StreamingAnswer text={streamAnswer} status={streamStatus} />
        )}

        {/* ── RAG Mode: Latency Chart (done後) ── */}
        {streamStatus === 'done' && ragResult && (
          <LatencyChart
            qdrant={ragResult.qdrant_latency_ms}
            pgvector={ragResult.pgvector_latency_ms}
          />
        )}

        {/* ── RAG Mode: Sources (done後) ── */}
        {streamStatus === 'done' && ragResult && ragResult.sources.length > 0 && (
          <div className="bg-white rounded-xl border border-gray-200 shadow-sm p-6">
            <div className="flex items-center justify-between mb-3">
              <h2 className="text-xs font-semibold text-gray-400 uppercase tracking-widest">
                参照ドキュメント{' '}
                <span className="normal-case font-normal">({ragResult.sources.length}件)</span>
              </h2>
              {ragResult.retry_count > 0 && (
                <span className="text-xs bg-yellow-50 text-yellow-600 border border-yellow-200 px-2 py-0.5 rounded-full">
                  クエリ再試行: {ragResult.retry_count}回
                </span>
              )}
            </div>
            <div className="space-y-2">
              {ragResult.sources.map((item, i) => (
                <ResultCard key={`${item.doc_id}-${i}`} item={item} rank={i + 1} />
              ))}
            </div>
          </div>
        )}
      </main>
    </div>
  );
}
