"use client";

import { memo } from 'react';
import { useDistress } from '../contexts/DistressContext';
import RutForm from './DistressForms/rut';
import CorrugationForm from './DistressForms/corrugation';
import CrownForm from './DistressForms/crown';
import DustForm from './DistressForms/dust';
import PotholeForm from './DistressForms/pothole';
import FinalURCIForm from './DistressForms/final_urci';

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

// Each form keeps its own state in `useState`, so unmounting throws away the
// user's selected DEM, polygon, parameter values, and pending/finished
// results. Switching tabs and reopening would reset everything to defaults
// — exactly what looked like "the form reverts to its old version".
//
// We mount every form once and toggle visibility with `hidden`/`display:none`
// instead of conditional rendering. State is preserved across closes and
// switches; only the DOM tree's CSS visibility changes.

const PanelShell = ({ visible, children }: { visible: boolean; children: React.ReactNode }) => (
  <div className={visible ? '' : 'hidden'}>{children}</div>
);

const DistressFormsOverlay = () => {
  const { activeDistress, setActiveDistress } = useDistress();
  const close = () => setActiveDistress(null);

  const isDust = activeDistress === 'Dust';
  const panelKinds = ['Rut', 'Corrugation', 'Crown', 'Loose Aggregate', 'Potholes', 'Drainage', 'Final URCI'] as const;
  const panelOpen = activeDistress != null && (panelKinds as readonly string[]).includes(activeDistress);

  return (
    <>
      {/* Dust modal — mounted always for state persistence; visible only when active */}
      <div
        className={`absolute inset-0 z-30 flex items-center justify-center pointer-events-auto ${
          isDust ? '' : 'hidden'
        }`}
      >
        <div className="absolute inset-0 bg-black/40" />
        <div className="relative w-[95vw] sm:w-[44rem] max-w-[44rem] max-h-[90vh] overflow-y-auto">
          <CloseButton onClick={close} />
          <DustForm />
        </div>
      </div>

      {/* Right-side panel — mounted always; child forms toggled by `hidden` */}
      <div
        className={`absolute right-1 sm:right-3 top-1 sm:top-2 z-20 pointer-events-auto ${
          panelOpen ? '' : 'hidden'
        }`}
      >
        <div className="relative w-[92vw] sm:w-[24rem] md:w-[26rem] max-w-[26rem] max-h-[85vh] overflow-y-auto">
          <CloseButton onClick={close} />
          <PanelShell visible={activeDistress === 'Rut'}><RutForm /></PanelShell>
          <PanelShell visible={activeDistress === 'Corrugation'}><CorrugationForm /></PanelShell>
          <PanelShell visible={activeDistress === 'Crown'}><CrownForm /></PanelShell>
          <PanelShell visible={activeDistress === 'Potholes'}><PotholeForm /></PanelShell>
          <PanelShell visible={activeDistress === 'Final URCI'}><FinalURCIForm /></PanelShell>
          <PanelShell visible={activeDistress === 'Loose Aggregate'}>
            <div className="text-slate-400 bg-slate-800 rounded-lg p-4">Loose Aggregate form coming soon...</div>
          </PanelShell>
          <PanelShell visible={activeDistress === 'Drainage'}>
            <div className="text-slate-400 bg-slate-800 rounded-lg p-4">Drainage form coming soon...</div>
          </PanelShell>
        </div>
      </div>
    </>
  );
};

export default memo(DistressFormsOverlay);
