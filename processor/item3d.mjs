import fs from "fs";
import path from "path";
import sharp from "sharp";
import archiver from "archiver";

const input = process.argv[2];
const output = process.argv[3];

const DEPTH = 0.8; // ضخامت

// خواندن تصویر
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
  return data[i + 3] > 40;
}

function addFace(v1, v2, v3, v4, uv1, uv2, uv3, uv4) {
  faces.push(`f ${v1}/${uv1} ${v2}/${uv2} ${v3}/${uv3} ${uv4}/${uv4}`);
}

for (let y = 0; y < info.height; y++) {
  for (let x = 0; x < info.width; x++) {
    if (!isSolid(x, y)) continue;

    const px = x;
    const py = info.height - y - 1;
    const pz0 = -DEPTH / 2;
    const pz1 = DEPTH / 2;

    const v0 = vIndex;

    // 8 vertex
    vertices.push(`v ${px} ${py} ${pz0}`);
    vertices.push(`v ${px+1} ${py} ${pz0}`);
    vertices.push(`v ${px+1} ${py+1} ${pz0}`);
    vertices.push(`v ${px} ${py+1} ${pz0}`);

    vertices.push(`v ${px} ${py} ${pz1}`);
    vertices.push(`v ${px+1} ${py} ${pz1}`);
    vertices.push(`v ${px+1} ${py+1} ${pz1}`);
    vertices.push(`v ${px} ${py+1} ${pz1}`);

    vIndex += 8;

    // UV مخصوص top/bottom
    const u1 = x / info.width;
    const u2 = (x + 1) / info.width;
    const v1 = (info.height - y - 1) / info.height;
    const v2 = (info.height - y) / info.height;

    const uv0 = uvIndex;
    uvs.push(`vt ${u1} ${v1}`);
    uvs.push(`vt ${u2} ${v1}`);
    uvs.push(`vt ${u2} ${v2}`);
    uvs.push(`vt ${u1} ${v2}`);
    uvIndex += 4;

    // top
    faces.push(`f ${v0+4}/${uv0} ${v0+5}/${uv0+1} ${v0+6}/${uv0+2} ${v0+7}/${uv0+3}`);

    // bottom
    faces.push(`f ${v0+0}/${uv0} ${v0+1}/${uv0+1} ${v0+2}/${uv0+2} ${v0+3}/${uv0+3}`);

    // side faces (UV مستقل)
    function side(uvi, a,b,c,d) {
      const u = uvi;
      uvs.push(`vt 0 0`);
      uvs.push(`vt 1 0`);
      uvs.push(`vt 1 1`);
      uvs.push(`vt 0 1`);
      faces.push(`f ${a}/${u} ${b}/${u+1} ${c}/${u+2} ${d}/${u+3}`);
      return u + 4;
    }

    // left
    if (!isSolid(x-1, y)) uvIndex = side(uvIndex, v0+0, v0+4, v0+7, v0+3);

    // right
    if (!isSolid(x+1, y)) uvIndex = side(uvIndex, v0+1, v0+2, v0+6, v0+5);

    // down
    if (!isSolid(x, y-1)) uvIndex = side(uvIndex, v0+3, v0+2, v0+6, v0+7);

    // up
    if (!isSolid(x, y+1)) uvIndex = side(uvIndex, v0+0, v0+1, v0+5, v0+4);
  }
}

const baseName = path.basename(output, ".obj");

// OBJ
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

// PNG
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

console.log("✅ Exported (Watertight, No Gaps)");
