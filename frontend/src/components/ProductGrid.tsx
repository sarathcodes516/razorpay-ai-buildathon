import React from 'react';

const mockImages = [
  "https://images.unsplash.com/photo-1583743814966-8936f5b7be1a?auto=format&fit=crop&q=80&w=600",
  "https://images.unsplash.com/photo-1556821840-3a63f95609a7?auto=format&fit=crop&q=80&w=600",
  "https://images.unsplash.com/photo-1523381294911-8d3cead13475?auto=format&fit=crop&q=80&w=600",
  "https://images.unsplash.com/photo-1618354691373-d851c5c3a990?auto=format&fit=crop&q=80&w=600"
];

export default function ProductGrid({ catalog }: { catalog: any[] }) {
  return (
    <div className="max-w-screen-xl mx-auto px-6 py-10">
      <h2 className="text-center text-xl font-black tracking-widest text-gray-900 mb-8 uppercase">New Arrivals</h2>
      <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-4 gap-6">
        {catalog.map((item, idx) => (
          <div key={item.sku} className="group cursor-pointer">
            <div className="relative aspect-[3/4] bg-gray-100 overflow-hidden mb-3 rounded-md">
              <img src={mockImages[idx % 4]} alt={item.name} className="object-cover w-full h-full group-hover:scale-105 transition-transform duration-500" />
              <div className="absolute top-2 left-2 bg-black/80 text-white text-[10px] font-bold px-2 py-1 uppercase">Oversized Fit</div>
            </div>
            <h3 className="text-sm font-semibold text-gray-900 truncate">{item.name}</h3>
            <p className="text-xs text-gray-500 mb-1 capitalize">{item.category}</p>
            <p className="text-sm font-bold text-gray-900">₹ {item.price}</p>
          </div>
        ))}
      </div>
    </div>
  );
}
