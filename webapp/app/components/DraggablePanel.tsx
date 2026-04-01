"use client";

import React, { useState, useRef, useCallback, useEffect } from "react";

interface DraggablePanelProps {
  children: React.ReactNode;
  initialX?: number;
  initialY?: number;
  initialWidth?: number;
  initialHeight?: number;
  minWidth?: number;
  minHeight?: number;
  maxWidth?: number;
  maxHeight?: number;
  onClose: () => void;
  title: React.ReactNode;
  className?: string;
}

export default function DraggablePanel({
  children,
  initialX,
  initialY,
  initialWidth = 420,
  initialHeight,
  minWidth = 280,
  minHeight = 200,
  maxWidth = 900,
  maxHeight,
  onClose,
  title,
  className = "",
}: DraggablePanelProps) {
  const panelRef = useRef<HTMLDivElement>(null);

  // Position & size
  const [pos, setPos] = useState({ x: initialX ?? -1, y: initialY ?? 8 });
  const [size, setSize] = useState({ w: initialWidth, h: initialHeight ?? 0 });
  const [autoHeight, setAutoHeight] = useState(!initialHeight);

  // Drag state
  const dragging = useRef(false);
  const dragOffset = useRef({ x: 0, y: 0 });

  // Resize state
  const resizing = useRef(false);
  const resizeStart = useRef({ x: 0, y: 0, w: 0, h: 0 });

  // Set initial position to right side if not specified
  useEffect(() => {
    if (pos.x === -1 && typeof window !== "undefined") {
      setPos({ x: window.innerWidth - initialWidth - 12, y: 8 });
    }
  }, [pos.x, initialWidth]);

  // --- DRAG ---
  const onDragStart = useCallback((e: React.MouseEvent) => {
    if ((e.target as HTMLElement).closest("button, select, input, a")) return;
    dragging.current = true;
    dragOffset.current = { x: e.clientX - pos.x, y: e.clientY - pos.y };
    e.preventDefault();
  }, [pos]);

  useEffect(() => {
    const onMove = (e: MouseEvent) => {
      if (dragging.current) {
        const x = Math.max(0, Math.min(e.clientX - dragOffset.current.x, window.innerWidth - 100));
        const y = Math.max(0, Math.min(e.clientY - dragOffset.current.y, window.innerHeight - 40));
        setPos({ x, y });
      }
      if (resizing.current) {
        const dw = e.clientX - resizeStart.current.x;
        const dh = e.clientY - resizeStart.current.y;
        const w = Math.max(minWidth, Math.min(resizeStart.current.w + dw, maxWidth));
        const h = Math.max(minHeight, Math.min(resizeStart.current.h + dh, maxHeight ?? window.innerHeight - 40));
        setSize({ w, h });
        setAutoHeight(false);
      }
    };
    const onUp = () => {
      dragging.current = false;
      resizing.current = false;
    };
    window.addEventListener("mousemove", onMove);
    window.addEventListener("mouseup", onUp);
    return () => { window.removeEventListener("mousemove", onMove); window.removeEventListener("mouseup", onUp); };
  }, [minWidth, minHeight, maxWidth, maxHeight]);

  // --- RESIZE ---
  const onResizeStart = useCallback((e: React.MouseEvent) => {
    resizing.current = true;
    const rect = panelRef.current?.getBoundingClientRect();
    resizeStart.current = {
      x: e.clientX, y: e.clientY,
      w: rect?.width ?? size.w, h: rect?.height ?? size.h,
    };
    e.preventDefault();
    e.stopPropagation();
  }, [size]);

  return (
    <div
      ref={panelRef}
      className={`fixed z-20 pointer-events-auto flex flex-col shadow-2xl ${className}`}
      style={{
        left: pos.x,
        top: pos.y,
        width: size.w,
        ...(autoHeight ? { maxHeight: "85vh" } : { height: size.h }),
      }}
    >
      {/* Drag handle (header) */}
      <div
        onMouseDown={onDragStart}
        className="flex items-center justify-between px-3 py-2 bg-slate-100 rounded-t-md border border-b-0 border-slate-300 cursor-move select-none shrink-0"
      >
        <div className="text-xs font-semibold text-red-800">{title}</div>
        <button
          onClick={onClose}
          className="text-gray-400 hover:text-gray-600 ml-2"
          aria-label="Close"
        >
          <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2">
            <path d="M18 6L6 18M6 6l12 12" />
          </svg>
        </button>
      </div>

      {/* Content */}
      <div className="flex-1 overflow-y-auto bg-white border border-slate-300 rounded-b-md p-3">
        {children}
      </div>

      {/* Resize handle (bottom-right corner) */}
      <div
        onMouseDown={onResizeStart}
        className="absolute bottom-0 right-0 w-4 h-4 cursor-nwse-resize"
        title="Drag to resize"
      >
        <svg width="16" height="16" viewBox="0 0 16 16" className="text-slate-400">
          <path d="M14 14L8 14M14 14L14 8M14 14L4 14M14 14L14 4" stroke="currentColor" strokeWidth="1.5" fill="none" />
        </svg>
      </div>
    </div>
  );
}
