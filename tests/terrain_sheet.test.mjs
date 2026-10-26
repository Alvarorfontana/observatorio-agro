import test from 'node:test';
import assert from 'node:assert/strict';
import { sheetScope, sheetSection, readingText } from '../src/dashboard/terrainSheetModel.ts';

test('un dato cero no se convierte en faltante', () => {
  const s = sheetSection('ndvi', { status: 'recibido', payload: { data: { latest: { ndvi_mean: 0 } } } });
  assert.equal(s.state, 'recibido');
  assert.equal(s.readings[0].value, 0);
  assert.notEqual(readingText(s.readings[0]), 'Sin dato');
});

test('lluvia incompleta no se presenta como un acumulado válido', () => {
  const s = sheetSection('variables', { status: 'recibido', payload: { data: { daily: { precipitation_sum: [3, null, 5] } } } });
  assert.equal(s.readings[1].value, null);
});

test('una respuesta con carbono pero sin WorldCover no acredita cobertura', () => {
  const s = sheetSection('sustentabilidad', { status: 'recibido', payload: { data: { carbon: { soc_t_ha: 50 }, deforestation: { worldcover: [] } } } });
  assert.equal(s.state, 'sin dato');
  assert(s.readings.every(r => r.value === null));
});

test('los resultados quedan asociados al punto y al polígono, no al nombre', () => {
  const lot = { center: [-28, -59], vertices: [[-28, -59], [-28.1, -59], [-28, -59.1]] };
  assert.equal(sheetScope(lot), sheetScope({ ...lot, name: 'Otro nombre' }));
  assert.notEqual(sheetScope(lot), sheetScope({ ...lot, vertices: [...lot.vertices, [-28.1, -59.1]] }));
});

test('WorldCover conserva el año y la consulta de suelo declara el punto vecino', () => {
  const wc = sheetSection('sustentabilidad', { status: 'recibido', payload: { data: { deforestation: { worldcover: [{ year: 2020, trees: .8 }, { year: 2021, trees: 0, grass: .6, crops: .4 }] } } } });
  assert.equal(wc.readings[0].value, 0);
  assert.equal(wc.readings[1].value, 60);
  assert.equal(wc.readings[0].date, 'WorldCover 2021');
  const soil = sheetSection('suelo', { status: 'recibido', payload: { point_used: { lat: -28, lon: -59, note: 'vecino a ~500 m al norte' }, data: {} } });
  assert.match(soil.note, /vecino/);
  assert.equal(soil.state, 'sin dato');
});
