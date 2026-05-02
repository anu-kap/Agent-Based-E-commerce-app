import type { Order } from '../types/api'

interface Props {
  order: Order
  onSimulate: () => void
}

export function CheckoutLink({ order, onSimulate }: Props) {
  const checkoutUrl = order?.quote?.checkoutUrl
  if (!checkoutUrl) return null
  return (
    <div className="post-cart-actions">
      <a className="checkout-link" href={checkoutUrl} target="_blank" rel="noreferrer">
        Open Shopify checkout
      </a>
      <button type="button" className="simulate-order" title="Trigger Kestra post-order automation" onClick={onSimulate}>
        Simulate order paid
      </button>
    </div>
  )
}
