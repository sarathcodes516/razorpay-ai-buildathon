import React from 'react';
import { Menu, Search, Mic, User, Heart, ShoppingBag } from 'lucide-react';

interface NavbarProps {
  cartCount?: number;
  onCartClick?: () => void;
}

export default function Navbar({ cartCount = 0, onCartClick }: NavbarProps) {
  return (
    <nav className="sticky top-0 z-40 w-full bg-white border-b border-gray-200 shadow-sm">
      <div className="flex items-center justify-between px-6 h-16 max-w-screen-2xl mx-auto">
        <div className="flex items-center gap-6">
          <Menu className="w-5 h-5 text-gray-700 cursor-pointer" />
          <div className="hidden md:flex items-center gap-6 text-sm font-bold tracking-wide">
            <span className="text-red-600 border-b-2 border-red-600 pb-5 pt-5 cursor-pointer">MEN</span>
            <span className="text-gray-600 hover:text-black pb-5 pt-5 cursor-pointer">WOMEN</span>
            <span className="text-gray-600 hover:text-black pb-5 pt-5 cursor-pointer">SNEAKERS</span>
          </div>
        </div>
        <div className="flex-shrink-0 cursor-pointer">
          <img src="/logo.png" alt="The Souled Stole" className="h-12 object-contain" />
        </div>
        <div className="flex items-center gap-5">
          <div className="hidden lg:flex items-center bg-gray-100 rounded-full px-4 py-1.5 w-72">
            <input type="text" placeholder="What are you looking for?" className="w-full text-sm bg-transparent outline-none text-gray-700" />
            <Mic className="w-4 h-4 text-gray-400 mx-2 cursor-pointer" />
            <Search className="w-4 h-4 text-gray-400 cursor-pointer" />
          </div>
          <User className="w-5 h-5 text-gray-700 cursor-pointer hover:text-black" />
          <Heart className="w-5 h-5 text-gray-700 cursor-pointer hover:text-black" />
          <button onClick={onCartClick} className="relative p-1 text-gray-700 hover:text-red-600 transition-colors">
            <ShoppingBag className="w-5 h-5" />
            {cartCount > 0 && (
              <span className="absolute -top-1 -right-1 bg-red-600 text-white text-[10px] font-bold w-4 h-4 rounded-full flex items-center justify-center">
                {cartCount}
              </span>
            )}
          </button>
        </div>
      </div>
    </nav>
  );
}
