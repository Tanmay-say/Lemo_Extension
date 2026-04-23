import React from 'react';
import { BadgeIndianRupee, ExternalLink, TrendingDown } from 'lucide-react';

const platformColors = {
  Amazon: 'from-orange-500 to-yellow-500',
  Flipkart: 'from-blue-500 to-blue-600',
  eBay: 'from-red-500 to-pink-500',
  Walmart: 'from-sky-500 to-blue-600',
  Meesho: 'from-pink-500 to-rose-500',
  default: 'from-gray-500 to-gray-600',
};

const parsePriceValue = (price) => {
  if (typeof price === 'number') {
    return price;
  }
  const numeric = parseFloat(String(price || '').replace(/[^\d.]/g, ''));
  return Number.isFinite(numeric) ? numeric : Number.POSITIVE_INFINITY;
};

const ComparisonTable = ({ comparisonData }) => {
  const products = comparisonData?.products || [];

  if (!products.length) {
    return null;
  }

  const priceValues = products
    .map((product) => parsePriceValue(product.price))
    .filter(Number.isFinite);
  const bestPrice = priceValues.length ? Math.min(...priceValues) : Number.POSITIVE_INFINITY;
  const maxPrice = priceValues.length ? Math.max(...priceValues) : Number.POSITIVE_INFINITY;
  const savings = Number.isFinite(bestPrice) && Number.isFinite(maxPrice) ? Math.max(0, maxPrice - bestPrice) : 0;

  return (
    <div className="overflow-hidden rounded-2xl border border-orange-100 bg-white shadow-[0_16px_40px_rgba(249,115,22,0.12)]">
      <div className="bg-gradient-to-r from-orange-500 via-amber-500 to-orange-600 px-4 py-3 text-white">
        <h3 className="flex items-center gap-2 text-sm font-semibold">
          <TrendingDown className="h-4 w-4" />
          Cross-Platform Comparison
        </h3>
      </div>

      <div className="divide-y divide-orange-100">
        {products.map((product, index) => {
          const priceValue = parsePriceValue(product.price);
          const isBest = Number.isFinite(priceValue) && priceValue === bestPrice;
          const color = platformColors[product.platform] || platformColors.default;

          return (
            <div
              key={`${product.platform || 'platform'}-${index}`}
              className={`p-4 transition-colors hover:bg-orange-50/40 ${isBest ? 'bg-emerald-50' : ''}`}
            >
              <div className="flex items-start justify-between gap-3">
                <div className="min-w-0 flex items-start gap-3">
                  <div className={`mt-1 h-2.5 w-2.5 rounded-full bg-gradient-to-r ${color}`}></div>
                  <div className="min-w-0">
                    <div className="font-semibold text-gray-800">{product.platform || 'Platform'}</div>
                    <div className="mt-1 text-xs text-gray-500">
                      {product.title || 'Matched product'}
                    </div>
                    <div className="mt-1 text-xs text-gray-500">
                      {product.rating_text || (product.rating ? `Rating: ${product.rating}/5` : 'Rating not found')}
                      {product.reviewCount ? ` • ${product.reviewCount}` : ''}
                    </div>
                  </div>
                </div>

                <div className="flex items-center gap-3">
                  <div className="text-right">
                    <div className="flex items-center justify-end gap-1 text-lg font-bold text-gray-800">
                      <BadgeIndianRupee className="h-4 w-4 text-orange-500" />
                      <span>{product.price || 'Price not found'}</span>
                    </div>
                    {isBest && <div className="text-xs font-semibold text-green-600">Best Price</div>}
                  </div>
                  {product.url && (
                    <button
                      onClick={() => window.open(product.url, '_blank')}
                      className="rounded-lg p-2 transition-colors hover:bg-orange-100"
                      title="View on platform"
                    >
                      <ExternalLink className="h-4 w-4 text-gray-600" />
                    </button>
                  )}
                </div>
              </div>
            </div>
          );
        })}
      </div>

      <div className="bg-orange-50/60 px-4 py-2 text-center text-xs text-gray-600">
        {savings > 0 ? `Potential savings: ${savings.toFixed(2)}` : 'Comparison is based on the latest product search results.'}
      </div>
    </div>
  );
};

export default ComparisonTable;
