// app/components/HomeWidget.tsx
"use client";
import React, { memo } from "react";
import Link from "next/link";

const HomeWidget = () => {
  return (
    <div
      className="fixed bottom-4 right-4 sm:bottom-6 sm:right-6 z-[2147483647]"
      style={{ pointerEvents: "auto" }}
    >
      <Link
        href="/"
        aria-label="Home"
        className="flex h-10 w-10 sm:h-12 sm:w-12 items-center justify-center rounded-full
                   bg-slate-900 text-white shadow-xl ring-2 ring-slate-700
                   hover:bg-slate-800 focus:outline-none focus:ring-4 focus:ring-blue-400
                   transition-all duration-200
                   pointer-events-auto"
      >
        <HomeIcon className="h-5 w-5 sm:h-6 sm:w-6" />
      </Link>
    </div>
  );
};

// Export memoized version to prevent unnecessary re-renders
export default memo(HomeWidget);

// Reusable SVG Icon
function HomeIcon({ className = "" }: { className?: string }) {
  return (
    <svg
      className={className}
      viewBox="0 0 24 24"
      fill="currentColor"
      aria-hidden="true"
    >
      <path d="M12.53 2.16a.75.75 0 0 0-1.06 0L3.2 10.43a.75.75 0 0 0 .53 1.28H5v8a1.5 1.5 0 0 0 1.5 1.5h4a.75.75 0 0 0 .75-.75V16.5h1.5v3.96a.75.75 0 0 0 .75.75h4A1.5 1.5 0 0 0 20 19.71v-8h1.27a.75.75 0 0 0 .53-1.28l-9.27-8.27Z" />
    </svg>
  );
}