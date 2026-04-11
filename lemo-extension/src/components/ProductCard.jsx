import React from 'react';
import { ExternalLink, Star } from 'lucide-react';

const ProductCard = ({ title, price, platform, rating, imageUrl, link }) => {
  return (
    <div className="bg-gradient-to-br from-white to-orange-50 rounded-xl overflow-hidden border border-orange-200 shadow-md hover:shadow-xl transition-all transform hover:-translate-y-1 cursor-pointer">
      {/* Product Image */}
      <div className="relative h-40 bg-gray-100 overflow-hidden">
        <img
          src={imageUrl}
          alt={title}
          className="w-full h-full object-cover"
        />
        <div className="absolute top-2 right-2 bg-white/90 backdrop-blur-sm px-2 py-1 rounded-lg text-xs font-semibold text-orange-600">
          {platform}
        </div>
      </div>

      {/* Product Info */}
      <div className="p-4">
        <h4 className="font-semibold text-gray-800 mb-2 line-clamp-2">{title}</h4>
        
        {/* Rating */}
        <div className="flex items-center gap-1 mb-2">
          {[...Array(5)].map((_, i) => (
            <Star
              key={i}
              className={`w-4 h-4 ${
                i < Math.floor(rating)
                  ? 'fill-yellow-400 text-yellow-400'
                  : 'text-gray-300'
              }`}
            />
          ))}
          <span className="text-sm text-gray-600 ml-1">{rating}</span>
        </div>

        {/* Price & Link */}
        <div className="flex items-center justify-between">
          <span className="text-2xl font-bold bg-gradient-to-r from-orange-600 to-orange-700 bg-clip-text text-transparent">
            {price}
          </span>
          <button
            onClick={() => window.open(link, '_blank')}
            className="flex items-center gap-1 px-3 py-1.5 bg-gradient-to-r from-[#FF7A00] to-[#E76500] text-white rounded-lg text-sm font-medium hover:shadow-lg transition-all transform hover:scale-105"
          >
            View
            <ExternalLink className="w-3 h-3" />
          </button>
        </div>
      </div>
    </div>
  );
};

export default ProductCard;