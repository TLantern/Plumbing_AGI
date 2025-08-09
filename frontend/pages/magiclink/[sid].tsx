import { useEffect, useState } from 'react'
import { useRouter } from 'next/router'
import { useIsMounted } from '@/hooks/useIsMounted'

const PHONE_API = process.env.NEXT_PUBLIC_PHONE_API_URL || 'http://localhost:5001'
const OP_API_KEY = process.env.NEXT_PUBLIC_MAGICLINK_OPERATOR_KEY || ''

export default function OperatorMagiclink() {
  const mounted = useIsMounted()
  const router = useRouter()
  const { sid } = router.query as { sid?: string }
  const [status, setStatus] = useState<any>(null)
  const [loading, setLoading] = useState<boolean>(false)

  async function refresh() {
    if (!sid) return
    try {
      const r = await fetch(`${PHONE_API}/magiclink/status/${sid}`)
      const j = await r.json()
      setStatus(j)
    } catch (e) {
      setStatus({ error: 'failed to load' })
    }
  }

  async function confirm() {
    if (!sid) return
    setLoading(true)
    try {
      const r = await fetch(`${PHONE_API}/magiclink/operator/confirm/${sid}`, {
        method: 'POST',
        headers: OP_API_KEY ? { 'x-api-key': OP_API_KEY } : undefined,
      })
      await refresh()
    } finally {
      setLoading(false)
    }
  }

  useEffect(() => {
    if (!mounted) return
    const id = setInterval(refresh, 2000)
    refresh()
    return () => clearInterval(id)
  }, [sid, mounted])

  if (!mounted) return null

  return (
    <div style={{ maxWidth: 720, margin: '2rem auto', fontFamily: 'system-ui' }}>
      <h1>Location Confirmation</h1>
      <p>Call SID: {sid}</p>
      <pre>{status ? JSON.stringify(status, null, 2) : 'Loading...'}</pre>
      <button disabled={loading} onClick={confirm} style={{ padding: '8px 16px' }}>
        {loading ? 'Confirming...' : 'Confirm Location'}
      </button>
      <p style={{ marginTop: 12 }}>This marks dispatcher confirmation. Booking finalizes once the caller has shared location.</p>
    </div>
  )
} 