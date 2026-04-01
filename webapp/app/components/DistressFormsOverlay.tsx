"use client";

import { memo } from 'react';
import { useDistress } from '../contexts/DistressContext';
import RutForm from './DistressForms/rut';
import CorrugationForm from './DistressForms/corrugation';
import CrownForm from './DistressForms/crown';
import DustForm from './DistressForms/dust';
import PotholeForm from './DistressForms/pothole';

const DistressFormsOverlay = () => {
  const { activeDistress, setActiveDistress } = useDistress();

  if (!activeDistress) {
    return null;
  }

  // Dust gets a centered modal
  if (activeDistress === 'Dust') {
    return (
      <div className="absolute inset-0 z-30 flex items-center justify-center pointer-events-auto">
        <div className="absolute inset-0 bg-black/40" />
        <div className="relative rounded-lg p-3 sm:p-5 w-[95vw] sm:w-[44rem] max-w-[44rem] max-h-[90vh] overflow-y-auto shadow-2xl bg-linear-to-b from-slate-800 to-slate-900 ring-1 ring-slate-700/50">
          <button
            onClick={() => setActiveDistress(null)}
            className="absolute top-2 right-2 text-slate-400 hover:text-white z-10"
            aria-label="Close"
          >
            <svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2">
              <path d="M18 6L6 18M6 6l12 12" />
            </svg>
          </button>
          <h1 className="text-xs font-semibold mb-2 text-center text-slate-200">
            <strong>Dust</strong> automatic detection
          </h1>
          <DustForm />
        </div>
      </div>
    );
  }

  // All other distress types use the right-side panel
  return (
    <div className="absolute right-1 sm:right-3 top-1 sm:top-2 z-20 pointer-events-auto">
      <div className="rounded-lg p-3 w-[92vw] sm:w-[24rem] md:w-[26rem] max-w-[26rem] max-h-[85vh] overflow-y-auto shadow-2xl bg-linear-to-b from-slate-800 to-slate-900 ring-1 ring-slate-700/50">
        <button
          onClick={() => setActiveDistress(null)}
          className="absolute top-2 right-2 text-slate-400 hover:text-white z-10"
          aria-label="Close"
        >
          <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2">
            <path d="M18 6L6 18M6 6l12 12" />
          </svg>
        </button>
        <h1 className="text-xs font-semibold mb-2 text-center text-slate-200">
          <strong>{activeDistress}</strong> automatic detection
        </h1>
        <div className="w-full">
          {activeDistress === 'Rut' && <RutForm />}
          {activeDistress === 'Corrugation' && <CorrugationForm />}
          {activeDistress === 'Crown' && <CrownForm />}
          {activeDistress === 'Loose Aggregate' && <div className="text-slate-400">Loose Aggregate form coming soon...</div>}
          {activeDistress === 'Potholes' && <PotholeForm />}
          {activeDistress === 'Drainage' && <div className="text-slate-400">Drainage form coming soon...</div>}
        </div>
      </div>
    </div>
  );
};

export default memo(DistressFormsOverlay);
