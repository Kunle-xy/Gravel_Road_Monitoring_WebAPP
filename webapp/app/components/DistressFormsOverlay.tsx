"use client";

import { memo } from 'react';
import { useDistress } from '../contexts/DistressContext';
import RutForm from './DistressForms/rut';
import CorrugationForm from './DistressForms/corrugation';
import CrownForm from './DistressForms/crown';
import DustForm from './DistressForms/dust';
import PotholeForm from './DistressForms/pothole';

const CloseButton = ({ onClick }: { onClick: () => void }) => (
  <button
    onClick={onClick}
    className="absolute top-3 right-3 text-slate-400 hover:text-white z-10 p-0.5 hover:bg-slate-700 rounded transition-colors"
    aria-label="Close"
  >
    <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2.5">
      <path d="M18 6L6 18M6 6l12 12" />
    </svg>
  </button>
);

const DistressFormsOverlay = () => {
  const { activeDistress, setActiveDistress } = useDistress();

  if (!activeDistress) {
    return null;
  }

  const close = () => setActiveDistress(null);

  // Dust gets a centered modal
  if (activeDistress === 'Dust') {
    return (
      <div className="absolute inset-0 z-30 flex items-center justify-center pointer-events-auto">
        <div className="absolute inset-0 bg-black/40" />
        <div className="relative w-[95vw] sm:w-[44rem] max-w-[44rem] max-h-[90vh] overflow-y-auto">
          <CloseButton onClick={close} />
          <DustForm />
        </div>
      </div>
    );
  }

  // All other distress types use the right-side panel
  return (
    <div className="absolute right-1 sm:right-3 top-1 sm:top-2 z-20 pointer-events-auto">
      <div className="relative w-[92vw] sm:w-[24rem] md:w-[26rem] max-w-[26rem] max-h-[85vh] overflow-y-auto">
        <CloseButton onClick={close} />
        {activeDistress === 'Rut' && <RutForm />}
        {activeDistress === 'Corrugation' && <CorrugationForm />}
        {activeDistress === 'Crown' && <CrownForm />}
        {activeDistress === 'Loose Aggregate' && <div className="text-slate-400 bg-slate-800 rounded-lg p-4">Loose Aggregate form coming soon...</div>}
        {activeDistress === 'Potholes' && <PotholeForm />}
        {activeDistress === 'Drainage' && <div className="text-slate-400 bg-slate-800 rounded-lg p-4">Drainage form coming soon...</div>}
      </div>
    </div>
  );
};

export default memo(DistressFormsOverlay);
