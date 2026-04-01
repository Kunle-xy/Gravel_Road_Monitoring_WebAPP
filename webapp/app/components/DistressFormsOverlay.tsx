"use client";

import { memo } from 'react';
import { useDistress } from '../contexts/DistressContext';
import RutForm from './DistressForms/rut';
import CorrugationForm from './DistressForms/corrugation';
import CrownForm from './DistressForms/crown';
import DustForm from './DistressForms/dust';
import PotholeForm from './DistressForms/pothole';
import DraggablePanel from './DraggablePanel';

const DistressFormsOverlay = () => {
  const { activeDistress, setActiveDistress } = useDistress();

  if (!activeDistress) {
    return null;
  }

  // Dust gets a wider panel
  if (activeDistress === 'Dust') {
    return (
      <DraggablePanel
        onClose={() => setActiveDistress(null)}
        title={<><strong>Dust</strong> automatic detection</>}
        initialWidth={700}
        minWidth={400}
        maxWidth={1000}
        minHeight={300}
      >
        <DustForm />
      </DraggablePanel>
    );
  }

  // All other distress types
  return (
    <DraggablePanel
      onClose={() => setActiveDistress(null)}
      title={<><strong>{activeDistress}</strong> automatic detection</>}
      initialWidth={420}
      minWidth={280}
      maxWidth={600}
      minHeight={200}
    >
      {activeDistress === 'Rut' && <RutForm />}
      {activeDistress === 'Corrugation' && <CorrugationForm />}
      {activeDistress === 'Crown' && <CrownForm />}
      {activeDistress === 'Loose Aggregate' && <div>Loose Aggregate form coming soon...</div>}
      {activeDistress === 'Potholes' && <PotholeForm />}
      {activeDistress === 'Drainage' && <div>Drainage form coming soon...</div>}
    </DraggablePanel>
  );
};

export default memo(DistressFormsOverlay);
