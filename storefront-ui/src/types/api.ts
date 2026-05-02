export interface Product {
  sku: string
  name: string
  category?: string
  price: number
  currency?: string
  inventory?: number | string
  rating?: number | string
  tags?: string[]
  description?: string
  url?: string
  imageUrl?: string
  source?: string
}

export interface CartLine {
  sku: string
  name: string
  quantity: number
  unitPrice: number
  lineTotal: number
}

export interface CartQuote {
  source?: string
  lines?: CartLine[]
  subtotal?: number
  shipping?: number
  tax?: number
  total: number
  checkoutUrl?: string
  cart?: Record<string, unknown>
}

export interface Order {
  orderId: string
  status: string
  shippingMethod?: string
  quote: CartQuote
  kestraWorkflow?: string
}

export interface KestraResult {
  status: string
  executionId?: string
  url?: string
  reason?: string
  workflowEvent?: string
  flowId?: string
}

export interface Automation {
  orderId: string
  status: string
  source?: string
  total?: number
  kestraWorkflow?: string
  kestra?: KestraResult
}

export interface SignalSource {
  name: string
  status?: string
  url?: string
}

export interface RadarSignals {
  events?: Record<string, unknown>
  weather?: Record<string, unknown>
  intent?: Record<string, unknown>
}

export interface RadarReport {
  reportId: string
  focus?: string
  generatedAt?: string
  signals?: RadarSignals
  actions?: string[]
  featuredProducts?: Product[]
  sourceSummary?: SignalSource[]
  kestraWorkflow?: string
  kestra?: KestraResult
}

export interface ChatResponse {
  reply: string
  trace?: string[]
  products?: Product[]
  cart?: Array<{ sku: string; quantity: number }>
  order?: Order
  automation?: Automation
  radar?: RadarReport
}

export interface Message {
  id: string
  role: 'user' | 'agent'
  text: string
  meta?: ChatResponse
}
