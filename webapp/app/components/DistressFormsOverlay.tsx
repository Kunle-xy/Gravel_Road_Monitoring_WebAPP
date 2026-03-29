"use client";

import { memo } from 'react';
import { useDistress } from '../contexts/DistressContext';
import RutForm from './DistressForms/rut';
import CorrugationForm from './DistressForms/corrugation';
import CrownForm from './DistressForms/crown';
import DustForm from './DistressForms/dust';

const DistressFormsOverlay = () => {
  const { activeDistress, setActiveDistress } = useDistress();

  // If no distress is active, don't render anything
  if (!activeDistress) {
    return null;
  }

  // Dust gets a centered modal
  if (activeDistress === 'Dust') {
    return (
      <div className="absolute inset-0 z-30 flex items-center justify-center pointer-events-auto">
        {/* Backdrop */}
        <div
          className="absolute inset-0 bg-black/40"
          onClick={() => setActiveDistress(null)}
        />
        {/* Centered modal */}
        <div className="relative bg-white outline rounded-lg p-5 w-[44rem] max-w-[95vw] max-h-[90vh] overflow-y-auto shadow-2xl">
          <button
            onClick={() => setActiveDistress(null)}
            className="absolute top-2 right-2 text-gray-400 hover:text-gray-600 z-10"
            aria-label="Close"
          >
            <svg width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2">
              <path d="M18 6L6 18M6 6l12 12" />
            </svg>
          </button>
          <h1 className="text-xs font-semibold mb-2 text-center text-red-800">
            <strong>Dust</strong> automatic detection
          </h1>
          <DustForm />
        </div>
      </div>
    );
  }

  // All other distress types use the right-side panel
  return (
    <div className="absolute right-3 top-2 z-20 pointer-events-auto">
      <div className="bg-white outline rounded-sm p-3 w-[22rem] sm:w-[24rem] md:w-[26rem] max-w-[92vw]">
        <h1 className="text-xs font-semibold mb-2 text-center text-red-800">
          <strong>{activeDistress}</strong> automatic detection
        </h1>
        <div className="w-full">
          {activeDistress === 'Rut' && <RutForm />}
          {activeDistress === 'Corrugation' && <CorrugationForm />}
          {activeDistress === 'Crown' && <CrownForm />}
          {activeDistress === 'Loose Aggregate' && <div>Loose Aggregate form coming soon...</div>}
          {activeDistress === 'Potholes' && <div>Potholes form coming soon...</div>}
          {activeDistress === 'Drainage' && <div>Drainage form coming soon...</div>}
        </div>
      </div>
    </div>
  );
};

// Memoize to prevent re-renders when activeDistress doesn't change
export default memo(DistressFormsOverlay);
