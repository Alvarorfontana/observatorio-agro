import assert from "node:assert/strict";
import test from "node:test";
import { parseDXF, readLotFile } from "../src/dashboard/lotFiles.ts";

function entity(type, groups) {
  return [["0", type], ...groups.map(([code, value]) => [String(code), String(value)])].flat();
}

function lwPolyline(layer, points, flags = 1) {
  return entity("LWPOLYLINE", [[8, layer], [90, points.length], [70, flags], ...points.flatMap(([x, y]) => [[10, x], [20, y]])]);
}

function dxf(...entities) {
  return ["0", "SECTION", "2", "ENTITIES", ...entities.flat(), "0", "ENDSEC", "0", "EOF"].join("\n");
}

const square = [[-59.01, -28.51], [-58.99, -28.51], [-58.99, -28.49], [-59.01, -28.49]];

test("requires an explicit CRS and coordinate units", () => {
  assert.throws(() => parseDXF(dxf(lwPolyline("Potrero A", square)), "campo"), /Elegí el CRS/);
  assert.throws(() => parseDXF(dxf(lwPolyline("Potrero A", square)), "campo", "EPSG:4326"), /unidades/);
});

test("imports named closed 2D polylines as longitude/latitude polygons", () => {
  const result = parseDXF(dxf(lwPolyline("Potrero A", square)), "campo", "EPSG:4326", "degrees");
  assert.equal(result.lots.length, 1);
  assert.equal(result.lots[0].name, "Potrero A");
  assert.deepEqual(result.lots[0].polygon[0], [-28.51, -59.01]);
  assert.deepEqual(result.warnings, []);
});

test("uses a fallback name for layer 0 and disambiguates duplicate layer names", () => {
  const result = parseDXF(dxf(lwPolyline("0", square), lwPolyline("Potrero A", square), lwPolyline("Potrero A", square)), "campo", "EPSG:4326", "degrees");
  assert.deepEqual(result.lots.map(lot => lot.name), ["campo", "Potrero A", "Potrero A (2)"]);
});

test("reports open, curved, and unsupported entities without treating them as lots", () => {
  const open = lwPolyline("abierta", square, 0);
  const curved = entity("LWPOLYLINE", [[8, "curva"], [90, 4], [70, 1], [10, -59.01], [20, -28.51], [42, 0.5], [10, -58.99], [20, -28.51], [10, -58.99], [20, -28.49], [10, -59.01], [20, -28.49]]);
  const line = entity("LINE", [[8, "camino"], [10, -59], [20, -28.5], [11, -58.9], [21, -28.4]]);
  const result = parseDXF(dxf(lwPolyline("válida", square), open, curved, line), "campo", "EPSG:4326", "degrees");
  assert.equal(result.lots.length, 1);
  assert.match(result.warnings.join(" "), /abierta/);
  assert.match(result.warnings.join(" "), /curvos/);
  assert.match(result.warnings.join(" "), /no poligonal/);
});

test("rejects self-crossing polygons and incompatible CRS units", () => {
  const bowtie = [[-59.01, -28.51], [-58.99, -28.49], [-59.01, -28.49], [-58.99, -28.51]];
  assert.throws(() => parseDXF(dxf(lwPolyline("cruzado", bowtie)), "campo", "EPSG:4326", "degrees"), /No se encontró ningún polígono/);
  assert.throws(() => parseDXF(dxf(lwPolyline("metros", [[500000, 7000000], [500010, 7000000], [500010, 7000010]])), "campo", "EPSG:32721", "degrees"), /requiere coordenadas en metros o pies/);
});

test("converts UTM 21S around its central meridian", () => {
  const result = parseDXF(dxf(lwPolyline("UTM", [[500000, 7000000], [500010, 7000000], [500010, 7000010]])), "campo", "EPSG:32721", "meters");
  const [lat, lon] = result.lots[0].polygon[0];
  assert.ok(lat < -27 && lat > -28);
  assert.ok(Math.abs(lon + 57) < 1e-6);
});

test("converts legacy POLYLINE entities and distinguishes international from survey feet", () => {
  const meters = [[500000, 7000000], [500010, 7000000], [500010, 7000010]];
  const legacy = [
    entity("POLYLINE", [[8, "Límite"], [70, 1]]),
    ...meters.map(([x, y]) => entity("VERTEX", [[10, x], [20, y], [30, 0]])),
    entity("SEQEND", []),
  ];
  const projected = parseDXF(dxf(...legacy), "campo", "EPSG:32721", "meters");
  const inInternationalFeet = parseDXF(dxf(lwPolyline("Límite", meters.map(([x, y]) => [x / 0.3048, y / 0.3048]))), "campo", "EPSG:32721", "international-feet");
  const inSurveyFeet = parseDXF(dxf(lwPolyline("Límite", meters.map(([x, y]) => [x * 3937 / 1200, y * 3937 / 1200]))), "campo", "EPSG:32721", "us-survey-feet");
  assert.equal(projected.lots[0].name, "Límite");
  for (const converted of [inInternationalFeet, inSurveyFeet]) {
    assert.ok(Math.abs(converted.lots[0].polygon[0][0] - projected.lots[0].polygon[0][0]) < 1e-8);
    assert.ok(Math.abs(converted.lots[0].polygon[0][1] - projected.lots[0].polygon[0][1]) < 1e-8);
  }
});

test("rejects malformed and binary DXF input", () => {
  assert.throws(() => parseDXF("AutoCAD Binary DXF", "campo", "EPSG:4326", "degrees"), /DXF binario/);
  assert.throws(() => parseDXF("0\nSECTION\n2", "campo", "EPSG:4326", "degrees"), /pares de códigos/);
});

test("rejects oversized DXF files before parsing", async () => {
  const file = { name: "lotes.dxf", size: 25 * 1024 * 1024 + 1, text: async () => "" };
  await assert.rejects(() => readLotFile(file), /supera 25 MB/);
});
