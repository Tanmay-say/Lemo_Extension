import React from 'react';
import { TrendingDown, ExternalLink } from 'lucide-react';

const ComparisonTable = () => {
  const products = [
    {
      platform: 'Amazon',
      price: 129.99,
      rating: 4.5,
      link: '#',
      color: 'from-orange-500 to-yellow-500',
    },
    {
      platform: 'Flipkart',
      price: 124.99,
      rating: 4.3,
      link: '#',
      color: 'from-blue-500 to-blue-600',
      isBest: true,
    },
    {
      platform: 'eBay',
      price: 134.99,
      rating: 4.4,
      link: '#',
      color: 'from-red-500 to-pink-500',
    },
  ];

  const bestPrice = Math.min(...products.map((p) => p.price));

  return (
    <div className="bg-white rounded-xl border border-gray-200 overflow-hidden shadow-lg">
      <div className="bg-gradient-to-r from-orange-500 to-orange-600 text-white px-4 py-3">
        <h3 className="font-semibold text-sm flex items-center gap-2">
          <TrendingDown className="w-4 h-4" />
          Price Comparison
        </h3>
      </div>

      <div className="divide-y divide-gray-200">
        {products.map((product, index) => (
          <div
            key={index}
            className={`p-4 hover:bg-gray-50 transition-colors ${
              product.price === bestPrice ? 'bg-green-50' : ''
            }`}
          >
            <div className="flex items-center justify-between">
              <div className="flex items-center gap-3">
                <div className={`w-2 h-2 rounded-full bg-gradient-to-r ${product.color}`}></div>
                <div>
                  <div className="font-semibold text-gray-800">{product.platform}</div>
                  <div className="text-xs text-gray-500">Rating: {product.rating}/5</div>
                </div>
              </div>
              
              <div className="flex items-center gap-3">
                <div className="text-right">
                  <div className="text-lg font-bold text-gray-800">${product.price}</div>
                  {product.price === bestPrice && (
                    <div className="text-xs text-green-600 font-semibold">Best Price</div>
                  )}
                </div>
                <button
                  onClick={() => window.open(product.link, '_blank')}
                  className="p-2 hover:bg-gray-200 rounded-lg transition-colors"
                  title="View on platform"
                >
                  <ExternalLink className="w-4 h-4 text-gray-600" />
                </button>
              </div>
            </div>
          </div>
        ))}
      </div>

      <div className="bg-gray-50 px-4 py-2 text-xs text-gray-500 text-center">
        💡 Save ${Math.max(...products.map(p => p.price)) - bestPrice} by choosing the best option
      </div>
    </div>
  );
};

export default ComparisonTable;