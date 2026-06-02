import fs from "fs";
import path from "path";
import sharp from "sharp";
import archiver from "archiver";

const input = process.argv[2];
const output = process.argv[3];

if (!input || !output) {
  console.log("Usage: node item3d.mjs input.png output.obj");
  process.exit(1);
}

const DEPTH = 0.8;
const ALPHA_THRESHOLD = 40;

const { data, info } = await sharp(input)
  .ensureAlpha()
  .raw()
  .toBuffer({ resolveWithObject: true });

const WIDTH = info.width;
const HEIGHT = info.height;

function isSolid(x, y) {
  if (x < 0 || y < 0 || x >= WIDTH || y >= HEIGHT)
    return false;

  const i = (y * WIDTH + x) * 4;
  return data[i + 3] > ALPHA_THRESHOLD;
}

// ---------------- OBJ BUFFERS ----------------

const vertices = [];
const uvs = [];
const faces = [];

let vertexIndex = 1;
let uvIndex = 1;

// ---------------- HELPERS ----------------

function addVertex(x, y, z) {
  vertices.push(`v ${x} ${y} ${z}`);
  return vertexIndex++;
}

function addUV(u, v) {
  uvs.push(`vt ${u} ${v}`);
  return uvIndex++;
}

function addTri(v1, t1, v2, t2, v3, t3) {
  faces.push(
    `f ${v1}/${t1} ${v2}/${t2} ${v3}/${t3}`
  );
}

function addQuad(v1, v2, v3, v4, t1, t2, t3, t4) {

  addTri(v1,t1,v2,t2,v3,t3);
  addTri(v1,t1,v3,t3,v4,t4);
}

// ---------------- FACE BUILDER ----------------

function buildVoxel(x, y) {

  const px = x;
  const py = HEIGHT - y - 1;

  const z0 = -DEPTH / 2;
  const z1 = DEPTH / 2;

  const v000 = addVertex(px,     py,     z0);
  const v100 = addVertex(px + 1, py,     z0);
  const v110 = addVertex(px + 1, py + 1, z0);
  const v010 = addVertex(px,     py + 1, z0);

  const v001 = addVertex(px,     py,     z1);
  const v101 = addVertex(px + 1, py,     z1);
  const v111 = addVertex(px + 1, py + 1, z1);
  const v011 = addVertex(px,     py + 1, z1);

  const u1 = x / WIDTH;
  const u2 = (x + 1) / WIDTH;

  const vv1 = (HEIGHT - y - 1) / HEIGHT;
  const vv2 = (HEIGHT - y) / HEIGHT;

  const t1 = addUV(u1, vv1);
  const t2 = addUV(u2, vv1);
  const t3 = addUV(u2, vv2);
  const t4 = addUV(u1, vv2);

  // FRONT

  addQuad(
    v001,v101,v111,v011,
    t1,t2,t3,t4
  );

  // BACK

  addQuad(
    v100,v000,v010,v110,
    t2,t1,t4,t3
  );

  // LEFT

  if (!isSolid(x - 1, y)) {

    addQuad(
      v000,v001,v011,v010,
      t1,t1,t4,t4
    );
  }

  // RIGHT

  if (!isSolid(x + 1, y)) {

    addQuad(
      v101,v100,v110,v111,
      t2,t2,t3,t3
    );
  }

  // TOP

  if (!isSolid(x, y - 1)) {

    addQuad(
      v010,v011,v111,v110,
      t4,t4,t3,t3
    );
  }

  // BOTTOM

  if (!isSolid(x, y + 1)) {

    addQuad(
      v000,v100,v101,v001,
      t1,t2,t2,t1
    );
  }
}

// ---------------- BUILD ----------------

for (let y = 0; y < HEIGHT; y++) {

  for (let x = 0; x < WIDTH; x++) {

    if (!isSolid(x, y))
      continue;

    buildVoxel(x, y);
  }
}

const baseName = path.basename(output, ".obj");

const objContent =
`mtllib ${baseName}.mtl
usemtl Material

${vertices.join("\n")}

${uvs.join("\n")}

${faces.join("\n")}
`;

fs.writeFileSync(output, objContent);

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

const archive = archiver(
  "zip",
  { zlib: { level: 9 } }
);

const stream = fs.createWriteStream(
  output.replace(".obj", ".zip")
);

archive.pipe(stream);

archive.file(output, {
  name: `${baseName}.obj`
});

archive.file(
  output.replace(".obj",".mtl"),
  {
    name: `${baseName}.mtl`
  }
);

archive.file(
  output.replace(".obj",".png"),
  {
    name: `${baseName}.png`
  }
);

await archive.finalize();

console.log("✅ Minecraft Voxel Exported");
