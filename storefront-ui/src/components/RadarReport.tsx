import type { Product, RadarReport as RadarReportType } from '../types/api'

function formatMoney(product: Product): string {
  const currency = product.currency ?? 'USD'
  const price = Number(product.price ?? 0)
  return `${currency} $${price.toFixed(price % 1 === 0 ? 0 : 2)}`
}

interface Props {
  radar: RadarReportType
}

export function RadarReport({ radar }: Props) {
  if (!radar?.reportId) return null

  return (
    <section className="radar-report">
      <div className="radar-header">
        <h3>Campus Demand Radar</h3>
        <span>{radar.reportId}</span>
      </div>
      <p className="radar-summary">
        This scan combines public campus signals, weather, recent shopper intent, and live Shopify products to tell the store what to feature this week.
      </p>

      <div className="signal-grid">
        {(radar.sourceSummary ?? []).map((source) => (
          <div key={source.name} className="signal">
            <strong>{source.name}</strong>
            <span>{source.status}</span>
          </div>
        ))}
      </div>

      {(radar.featuredProducts?.length ?? 0) > 0 && (
        <>
          <p className="radar-subhead">Products to feature now</p>
          <div className="radar-products">
            {radar.featuredProducts!.slice(0, 3).map((product) => (
              <div key={product.sku} className="radar-product">
                <strong>{product.name}</strong>
                <span>{formatMoney(product)}</span>
              </div>
            ))}
          </div>
        </>
      )}

      <p className="radar-subhead">Merchant actions</p>
      <ol className="radar-actions">
        {(radar.actions ?? []).map((action, i) => (
          <li key={i}>{action}</li>
        ))}
      </ol>

      {radar.kestra && (
        <div className="automation-status">
          <strong>
            {radar.kestra.status === 'triggered' ? 'Kestra radar workflow started' : 'Kestra radar workflow ready'}
          </strong>
          <span>
            {radar.kestra.executionId
              ? `Execution ${radar.kestra.executionId}`
              : 'Start Kestra locally to execute the scheduled version of this scan.'}
          </span>
        </div>
      )}
    </section>
  )
}
