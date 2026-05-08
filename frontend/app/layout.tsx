import type { Metadata } from 'next';
import './globals.css';

export const metadata: Metadata = {
  title: 'VectorDB Benchmark',
  description: 'Qdrant vs pgvector パフォーマンス比較',
};

export default function RootLayout({ children }: { children: React.ReactNode }) {
  return (
    <html lang="ja">
      <body className="antialiased">{children}</body>
    </html>
  );
}
