import { useEffect, useState } from 'react'
import { useIsMounted } from '@/hooks/useIsMounted'

const MAGICLINK_API = process.env.NEXT_PUBLIC_MAGICLINK_API_URL || 'http://localhost:8000'

function extractTokenFromUrl(): string | null {
  try {
    const { search, hash } = window.location
    const qs = new URLSearchParams(search)
    const qToken = qs.get('token') || qs.get('t')
    if (qToken) return qToken
    if (hash && hash.startsWith('#')) {
      const hs = new URLSearchParams(hash.slice(1))
      const hToken = hs.get('token') || hs.get('t')
      if (hToken) return hToken
    }
  } catch (_) {}
  return null
}

export default function LocationPage() {
  const mounted = useIsMounted()
  const [status, setStatus] = useState<string>('Ready')
  const [sid, setSid] = useState<string>('')

  useEffect(() => {
    if (!mounted) return
    const token = extractTokenFromUrl()
    if (!token) {
      setStatus('Missing token')
      return
    }
    async function run() {
      try {
        setStatus('Validating token...')
        const introspect = await fetch(`${MAGICLINK_API}/introspect`, {
          method: 'POST',
          headers: { Authorization: `Bearer ${token}` },
        })
        if (!introspect.ok) {
          setStatus('Token invalid or expired')
          return
        }
        const data = await introspect.json()
        const sidVal = data.sid as string
        setSid(sidVal)
        setStatus('Requesting location...')
        navigator.geolocation.getCurrentPosition(
          async (pos) => {
            try {
              const payload = {
                lat: pos.coords.latitude,
                lng: pos.coords.longitude,
                accuracy: pos.coords.accuracy,
                timestamp: Date.now(),
                user_agent: navigator.userAgent,
              }
              const res = await fetch(`${MAGICLINK_API}/calls/${sidVal}/location`, {
                method: 'POST',
                headers: {
                  'Content-Type': 'application/json',
                  Authorization: `Bearer ${token}`,
                },
                body: JSON.stringify(payload),
              })
              const body = await res.json().catch(() => ({}))
              if (res.ok) {
                setStatus('Location shared. You can return to the call.')
              } else if (res.status === 409) {
                setStatus('Link already used. If you already shared, you are all set.')
              } else if (res.status === 401) {
                setStatus('Token expired. Ask for a new link.')
              } else {
                setStatus(`Error: ${body?.reason || 'unknown'}`)
              }
            } catch (e) {
              setStatus('Failed to send location')
            }
          },
          async (err) => {
            try {
              const res = await fetch(`${MAGICLINK_API}/calls/${sidVal}/location`, {
                method: 'POST',
                headers: { 'Content-Type': 'application/json', Authorization: `Bearer ${token}` },
                body: JSON.stringify({ denied: true, user_agent: navigator.userAgent }),
              })
              if (res.ok) setStatus('Location denied. Dispatcher will proceed without it.')
              else setStatus('Failed to report denial')
            } catch (e) {
              setStatus('Failed to report denial')
            }
          },
          { enableHighAccuracy: true, timeout: 15000 }
        )
      } catch (e) {
        setStatus('Unexpected error')
      }
    }
    run()
  }, [mounted])

  if (!mounted) return null

  return (
    <div style={{ maxWidth: 520, margin: '3rem auto', fontFamily: 'system-ui' }}>
      <h1>Share Location</h1>
      <p>Call: {sid || '-'}</p>
      <p>Status: {status}</p>
    </div>
  )
} 