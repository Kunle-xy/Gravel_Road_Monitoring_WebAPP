// components/Header.tsx
import React, { memo } from 'react';
import Link from 'next/link';

const Header = () => {
  return (
    <header className="bg-red-800 text-white w-full">
      <div className="flex flex-col sm:flex-row justify-between items-start sm:items-center gap-4 p-1 max-w-full">
        
        {/* Left Section - PROSPER */}
        <Link 
          href="https://prosper.intrans.iastate.edu/"
          className="flex flex-col w-full sm:w-64 shrink-0 hover:opacity-90 transition"
        >
          <h1 className="text-lg mb-1 underline">
            PROSPER
          </h1>
          <p className="text-sm leading-tight">
            Program for Sustainable Pavement Engineering and Research
          </p>
        </Link>

        {/* Right Section - Gravel Road Iowa */}
        <div className="flex flex-col items-end text-right">
          <div className="text-lg sm:text-xl font-semibold whitespace-nowrap">
            Gravel Road Monitoring System
          </div>
          <div className="text-xs opacity-75 whitespace-nowrap">
            v1.0.0 &mdash; Developed by Kunle S Oguntoye (oguntoye@iastate.edu)
          </div>
        </div>
      </div>
    </header>
  );
};

// Export memoized version to prevent unnecessary re-renders
export default memo(Header);