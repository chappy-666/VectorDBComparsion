import { NextRequest } from 'next/server';

const BACKEND = process.env.BACKEND_URL ?? 'http://backend:8000';

export async function POST(req: NextRequest) {
  try {
    const body = await req.json();
    const backendRes = await fetch(`${BACKEND}/rag`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(body),
    });

    return new Response(backendRes.body, {
      status: backendRes.status,
      headers: {
        'Content-Type': 'text/event-stream',
        'Cache-Control': 'no-cache',
        'Connection': 'keep-alive',
        'X-Accel-Buffering': 'no',
      },
    });
  } catch {
    return new Response(
      'event: error\ndata: {"message":"バックエンドへの接続に失敗しました"}\n\n',
      { status: 502, headers: { 'Content-Type': 'text/event-stream' } },
    );
  }
}
