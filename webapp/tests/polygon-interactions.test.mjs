import { test } from 'node:test';
import assert from 'node:assert/strict';
import { join } from 'node:path';
import { createRequire } from 'node:module';
const loadModule = createRequire(import.meta.url);
const { createPolygonStore, polygonSelectionKey } = loadModule(join(process.env.POLYGON_TEST_BUILD_DIR, 'polygonStore.js'));
const { rotatePoints, resizeEdge, attachPointerDrag } = loadModule(join(process.env.POLYGON_TEST_BUILD_DIR, 'polygonEditing.js'));
const shape = () => ({ type: 'Polygon', coordinates: [[[0, 0], [0, 4], [8, 4], [8, 0], [0, 0]]], horizontal_edge_index: 1 });
const input = name => ({ name, geoJSON: shape() });

test('a direction change immediately reaches submissions, even through an old callback', () => {
  const store = createPolygonStore();
  const polygon = store.addPolygon(input('First'));
  const oldSubmit = store.getAnalysisSelection;
  store.updatePolygon(polygon.id, { roadDirection: 'vertical' });
  assert.equal(oldSubmit('dem').road_direction, 'vertical');
  assert.equal(store.getSnapshot().selectedPolygonId, polygon.id);
});

test('rotation commits preserve the latest direction and the original edge identity', () => {
  const store = createPolygonStore();
  const polygon = store.addPolygon(input('First'));
  store.beginPolygonEdit(polygon.id);
  assert.throws(() => store.getAnalysisSelection('dem'), /Finish dragging/);
  store.updatePolygon(polygon.id, { roadDirection: 'vertical' });
  const geometry = [[[1, 2], [2, 5], [6, 4], [5, 1], [1, 2]]];
  store.updatePolygonGeometry(polygon.id, geometry);
  store.finishPolygonEdit(polygon.id);
  const request = store.getAnalysisSelection('dem');
  assert.equal(request.road_direction, 'vertical');
  assert.equal(request.polygon_geojson.horizontal_edge_index, 1);
  assert.deepEqual(request.polygon_geojson.coordinates, geometry);
});

test('all panels share selection while each polygon remembers its own direction', () => {
  const store = createPolygonStore();
  const first = store.addPolygon(input('First'));
  store.updatePolygon(first.id, { roadDirection: 'vertical' });
  const second = store.addPolygon(input('Second'));
  assert.equal(store.getAnalysisSelection('dem').road_direction, 'horizontal');
  store.setSelectedPolygonId(first.id);
  assert.equal(store.getAnalysisSelection('dem').road_direction, 'vertical');
  store.setSelectedPolygonId(second.id);
  assert.equal(store.getAnalysisSelection('dem').road_direction, 'horizontal');
  store.removePolygon(second.id);
  assert.throws(() => store.getAnalysisSelection('dem'), /Select a polygon/);
  store.setSelectedPolygonId('deleted-id');
  assert.equal(store.getSnapshot().selectedPolygonId, '');
});

test('job snapshots cannot change underneath an in-flight request', () => {
  const store = createPolygonStore();
  const polygon = store.addPolygon(input('First'));
  const submitted = store.getAnalysisSelection('dem');
  const edited = shape().coordinates;
  edited[0][0][0] = 100;
  store.updatePolygonGeometry(polygon.id, edited);
  assert.notEqual(store.getAnalysisSelection('dem').key, submitted.key);
  assert.equal(submitted.polygon_geojson.coordinates[0][0][0], 0);
  assert.notEqual(polygonSelectionKey(store.getPolygon(polygon.id), 'other-dem'), submitted.key);
});

test('an overlay response is rejected immediately when selection changes or dragging begins', () => {
  const store = createPolygonStore();
  const polygon = store.addPolygon(input('First'));
  const request = store.getAnalysisSelection('dem');
  assert.equal(store.isAnalysisSelectionCurrent(request.key, 'dem'), true);
  store.beginPolygonEdit(polygon.id);
  assert.equal(store.isAnalysisSelectionCurrent(request.key, 'dem'), false);
  store.finishPolygonEdit(polygon.id);
  store.updatePolygon(polygon.id, { roadDirection: 'vertical' });
  assert.equal(store.isAnalysisSelectionCurrent(request.key, 'dem'), false);
});

test('repeated rotations preserve subpixel geometry rather than rounding to display pixels', () => {
  const points = [{ x: 100000.1234, y: 99999.8876 }, { x: 100001.2345, y: 99999.8765 },
    { x: 100001.2456, y: 100000.9876 }, { x: 100000.1345, y: 100000.9987 }];
  const center = { x: 100000.5, y: 100000.5 };
  let rotated = points;
  for (let i = 0; i < 100; i++) {
    rotated = rotatePoints(rotated, center, Math.PI / 6);
    rotated = rotatePoints(rotated, center, -Math.PI / 6);
  }
  rotated.forEach((p, i) => assert.ok(Math.hypot(p.x - points[i].x, p.y - points[i].y) < 1e-7));
});

test('resizing cannot cross the opposite edge and invert the polygon', () => {
  const points = [{ x: 0, y: 0 }, { x: 0, y: 4 }, { x: 8, y: 4 }, { x: 8, y: 0 }];
  const resized = resizeEdge(points, 1, { x: 0, y: -20 }, .1);
  assert.ok(resized[1].y > resized[0].y);
  assert.ok(Math.abs(resized[1].y - resized[0].y - .1) < 1e-9);
  assert.deepEqual(resized[0], points[0]);
  assert.deepEqual(resized[3], points[3]);
});


function pointer(type, values = {}) {
  return Object.assign(new Event(type, { cancelable: true }), { button: 0, pointerId: 1, ...values });
}
function elementFixture() {
  const window = new EventTarget();
  const document = Object.assign(new EventTarget(), { defaultView: window });
  const element = Object.assign(new EventTarget(), { ownerDocument: document, style: { touchAction: 'auto' } });
  return { element, document, window };
}

for (const ending of ['pointerup', 'pointercancel', 'blur', 'cleanup', 'viewport change', 'lostpointercapture']) {
  test(`a drag commits exactly once on ${ending}, including release outside its handle`, () => {
    const { element, document, window } = elementFixture();
    let moved = 0, finished = 0;
    const detach = attachPointerDrag(element, () => ({ move: () => moved++, finish: () => finished++ }));
    element.dispatchEvent(pointer('pointerdown'));
    document.dispatchEvent(pointer('pointermove', { pointerId: 99 }));
    assert.equal(moved, 0);
    document.dispatchEvent(pointer('pointermove'));
    assert.equal(moved, 1);
    if (ending === 'blur') window.dispatchEvent(new Event('blur'));
    else if (ending === 'cleanup') detach();
    else if (ending === 'viewport change') detach.finish();
    else if (ending === 'lostpointercapture') element.dispatchEvent(new Event('lostpointercapture'));
    else document.dispatchEvent(pointer(ending));
    detach();
    document.dispatchEvent(pointer('pointerup'));
    assert.equal(finished, 1);
    assert.equal(element.style.touchAction, 'auto');
  });
}

test('switching selection during drag commits the edited polygon, not its replacement', () => {
  const store = createPolygonStore();
  const first = store.addPolygon(input('First'));
  const second = store.addPolygon(input('Second'));
  store.setSelectedPolygonId(first.id);
  const { element, document } = elementFixture();
  const detach = attachPointerDrag(element, () => {
    store.beginPolygonEdit(first.id);
    let geometry = shape().coordinates;
    return {
      move: () => { geometry = [[[2, 0], [2, 4], [8, 4], [8, 0], [2, 0]]]; },
      finish: () => {
        store.updatePolygonGeometry(first.id, geometry);
        store.finishPolygonEdit(first.id);
      },
    };
  });
  element.dispatchEvent(pointer('pointerdown'));
  document.dispatchEvent(pointer('pointermove'));
  store.setSelectedPolygonId(second.id);
  detach();
  assert.equal(store.getPolygon(first.id).geoJSON.coordinates[0][0][0], 2);
  assert.equal(store.getPolygon(second.id).geoJSON.coordinates[0][0][0], 0);
  assert.equal(store.getSnapshot().selectedPolygonId, second.id);
  assert.equal(store.getSnapshot().editingPolygonId, null);
});
