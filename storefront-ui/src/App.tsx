import { useSession } from './hooks/useSession'
import { useChat } from './hooks/useChat'
import { ChatPanel } from './components/ChatPanel'
import './styles/globals.css'

export function App() {
  const { sessionId, resetSession } = useSession()
  const { messages, loading, sendMessage, clearMessages } = useChat(sessionId)

  function handleReset() {
    resetSession()
    clearMessages()
  }

  return (
    <main className="shell">
      <section className="workspace" aria-label="Storefront Concierge workspace">
        <aside className="rail" aria-label="System status">
          <div>
            <p className="eyebrow">Storefront Concierge</p>
            <h1>Chat your Shopify catalog into a cart.</h1>
            <p className="rail-subtitle">
              Showcase store: <strong>The Kohawk Shop</strong> &mdash; Coe College
            </p>
          </div>
          <div className="stack">
            <div className="status">
              <span className="dot"></span>
              <span>Live Shopify Storefront MCP catalog &amp; cart</span>
            </div>
            <div className="status">
              <span className="dot"></span>
              <span>LangGraph agent with deterministic fallback</span>
            </div>
            <div className="status">
              <span className="dot muted"></span>
              <span>Campus Demand Radar &rarr; Kestra workflow</span>
            </div>
          </div>
          <div className="metrics">
            <div>
              <strong>Live</strong>
              <span>Shopify</span>
            </div>
            <div>
              <strong>Cart</strong>
              <span>Ready</span>
            </div>
            <div>
              <strong>Ops</strong>
              <span>Kestra</span>
            </div>
          </div>
        </aside>

        <ChatPanel messages={messages} loading={loading} onSend={sendMessage} onReset={handleReset} />
      </section>
    </main>
  )
}
