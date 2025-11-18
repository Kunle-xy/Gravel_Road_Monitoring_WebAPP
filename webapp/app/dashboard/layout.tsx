"use client";

import Header from "../components/Header";
import ProfileWidget from "../components/ProfileWidget";
import DistressWidget from "../components/DistressWidget";
import HomeWidget from "../components/HomeWidget";
import MapClient from "../components/MapClient";
import DistressFormsOverlay from "../components/DistressFormsOverlay";
import { MapProvider } from "../contexts/MapContext";
import { DistressProvider } from "../contexts/DistressContext";
import ProtectedRoute from "../components/ProtectedRoute";

export default function DashboardLayout({
  children,
}: {
  children: React.ReactNode;
}) {
  return (
    <ProtectedRoute>
      <DistressProvider>
        <MapProvider>
          <div className="h-screen overflow-hidden flex flex-col">
            <header className="font-header shrink-0">
              <Header />
            </header>

            <div className="flex-1 flex flex-col overflow-hidden">
              <div className="shrink-0">
                <DistressWidget />
              </div>

              <div className="flex-1 flex overflow-hidden">
                <div className="shrink-0">
                  <ProfileWidget />
                </div>

                <div className="flex-1 relative overflow-hidden">
                  {/* Map as fixed background */}
                  <div className="absolute inset-0 z-0">
                    <MapClient />
                  </div>

                  {/* Distress Forms Overlay */}
                  <DistressFormsOverlay />

                  {/* Children (if needed for other routes) */}
                  <div className="relative z-10 h-full overflow-y-auto pointer-events-none">
                    <div className="pointer-events-auto">
                      {children}
                    </div>
                  </div>
                </div>
              </div>
            </div>

            <HomeWidget />
          </div>
        </MapProvider>
      </DistressProvider>
    </ProtectedRoute>
  );
}