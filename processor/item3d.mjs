import fs from "fs";
import path from "path";
import sharp from "sharp";
import archiver from "archiver";

const input = process.argv[2];
const output = process.argv[3];
const DEPTH = 0.8;           // ضخامت مناسب
const OVERLAP = 0.02;        // کمی هم‌پوشانی برای حذف gap

const { data, info } = await sharp(input)
  .ensureAlpha()
  .raw()
  .toBuffer({ resolveWithObject: true });

let vertices = [];
let uvs = [];
let faces = [];
let vIndex = 1;

function isSolid(x, y) {
  if (x < 0 || y < 0 || x >= info.width || y >= info.height) return false;
  const i = (y * info.width + x) * 4;
  return data[i + 3] > 40;
}

for (let y = 0; y < info.height; y++) {
  for (let x = 0; x < info.width; x++) {
    if (!isSolid(x, y)) continue;

    const px = x - OVERLAP;
    const py = info.height - y - 1 - OVERLAP;
    const pz0 = -DEPTH / 2;
    const pz1 = DEPTH / 2;

    const vBase = vIndex;
    const uvBase = uvs.length + 1;

    // Vertices با کمی overlap
    vertices.push(`v ${px}          ${py}          ${pz0}`);
    vertices.push(`v ${px + 1 + OVERLAP*2} ${py}          ${pz0}`);
    vertices.push(`v ${px + 1 + OVERLAP*2} ${py + 1 + OVERLAP*2} ${pz0}`);
    vertices.push(`v ${px}          ${py + 1 + OVERLAP*2} ${pz0}`);

    vertices.push(`v ${px}          ${py}          ${pz1}`);
    vertices.push(`v ${px + 1 + OVERLAP*2} ${py}          ${pz1}`);
    vertices.push(`v ${px + 1 + OVERLAP*2} ${py + 1 + OVERLAP*2} ${pz1}`);
    vertices.push(`v ${px}          ${py + 1 + OVERLAP*2} ${pz1}`);

    // UVs
    const u1 = x / info.width;
    const u2 = (x + 1) / info.width;
    const v1 = (info.height - y - 1) / info.height;
    const v2 = (info.height - y) / info.height;

    uvs.push(`vt ${u1} ${v1}`);
    uvs.push(`vt ${u2} ${v1}`);
    uvs.push(`vt ${u2} ${v2}`);
    uvs.push(`vt ${u1} ${v2}`);

    const f = (a,b,c,d,uva,uvb,uvc,uvd) => 
      `f ${vBase+a}/${uvBase+uva} ${vBase+b}/${uvBase+uvb} ${vBase+c}/${uvBase+uvc} ${vBase+d}/${uvBase+uvd}`;

    faces.push(f(0,1,2,3,0,1,2,3)); // bottom
    faces.push(f(4,5,6,7,0,1,2,3)); // top

    if (!isSolid(x-1, y)) faces.push(f(0,4,7,3,0,0,3,3));
    if (!isSolid(x+1, y)) faces.push(f(1,2,6,5,1,2,2,1));
    if (!isSolid(x, y-1)) faces.push(f(3,2,6,7,3,2,2,3));
    if (!isSolid(x, y+1)) faces.push(f(0,1,5,4,0,1,1,0));

    vIndex += 8;
  }
}

const baseName = path.basename(output, ".obj");

const objContent = `mtllib ${baseName}.mtl
usemtl Material

${vertices.join("\n")}
${uvs.join("\n")}
${faces.join("\n")}`;

fs.writeFileSync(output, objContent);

fs.writeFileSync(output.replace(".obj", ".mtl"), 
`newmtl Material
Ka 1 1 1
Kd 1 1 1
Ks 0 0 0
d 1
illum 2
map_Kd ${baseName}.png
`);

fs.copyFileSync(input, output.replace(".obj", ".png"));

// ZIP
const zipPath = output.replace(".obj", ".zip");
const archive = archiver("zip", { zlib: { level: 9 } });
const stream = fs.createWriteStream(zipPath);
archive.pipe(stream);

archive.file(output, { name: `${baseName}.obj` });
archive.file(output.replace(".obj", ".mtl"), { name: `${baseName}.mtl` });
archive.file(output.replace(".obj", ".png"), { name: `${baseName}.png` });

await archive.finalize();

console.log(`✅ Exported | Depth: ${DEPTH} | Overlap: ${OVERLAP}`);
