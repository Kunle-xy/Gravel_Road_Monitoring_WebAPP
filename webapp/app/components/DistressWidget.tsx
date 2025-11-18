"use client";
import React, { memo } from "react";
import { useDistress } from "../contexts/DistressContext";

const Distress: Array<'Rut' | 'Corrugation' | 'Loose Aggregate' | 'Crown' | 'Potholes' | 'Dust' | 'Drainage'> = [
  "Rut",
  "Corrugation",
  "Loose Aggregate",
  "Crown",
  "Potholes",
  "Dust",
  "Drainage"
];

function DistressWidget() {
  const [open, setOpen] = React.useState(false);
  const { activeDistress, toggleDistress } = useDistress();

  return (
    <div className="w-full">
      {/* toggle */}
      <button
        type="button"
        onClick={() => setOpen((v) => !v)}
        className="flex items-center gap-2 px-3 py-2 rounded-md bg-gray-100 hover:bg-gray-200 transition-colors"
        aria-expanded={open}
        aria-controls="distress-list"
      >
        <span className="text-sm font-medium"> Gravel Distress Types</span>
        {/* arrow rotates when open */}
        <svg
          className={`h-4 w-4 transition-transform ${open ? "rotate-180" : "rotate-0"}`}
          viewBox="0 0 20 20"
          fill="currentColor"
          aria-hidden="true"
        >
          <path d="M5.23 7.21a.75.75 0 0 1 1.06.02L10 10.17l3.71-2.94a.75.75 0 1 1 .94 1.16l-4.24 3.36a.75.75 0 0 1-.94 0L5.21 8.39a.75.75 0 0 1 .02-1.18z" />
        </svg>
      </button>

      {/* collapsible container */}
      <div
        id="distress-list"
        className={`overflow-hidden transition-[max-height,opacity] duration-300 ease-out ${
          open ? "max-h-48 opacity-100" : "max-h-0 opacity-0"
        }`}
      >
        <ul className="mt-2 flex flex-row flex-wrap items-center gap-2 overflow-x-auto py-1">
          {Distress.map((type, index) => (
            <li key={index}>
              <button
                onClick={() => toggleDistress(type)}
                className={`px-3 py-1 rounded-full shadow-sm hover:shadow transition-all text-sm whitespace-nowrap ${
                  activeDistress === type
                    ? 'bg-red-800 text-white font-semibold ring-2 ring-red-600'
                    : 'bg-white text-gray-800 hover:bg-gray-500 hover:text-white'
                }`}
              >
                {type}
              </button>
            </li>
          ))}
        </ul>
      </div>
    </div>
  );
}

// Export memoized version to prevent unnecessary re-renders
export default memo(DistressWidget);
