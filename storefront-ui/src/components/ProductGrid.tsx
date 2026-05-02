import type { Product } from '../types/api'
import { ProductCard } from './ProductCard'

interface Props {
  products: Product[]
  onAdd: (product: Product) => void
  limit?: number
}

export function ProductGrid({ products, onAdd, limit = 4 }: Props) {
  const usable = products.filter((p) => p?.sku && p?.name && p?.price !== undefined).slice(0, limit)
  if (!usable.length) return null
  return (
    <div className="product-grid">
      {usable.map((p) => (
        <ProductCard key={p.sku} product={p} onAdd={onAdd} />
      ))}
    </div>
  )
}
