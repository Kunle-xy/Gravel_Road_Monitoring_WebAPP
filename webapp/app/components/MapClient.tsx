// app/components/MapClient.tsx
"use client";

import dynamic from "next/dynamic";

// load Map only on the client, no SSR
const MapDynamic = dynamic(() => import("./Map"), { ssr: false });

export default function MapClient() {
  return <MapDynamic />;
}
