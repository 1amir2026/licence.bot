import fs from "fs";
import path from "path";
import sharp from "sharp";
import archiver from "archiver";

const input = process.argv[2];
const output = process.argv[3];

const DEPTH = 0.8;
const ALPHA_THRESHOLD = 40;

const { data, info } = await sharp(input)
  .ensureAlpha()
  .raw()
  .toBuffer({ resolveWithObject: true });

function isSolid(x, y) {
  if (x < 0 || y < 0 || x >= info.width || y >= info.height)
    return false;

  const i = (y * info.width + x) * 4;
  return data[i + 3] > ALPHA_THRESHOLD;
}

const vertices = [];
const uvs = [];
const faces = [];

let vertexIndex = 1;
let uvIndex = 1;

function addQuad(a, b, c, d, ta, tb, tc, td) {
  faces.push(`f ${a}/${ta} ${b}/${tb} ${c}/${tc}`);
  faces.push(`f ${a}/${ta} ${c}/${tc} ${d}/${td}`);
}

for (let y = 0; y < info.height; y++) {
  for (let x = 0; x < info.width; x++) {

    if (!isSolid(x, y)) continue;

    const px = x;
    const py = info.height - y - 1;

    const z0 = -DEPTH / 2;
    const z1 = DEPTH / 2;

    const vb = vertexIndex;
    const tb = uvIndex;

    vertices.push(`v ${px} ${py} ${z0}`);
    vertices.push(`v ${px + 1} ${py} ${z0}`);
    vertices.push(`v ${px + 1} ${py + 1} ${z0}`);
    vertices.push(`v ${px} ${py + 1} ${z0}`);

    vertices.push(`v ${px} ${py} ${z1}`);
    vertices.push(`v ${px + 1} ${py} ${z1}`);
    vertices.push(`v ${px + 1} ${py + 1} ${z1}`);
    vertices.push(`v ${px} ${py + 1} ${z1}`);

    const u1 = x / info.width;
    const u2 = (x + 1) / info.width;
    const v1 = (info.height - y - 1) / info.height;
    const v2 = (info.height - y) / info.height;

    uvs.push(`vt ${u1} ${v1}`);
    uvs.push(`vt ${u2} ${v1}`);
    uvs.push(`vt ${u2} ${v2}`);
    uvs.push(`vt ${u1} ${v2}`);

    // FRONT
    addQuad(
      vb+4, vb+5, vb+6, vb+7,
      tb, tb+1, tb+2, tb+3
    );

    // BACK
    addQuad(
      vb+1, vb+0, vb+3, vb+2,
      tb+1, tb, tb+3, tb+2
    );

    // LEFT
    addQuad(
      vb+0, vb+4, vb+7, vb+3,
      tb, tb, tb+3, tb+3
    );

    // RIGHT
    addQuad(
      vb+5, vb+1, vb+2, vb+6,
      tb+1, tb+1, tb+2, tb+2
    );

    // TOP
    addQuad(
      vb+3, vb+7, vb+6, vb+2,
      tb+3, tb+3, tb+2, tb+2
    );

    // BOTTOM
    addQuad(
      vb+0, vb+1, vb+5, vb+4,
      tb, tb+1, tb+1, tb
    );

    vertexIndex += 8;
    uvIndex += 4;
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

fs.copyFileSync(input, output.replace(".obj", ".png"));

const zipPath = output.replace(".obj", ".zip");

const archive = archiver("zip", {
  zlib: { level: 9 }
});

const stream = fs.createWriteStream(zipPath);

archive.pipe(stream);

archive.file(output, { name: `${baseName}.obj` });
archive.file(output.replace(".obj", ".mtl"), { name: `${baseName}.mtl` });
archive.file(output.replace(".obj", ".png"), { name: `${baseName}.png` });

await archive.finalize();

console.log(`✅ Exported (${info.width}x${info.height})`);
