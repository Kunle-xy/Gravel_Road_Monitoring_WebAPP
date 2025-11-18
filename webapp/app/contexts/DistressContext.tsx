"use client";

import React, { createContext, useContext, useState, ReactNode } from 'react';

type DistressType = 'rut' | 'corrugation' | 'loose Aggregate' | 'crown' | 'potholes' | 'dust' | 'drainage' | null;

interface DistressContextType {
  activeDistress: DistressType;
  setActiveDistress: (distress: DistressType) => void;
  toggleDistress: (distress: DistressType) => void;
}

const DistressContext = createContext<DistressContextType | undefined>(undefined);

export function DistressProvider({ children }: { children: ReactNode }) {
  const [activeDistress, setActiveDistress] = useState<DistressType>(null);

  const toggleDistress = (distress: DistressType) => {
    // If clicking the same distress, close it
    if (activeDistress === distress) {
      setActiveDistress(null);
    } else {
      setActiveDistress(distress);
    }
  };

  return (
    <DistressContext.Provider value={{ activeDistress, setActiveDistress, toggleDistress }}>
      {children}
    </DistressContext.Provider>
  );
}

export function useDistress() {
  const context = useContext(DistressContext);
  if (context === undefined) {
    throw new Error('useDistress must be used within a DistressProvider');
  }
  return context;
}
