import type { ChatResponse } from '../types/api'

const API_BASE = import.meta.env.VITE_API_GATEWAY_URL ?? ''

export async function sendChatMessage(
  message: string,
  sessionId: string,
  extra: Partial<{ selectedSku: string; products: unknown[]; cart: unknown[]; order: unknown; automation: unknown; radar: unknown }> = {}
): Promise<ChatResponse> {
  const response = await fetch(`${API_BASE}/api/chat`, {
    method: 'POST',
    headers: { 'content-type': 'application/json' },
    body: JSON.stringify({ message, sessionId, ...extra }),
  })
  if (!response.ok) {
    const err = await response.json().catch(() => ({}))
    throw new Error((err as { error?: string }).error ?? 'Chat request failed')
  }
  return response.json() as Promise<ChatResponse>
}
