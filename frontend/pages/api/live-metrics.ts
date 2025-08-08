import type { NextApiRequest, NextApiResponse } from 'next';

export default async function handler(req: NextApiRequest, res: NextApiResponse) {
  const base = process.env.NEXT_PUBLIC_BACKEND_HTTP || 'http://localhost:5001';
  try {
    const r = await fetch(`${base}/metrics`, { headers: { 'accept': 'application/json' } });
    if (!r.ok) {
      return res.status(r.status).json({ error: `Backend responded ${r.status}` });
    }
    const data = await r.json();
    return res.status(200).json(data);
  } catch (e: any) {
    return res.status(503).json({ error: 'Metrics backend unavailable' });
  }
} 