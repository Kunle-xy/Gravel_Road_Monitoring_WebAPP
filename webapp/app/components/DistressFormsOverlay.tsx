"use client";

import { memo } from 'react';
import { useDistress } from '../contexts/DistressContext';
import RutForm from './DistressForms/rut';
import CorrugationForm from './DistressForms/corrugation';

const DistressFormsOverlay = () => {
  const { activeDistress } = useDistress();

  // If no distress is active, don't render anything
  if (!activeDistress) {
    return null;
  }

  return (
    <div className="absolute right-3 top-2 z-20 pointer-events-auto">
      <div className="bg-white outline rounded-sm p-3 w-[22rem] sm:w-[24rem] md:w-[26rem] max-w-[92vw]">
        <h1 className="text-xs font-semibold mb-2 text-center text-red-800">
          <strong>{activeDistress}</strong> automatic detection
        </h1>
        <div className="w-full">
          {activeDistress === 'rut' && <RutForm />}
          {activeDistress === 'corrugation' && <CorrugationForm />}
          {activeDistress === 'loose Aggregate' && <div>Loose Aggregate form coming soon...</div>}
          {activeDistress === 'crown' && <div>Crown form coming soon...</div>}
          {activeDistress === 'potholes' && <div>Potholes form coming soon...</div>}
          {activeDistress === 'dust' && <div>Dust form coming soon...</div>}
          {activeDistress === 'drainage' && <div>Drainage form coming soon...</div>}
        </div>
      </div>
    </div>
  );
};

// Memoize to prevent re-renders when activeDistress doesn't change
export default memo(DistressFormsOverlay);
