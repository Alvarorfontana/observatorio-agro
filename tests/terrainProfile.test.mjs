import assert from "node:assert/strict";
import test from "node:test";
import { distanceM, profileAlong, sampleGrid } from "../src/lib/terrainProfile.ts";

// Grilla sintética: 100 x 100 celdas de 0,0001°, con un plano inclinado.
// La cota depende de la columna y, en menor medida, de la fila: así se puede
// verificar la interpolación y el signo de la pendiente.
const nx = 100, ny = 100, west = 0, north = 0.01, rx = 0.0001, ry = 0.0001;
const z = new Float32Array(nx * ny);
for (let y = 0; y < ny; y++) {
  for (let x = 0; x < nx; x++) z[y * nx + x] = 1000 + x + y * 0.5;
}
const plano = { nx, ny, west, north, rx, ry, z };

const centro = (x, y) => [north - (y + 0.5) * ry, west + (x + 0.5) * rx];

test("distanceM mide un grado de latitud como ~111 km", () => {
  const d = distanceM([0, 0], [1, 0]);
  assert.ok(d > 111_000 && d < 111_400, `distancia inesperada: ${d}`);
});

test("sampleGrid interpola el valor exacto en el centro de una celda", () => {
  const [lat, lon] = centro(10, 20);
  assert.equal(sampleGrid(plano, lat, lon), 1000 + 10 + 20 * 0.5);
});

test("profileAlong devuelve largo, extremos y desnivel del plano", () => {
  const a = centro(0, 50), b = centro(99, 50);
  const p = profileAlong(plano, a, b);
  assert.ok(p, "el perfil no debería ser null");
  assert.equal(p.points.length >= 160, true);
  assert.ok(Math.abs(p.lengthM - 1102) < 60, `largo inesperado: ${p.lengthM}`);
  assert.ok(Math.abs(p.points[0].z - (1000 + 0 + 25)) < 0.01);
  assert.ok(Math.abs(p.points[p.points.length - 1].z - (1000 + 99 + 25)) < 0.01);
  assert.ok(Math.abs(p.reliefM - 99) < 0.6, `desnivel inesperado: ${p.reliefM}`);
  assert.ok(p.slopePct > 8 && p.slopePct < 10, `pendiente inesperada: ${p.slopePct}`);
  assert.equal(p.validPct, 100);
});

test("profileAlong ignora las celdas sin dato y avisa qué parte quedó vacía", () => {
  const conHueco = { ...plano, z: Float32Array.from(z) };
  for (let y = 0; y < ny; y++) {
    for (let x = 60; x < 80; x++) conHueco.z[y * nx + x] = NaN;
  }
  const p = profileAlong(conHueco, centro(0, 50), centro(99, 50));
  assert.ok(p);
  assert.ok(p.validPct > 70 && p.validPct < 85, `cobertura inesperada: ${p.validPct}`);
  assert.ok(Number.isFinite(p.minZ) && Number.isFinite(p.maxZ));
});

test("profileAlong devuelve null si los puntos coinciden", () => {
  const a = centro(4, 4);
  assert.equal(profileAlong(plano, a, a), null);
});
