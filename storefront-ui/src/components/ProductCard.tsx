import type { Product } from '../types/api'

function formatMoney(product: Product): string {
  const currency = product.currency ?? 'USD'
  const price = Number(product.price ?? 0)
  return `${currency} $${price.toFixed(price % 1 === 0 ? 0 : 2)}`
}

interface Props {
  product: Product
  onAdd: (product: Product) => void
}

export function ProductCard({ product, onAdd }: Props) {
  return (
    <article className="product-card">
      {product.imageUrl && <img src={product.imageUrl} alt={product.name} loading="lazy" />}
      <div className="product-body">
        <h3>{product.name}</h3>
        <p className="product-meta">
          {product.inventory === 'available' ? 'Available now' : 'Campus store item'}
        </p>
        <p className="product-price">{formatMoney(product)}</p>
        {product.description && (
          <p className="product-description">{product.description.replace(/<[^>]*>/g, '')}</p>
        )}
        <div className="product-actions">
          <button type="button" title={`Add ${product.name} to cart`} onClick={() => onAdd(product)}>
            Add
          </button>
          {product.url && (
            <a href={product.url} target="_blank" rel="noreferrer">
              View
            </a>
          )}
        </div>
      </div>
    </article>
  )
}
