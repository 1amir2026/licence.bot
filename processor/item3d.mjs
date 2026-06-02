import fs from "fs";
import path from "path";
import sharp from "sharp";
import archiver from "archiver";

const DEPTH = 1.5;
const input = process.argv[2];
const output = process.argv[3];

const { data, info } = await sharp(input)
  .ensureAlpha()
  .raw()
  .toBuffer({ resolveWithObject: true });

let vertices = [];
let uvs = [];
let faces = [];
let index = 1;
let uvIndex = 1;

function isSolid(x, y) {
  if (x < 0 || y < 0 || x >= info.width || y >= info.height) return false;
  const i = (y * info.width + x) * 4;
  return data[i + 3] > 0;
}

function addCube(x, y) {
  const z0 = 0;
  const z1 = DEPTH;
  const start = index;
  const uvStart = uvIndex;

  // Vertices
  const v = [
    [x, y, z0], [x + 1, y, z0], [x + 1, y + 1, z0], [x, y + 1, z0],
    [x, y, z1], [x + 1, y, z1], [x + 1, y + 1, z1], [x, y + 1, z1]
  ];

  v.forEach(p => vertices.push(`v ${p[0]} ${p[1]} ${p[2]}`));

  // UVs (simple mapping for each face)
  uvs.push(`vt 0 0`);
  uvs.push(`vt 1 0`);
  uvs.push(`vt 1 1`);
  uvs.push(`vt 0 1`);
  uvIndex += 4;

  // Faces with UVs
  const f = (a, b, c, d) => `f ${a}/${uvStart} ${b}/${uvStart+1} ${c}/${uvStart+2} ${d}/${uvStart+3}`;

  // front
  faces.push(f(start, start+1, start+2, start+3));

  // back
  faces.push(f(start+4, start+5, start+6, start+7));

  // left
  if (!isSolid(x - 1, info.height - y - 1)) {
    faces.push(`f ${start}/${uvStart} ${start+4}/${uvStart} ${start+7}/${uvStart+3} ${start+3}/${uvStart+3}`);
  }

  // right
  if (!isSolid(x + 1, info.height - y - 1)) {
    faces.push(`f ${start+1}/${uvStart+1} ${start+5}/${uvStart+1} ${start+6}/${uvStart+2} ${start+2}/${uvStart+2}`);
  }

  // top & bottom (simplified)
  faces.push(f(start+3, start+2, start+6, start+7)); // top
  faces.push(f(start, start+1, start+5, start+4));   // bottom

  index += 8;
}

for (let y = 0; y < info.height; y++) {
  for (let x = 0; x < info.width; x++) {
    if (data[(y * info.width + x) * 4 + 3] > 0) {
      addCube(x, info.height - y);
    }
  }
}

const baseName = path.basename(output, ".obj");

const objContent = 
`mtllib ${baseName}.mtl
usemtl Material

${vertices.join("\n")}
${uvs.join("\n")}
${faces.join("\n")}`;

fs.writeFileSync(output, objContent);

// MTL File
const mtlPath = output.replace(".obj", ".mtl");
fs.writeFileSync(mtlPath, 
`newmtl Material
Ka 1.000 1.000 1.000
Kd 1.000 1.000 1.000
Ks 0.000 0.000 0.000
d 1.0
illum 2
map_Kd ${baseName}.png
`);

const pngOutput = output.replace(".obj", ".png");
fs.copyFileSync(input, pngOutput);

// ZIP
const zipPath = output.replace(".obj", ".zip");
const archive = archiver("zip", { zlib: { level: 9 } });
const stream = fs.createWriteStream(zipPath);

archive.pipe(stream);
archive.file(output, { name: `${baseName}.obj` });
archive.file(mtlPath, { name: `${baseName}.mtl` });
archive.file(pngOutput, { name: `${baseName}.png` });

await archive.finalize();
console.log("✅ ZIP created with UVs:", zipPath);
