import React from 'react';
import { TrendingDown, ExternalLink } from 'lucide-react';

const platformColors = {
  Amazon: 'from-orange-500 to-yellow-500',
  Flipkart: 'from-blue-500 to-blue-600',
  eBay: 'from-red-500 to-pink-500',
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

  const bestPrice = Math.min(...products.map((product) => parsePriceValue(product.price)));
  const maxPrice = Math.max(...products.map((product) => parsePriceValue(product.price)).filter(Number.isFinite));
  const savings = Number.isFinite(bestPrice) && Number.isFinite(maxPrice) ? Math.max(0, maxPrice - bestPrice) : 0;

  return (
    <div className="bg-white rounded-xl border border-gray-200 overflow-hidden shadow-lg">
      <div className="bg-gradient-to-r from-orange-500 to-orange-600 text-white px-4 py-3">
        <h3 className="font-semibold text-sm flex items-center gap-2">
          <TrendingDown className="w-4 h-4" />
          Cross-Platform Comparison
        </h3>
      </div>

      <div className="divide-y divide-gray-200">
        {products.map((product, index) => {
          const priceValue = parsePriceValue(product.price);
          const isBest = Number.isFinite(priceValue) && priceValue === bestPrice;
          const color = platformColors[product.platform] || platformColors.default;

          return (
            <div
              key={`${product.platform || 'platform'}-${index}`}
              className={`p-4 hover:bg-gray-50 transition-colors ${isBest ? 'bg-green-50' : ''}`}
            >
              <div className="flex items-center justify-between gap-3">
                <div className="flex items-center gap-3 min-w-0">
                  <div className={`w-2 h-2 rounded-full bg-gradient-to-r ${color}`}></div>
                  <div className="min-w-0">
                    <div className="font-semibold text-gray-800">{product.platform || 'Platform'}</div>
                    <div className="text-xs text-gray-500 truncate">
                      {product.rating_text || (product.rating ? `Rating: ${product.rating}/5` : 'Rating not found')}
                      {product.reviewCount ? ` • ${product.reviewCount}` : ''}
                    </div>
                  </div>
                </div>

                <div className="flex items-center gap-3">
                  <div className="text-right">
                    <div className="text-lg font-bold text-gray-800">{product.price || 'Price not found'}</div>
                    {isBest && (
                      <div className="text-xs text-green-600 font-semibold">Best Price</div>
                    )}
                  </div>
                  {product.url && (
                    <button
                      onClick={() => window.open(product.url, '_blank')}
                      className="p-2 hover:bg-gray-200 rounded-lg transition-colors"
                      title="View on platform"
                    >
                      <ExternalLink className="w-4 h-4 text-gray-600" />
                    </button>
                  )}
                </div>
              </div>
            </div>
          );
        })}
      </div>

      <div className="bg-gray-50 px-4 py-2 text-xs text-gray-500 text-center">
        {savings > 0 ? `Potential savings: ${savings.toFixed(2)}` : 'Comparison is based on the latest product search results.'}
      </div>
    </div>
  );
};

export default ComparisonTable;
