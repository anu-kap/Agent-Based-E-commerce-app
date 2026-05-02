import { useRef, useEffect, type FormEvent } from 'react'
import type { Message, Product } from '../types/api'
import { ProductGrid } from './ProductGrid'
import { CheckoutLink } from './CheckoutLink'
import { AutomationStatus } from './AutomationStatus'
import { RadarReport } from './RadarReport'
import { AgentTrace } from './AgentTrace'

const SUGGESTIONS = [
  'Find a hoodie for an alum',
  'Find a mug',
  'Run campus opportunity scan',
  'Add the best option to my cart',
  'Checkout in Shopify',
  'Simulate order paid',
]

interface Props {
  messages: Message[]
  loading: boolean
  onSend: (text: string, extra?: { selectedSku?: string }) => void
  onReset: () => void
}

function MessageBubble({ message, onSend }: { message: Message; onSend: Props['onSend'] }) {
  const { role, text, meta } = message
  const trace = meta?.trace ?? []
  const showProducts = role === 'agent' && trace.includes('catalog-service.search') || trace.includes('mcp.search_catalog')
  const showCheckout = role === 'agent' && meta?.order && !trace.includes('kestra.post_order_workflow')
  const showAutomation = role === 'agent' && !!meta?.automation?.kestra
  const showRadar = role === 'agent' && !!meta?.radar?.reportId

  return (
    <article className={`message ${role}`}>
      <span style={{ whiteSpace: 'pre-wrap' }}>{text}</span>
      {showProducts && meta?.products && (
        <ProductGrid
          products={meta.products}
          onAdd={(product: Product) => onSend(`Add ${product.name} to my cart`, { selectedSku: product.sku })}
        />
      )}
      {showCheckout && meta?.order && (
        <CheckoutLink order={meta.order} onSimulate={() => onSend('Simulate Shopify order paid webhook')} />
      )}
      {showAutomation && meta?.automation && <AutomationStatus automation={meta.automation} />}
      {showRadar && meta?.radar && <RadarReport radar={meta.radar} />}
      <AgentTrace trace={trace} />
    </article>
  )
}

export function ChatPanel({ messages, loading, onSend, onReset }: Props) {
  const messagesRef = useRef<HTMLDivElement>(null)
  const inputRef = useRef<HTMLInputElement>(null)

  useEffect(() => {
    if (messagesRef.current) {
      messagesRef.current.scrollTop = messagesRef.current.scrollHeight
    }
  }, [messages])

  function handleSubmit(e: FormEvent<HTMLFormElement>) {
    e.preventDefault()
    const text = inputRef.current?.value.trim()
    if (text) {
      onSend(text)
      if (inputRef.current) inputRef.current.value = ''
    }
  }

  return (
    <section className="chat-panel">
      <header className="chat-header">
        <div>
          <p className="eyebrow">Live Demo</p>
          <h2>The Kohawk Shop concierge</h2>
        </div>
        <button type="button" onClick={onReset} title="Reset conversation">
          Reset
        </button>
      </header>

      <div id="messages" className="messages" aria-live="polite" ref={messagesRef}>
        {messages.map((msg) => (
          <MessageBubble key={msg.id} message={msg} onSend={onSend} />
        ))}
        {loading && (
          <article className="message agent">
            <span>Thinking…</span>
          </article>
        )}
      </div>

      <form className="composer" onSubmit={handleSubmit}>
        <input
          ref={inputRef}
          name="message"
          type="text"
          autoComplete="off"
          placeholder="Ask for campus gear, alumni gifts, pickup needs..."
          disabled={loading}
          required
        />
        <button type="submit" disabled={loading}>
          Send
        </button>
      </form>

      <div className="suggestions" aria-label="Example prompts">
        {SUGGESTIONS.map((s) => (
          <button key={s} type="button" onClick={() => onSend(s)}>
            {s}
          </button>
        ))}
      </div>
    </section>
  )
}
