import fs from "fs";
import path from "path";
import sharp from "sharp";
import archiver from "archiver";
import { Potrace } from "potrace";
import earcut from "earcut";

const input = process.argv[2];
const output = process.argv[3];

if (!input || !output) {
  console.log("Usage: node item3d.mjs input.png output.obj");
  process.exit(1);
}

const DEPTH = 0.8;

const pngBuffer = await sharp(input)
  .ensureAlpha()
  .png()
  .toBuffer();

function trace(buffer) {
  return new Promise((resolve, reject) => {
    const potrace = new Potrace({
      threshold: 128,
      turdSize: 2,
      optCurve: true
    });

    potrace.loadImage(buffer, (err) => {
      if (err) return reject(err);
      resolve(potrace.getPathTag());
    });
  });
}

function parsePath(pathTag) {
  const d = pathTag.match(/d="([^"]+)"/)?.[1];
  if (!d) throw new Error("No SVG path");

  const pts = [];

  const tokens = d
    .replace(/[A-Za-z]/g, m => ` ${m} `)
    .trim()
    .split(/[\s,]+/);

  let i = 0;

  while (i < tokens.length) {
    const cmd = tokens[i++];

    if (cmd === "M" || cmd === "L") {
      const x = parseFloat(tokens[i++]);
      const y = parseFloat(tokens[i++]);
      pts.push([x, -y]);
    }

    if (cmd === "Z") break;
  }

  return pts;
}

const pathTag = await trace(pngBuffer);
const contour = parsePath(pathTag);

if (contour.length < 3) {
  throw new Error("Contour too small");
}

const vertices = [];
const uvs = [];
const faces = [];

function addVertex(x, y, z) {
  vertices.push([x, y, z]);
  return vertices.length;
}

function addUV(u, v) {
  uvs.push([u, v]);
  return uvs.length;
}

const flat = [];

for (const [x, y] of contour) {
  flat.push(x, y);
}

const tris = earcut(flat);

const front = [];
const back = [];

let minX = Infinity;
let maxX = -Infinity;
let minY = Infinity;
let maxY = -Infinity;

for (const [x, y] of contour) {
  minX = Math.min(minX, x);
  maxX = Math.max(maxX, x);
  minY = Math.min(minY, y);
  maxY = Math.max(maxY, y);
}

for (const [x, y] of contour) {

  const u = (x - minX) / (maxX - minX || 1);
  const v = (y - minY) / (maxY - minY || 1);

  const uv = addUV(u, v);

  front.push({
    v: addVertex(x, y, DEPTH / 2),
    uv
  });

  back.push({
    v: addVertex(x, y, -DEPTH / 2),
    uv
  });
}

for (let i = 0; i < tris.length; i += 3) {

  const a = tris[i];
  const b = tris[i + 1];
  const c = tris[i + 2];

  faces.push([
    front[a].v, front[a].uv,
    front[b].v, front[b].uv,
    front[c].v, front[c].uv
  ]);

  faces.push([
    back[c].v, back[c].uv,
    back[b].v, back[b].uv,
    back[a].v, back[a].uv
  ]);
}

for (let i = 0; i < contour.length; i++) {

  const j = (i + 1) % contour.length;

  const a = front[i];
  const b = front[j];
  const c = back[j];
  const d = back[i];

  faces.push([
    a.v, a.uv,
    b.v, b.uv,
    c.v, c.uv
  ]);

  faces.push([
    a.v, a.uv,
    c.v, c.uv,
    d.v, d.uv
  ]);
}

const baseName = path.basename(output, ".obj");

let obj = `mtllib ${baseName}.mtl\nusemtl Material\n\n`;

for (const v of vertices) {
  obj += `v ${v[0]} ${v[1]} ${v[2]}\n`;
}

obj += "\n";

for (const uv of uvs) {
  obj += `vt ${uv[0]} ${uv[1]}\n`;
}

obj += "\n";

for (const f of faces) {
  obj += `f ${f[0]}/${f[1]} ${f[2]}/${f[3]} ${f[4]}/${f[5]}\n`;
}

fs.writeFileSync(output, obj);

fs.writeFileSync(
  output.replace(".obj", ".mtl"),
`newmtl Material
Ka 1 1 1
Kd 1 1 1
Ks 0 0 0
d 1
illum 2
map_Kd ${baseName}.png
`
);

fs.copyFileSync(
  input,
  output.replace(".obj", ".png")
);

const archive = archiver("zip", {
  zlib: { level: 9 }
});

const stream = fs.createWriteStream(
  output.replace(".obj", ".zip")
);

archive.pipe(stream);

archive.file(output, {
  name: `${baseName}.obj`
});

archive.file(
  output.replace(".obj", ".mtl"),
  { name: `${baseName}.mtl` }
);

archive.file(
  output.replace(".obj", ".png"),
  { name: `${baseName}.png` }
);

await archive.finalize();

console.log("✅ Extruded OBJ exported");
