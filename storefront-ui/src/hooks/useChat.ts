import { useState, useCallback } from 'react'
import { sendChatMessage } from '../api/chatClient'
import type { Message } from '../types/api'

export function useChat(sessionId: string) {
  const [messages, setMessages] = useState<Message[]>([
    {
      id: crypto.randomUUID(),
      role: 'agent',
      text: "Hi! I'm Storefront Concierge. I can search a live Shopify catalog, build a cart, and run a Campus Demand Radar. Try one of the prompts below to start.",
      meta: { reply: '', trace: ['agent.ready', 'shopify.mcp.live', 'kestra.radar.ready'] },
    },
  ])
  const [loading, setLoading] = useState(false)

  const sendMessage = useCallback(
    async (text: string, extra?: { selectedSku?: string }) => {
      setMessages((prev) => [...prev, { id: crypto.randomUUID(), role: 'user', text }])
      setLoading(true)
      try {
        const result = await sendChatMessage(text, sessionId, extra)
        setMessages((prev) => [...prev, { id: crypto.randomUUID(), role: 'agent', text: result.reply, meta: result }])
      } catch (err) {
        const msg = err instanceof Error ? err.message : 'An error occurred'
        setMessages((prev) => [...prev, { id: crypto.randomUUID(), role: 'agent', text: `I hit an execution error: ${msg}` }])
      } finally {
        setLoading(false)
      }
    },
    [sessionId]
  )

  const clearMessages = useCallback(() => {
    setMessages([
      {
        id: crypto.randomUUID(),
        role: 'agent',
        text: 'Fresh session started. Tell me who you are shopping for, the occasion, size, budget, or pickup timing — or ask me to run a campus demand scan.',
        meta: { reply: '', trace: ['session.reset'] },
      },
    ])
  }, [])

  return { messages, loading, sendMessage, clearMessages }
}
