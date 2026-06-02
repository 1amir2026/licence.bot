import fs from "fs";
import path from "path";
import sharp from "sharp";
import archiver from "archiver";

const input = process.argv[2];
const output = process.argv[3];
const DEPTH = 0.4; // ضخامت کمتر برای آیتم‌های ماینکرافت

const { data, info } = await sharp(input)
  .ensureAlpha()
  .raw()
  .toBuffer({ resolveWithObject: true });

let vertices = [];
let uvs = [];
let faces = [];
let vIndex = 1;
let uvIndex = 1;

function isSolid(x, y) {
  if (x < 0 || y < 0 || x >= info.width || y >= info.height) return false;
  const i = (y * info.width + x) * 4;
  return data[i + 3] > 30; // کمی tolerance برای alpha
}

function addFace(v1, v2, v3, v4, uv1, uv2, uv3, uv4) {
  faces.push(`f ${v1}/${uv1} ${v2}/${uv2} ${v3}/${uv3} ${v4}/${uv4}`);
}

for (let y = 0; y < info.height; y++) {
  for (let x = 0; x < info.width; x++) {
    if (!isSolid(x, y)) continue;

    const px = x;
    const py = info.height - y;
    const pz0 = 0;
    const pz1 = DEPTH;

    const vBase = vIndex;
    const uvBase = uvIndex;

    // 8 vertex برای هر куб
    vertices.push(`v ${px} ${py} ${pz0}`);
    vertices.push(`v ${px + 1} ${py} ${pz0}`);
    vertices.push(`v ${px + 1} ${py + 1} ${pz0}`);
    vertices.push(`v ${px} ${py + 1} ${pz0}`);

    vertices.push(`v ${px} ${py} ${pz1}`);
    vertices.push(`v ${px + 1} ${py} ${pz1}`);
    vertices.push(`v ${px + 1} ${py + 1} ${pz1}`);
    vertices.push(`v ${px} ${py + 1} ${pz1}`);

    // UVs (مشترک برای همه فیس‌ها)
    uvs.push(`vt 0 0`);
    uvs.push(`vt 1 0`);
    uvs.push(`vt 1 1`);
    uvs.push(`vt 0 1`);
    uvIndex += 4;

    // Faces با UV یکسان
    const u1 = uvBase, u2 = uvBase+1, u3 = uvBase+2, u4 = uvBase+3;

    // Front, Back, Left, Right, Top, Bottom
    addFace(vBase, vBase+1, vBase+2, vBase+3, u1, u2, u3, u4);     // bottom
    addFace(vBase+4, vBase+5, vBase+6, vBase+7, u1, u2, u3, u4);   // top

    // فقط فیس‌هایی که همسایه خالی دارند
    if (!isSolid(x-1, y)) addFace(vBase, vBase+4, vBase+7, vBase+3, u1, u1, u4, u4);
    if (!isSolid(x+1, y)) addFace(vBase+1, vBase+2, vBase+6, vBase+5, u2, u3, u3, u2);
    if (!isSolid(x, y-1)) addFace(vBase+3, vBase+2, vBase+6, vBase+7, u4, u3, u3, u4);
    if (!isSolid(x, y+1)) addFace(vBase, vBase+1, vBase+5, vBase+4, u1, u2, u2, u1);

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

// MTL
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

console.log(`✅ Done: ${info.width}x${info.height} pixels → ${zipPath}`);
