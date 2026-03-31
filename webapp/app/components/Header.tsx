// components/Header.tsx
import React, { memo } from 'react';
import Link from 'next/link';

const Header = () => {
  return (
    <header className="bg-red-800 text-white w-full">
      <div className="flex flex-row justify-between items-center gap-2 px-2 py-1 sm:p-1 max-w-full">

        {/* Left Section - PROSPER */}
        <Link
          href="https://prosper.intrans.iastate.edu/"
          className="flex flex-col shrink-0 hover:opacity-90 transition"
        >
          <h1 className="text-sm sm:text-lg mb-0 sm:mb-1 underline">
            PROSPER
          </h1>
          <p className="text-[10px] sm:text-sm leading-tight hidden sm:block">
            Program for Sustainable Pavement Engineering and Research
          </p>
        </Link>

        {/* Right Section - Gravel Road Iowa */}
        <div className="text-xs sm:text-lg md:text-xl font-semibold whitespace-nowrap">
          Gravel Road Monitoring System
        </div>
      </div>
    </header>
  );
};

// Export memoized version to prevent unnecessary re-renders
export default memo(Header);