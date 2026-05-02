import { useState } from 'react'

export function useSession() {
  const [sessionId, setSessionId] = useState(() => crypto.randomUUID())

  function resetSession() {
    setSessionId(crypto.randomUUID())
  }

  return { sessionId, resetSession }
}
