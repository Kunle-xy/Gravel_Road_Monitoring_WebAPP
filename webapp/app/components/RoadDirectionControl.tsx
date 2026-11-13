"use client";

import { useId } from "react";
import { usePolygons } from "../contexts/PolygonContext";

export default function RoadDirectionControl({ polygonId }: { polygonId: string }) {
  const name = useId();
  const { polygons, updatePolygon, editingPolygonId } = usePolygons();
  const polygon = polygons.find(p => p.id === polygonId);
  return (
    <fieldset disabled={!polygon || editingPolygonId === polygonId} className="my-2 text-[12px] text-slate-300 disabled:opacity-50">
      <legend className="font-semibold">Road direction{polygon ? ` — ${polygon.name}` : ''}</legend>
      <div className="flex gap-4 py-1">
        {(["horizontal", "vertical"] as const).map(direction => (
          <label key={direction} className="flex items-center gap-1 cursor-pointer">
            <input type="radio" name={name} value={direction}
              checked={polygon?.roadDirection === direction}
              onChange={() => updatePolygon(polygonId, { roadDirection: direction })} />
            {direction === "horizontal" ? "Horizontal" : "Vertical"}
          </label>
        ))}
      </div>
      <p className="text-slate-400">Direction before polygon rotation. Lines rotate with the polygon.</p>
    </fieldset>
  );
}
