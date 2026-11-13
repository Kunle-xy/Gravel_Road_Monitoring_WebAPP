export interface XY { x: number; y: number }

export function rotatePoints(points: XY[], center: XY, angle: number): XY[] {
  const c = Math.cos(angle), s = Math.sin(angle);
  return points.map(p => ({
    x: center.x + (p.x - center.x) * c - (p.y - center.y) * s,
    y: center.y + (p.x - center.x) * s + (p.y - center.y) * c,
  }));
}

export function resizeEdge(points: XY[], edge: number, delta: XY, minimum = 2): XY[] {
  const a = points[edge], b = points[(edge + 1) % 4];
  const length = Math.hypot(b.x - a.x, b.y - a.y);
  if (!length) return points;
  const nx = -(b.y - a.y) / length, ny = (b.x - a.x) / length;
  const opposite = points[(edge + 2) % 4];
  const gap = (opposite.x - a.x) * nx + (opposite.y - a.y) * ny;
  const margin = Math.min(minimum, Math.abs(gap));
  const requested = delta.x * nx + delta.y * ny;
  const offset = gap > 0 ? Math.min(requested, gap - margin) : Math.max(requested, gap + margin);
  return points.map((p, i) => i === edge || i === (edge + 1) % 4
    ? { x: p.x + offset * nx, y: p.y + offset * ny } : p);
}

export function samplingPreview(points: XY[], edge: number, direction: 'horizontal' | 'vertical') {
  const at = (i: number) => points[(edge + i) % 4];
  const lerp = (a: XY, b: XY, t: number): XY => ({ x: a.x + (b.x - a.x) * t, y: a.y + (b.y - a.y) * t });
  const across: XY[][] = [], along: XY[][] = [];
  for (const t of [.2, .4, .6, .8]) {
    across.push([lerp(at(0), at(1), t), lerp(at(3), at(2), t)]);
    along.push([lerp(at(0), at(3), t), lerp(at(1), at(2), t)]);
  }
  return direction === 'horizontal' ? { across, along } : { across: along, along: across };
}

export interface DragSession {
  move: (event: PointerEvent) => void;
  finish: () => void;
}

// Finish on pointer-up, cancellation, window blur, or component cleanup. A
// visible edit must never be discarded just because a React effect rerenders.
export function attachPointerDrag(element: HTMLElement, start: (event: PointerEvent) => DragSession | undefined) {
  const document = element.ownerDocument;
  const window = document.defaultView;
  let session: DragSession | undefined;
  let pointerId: number | undefined;
  const finish = () => {
    const current = session;
    const captured = pointerId;
    session = undefined;
    pointerId = undefined;
    if (captured !== undefined && element.hasPointerCapture?.(captured)) {
      element.releasePointerCapture(captured);
    }
    current?.finish();
  };
  const move = (event: PointerEvent) => {
    if (event.pointerId !== pointerId) return;
    event.preventDefault();
    session?.move(event);
  };
  const up = (event: PointerEvent) => {
    if (event.pointerId === pointerId) finish();
  };
  const down = (event: PointerEvent) => {
    if (event.button !== 0 || session) return;
    event.preventDefault();
    event.stopPropagation();
    session = start(event);
    pointerId = session ? event.pointerId : undefined;
    if (session) {
      try { element.setPointerCapture?.(event.pointerId); } catch { /* pointer already released */ }
    }
  };
  const touchAction = element.style.touchAction;
  element.style.touchAction = 'none';
  element.addEventListener('pointerdown', down);
  element.addEventListener('lostpointercapture', finish);
  document.addEventListener('pointermove', move, { capture: true, passive: false });
  document.addEventListener('pointerup', up, true);
  document.addEventListener('pointercancel', up, true);
  window?.addEventListener('blur', finish);
  const detach = () => {
    element.removeEventListener('pointerdown', down);
    element.removeEventListener('lostpointercapture', finish);
    document.removeEventListener('pointermove', move, true);
    document.removeEventListener('pointerup', up, true);
    document.removeEventListener('pointercancel', up, true);
    window?.removeEventListener('blur', finish);
    element.style.touchAction = touchAction;
    finish();
  };
  detach.finish = finish;
  return detach;
}
