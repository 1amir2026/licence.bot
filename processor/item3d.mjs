import fs from "fs";
import path from "path";
import sharp from "sharp";
import archiver from "archiver";

const input = process.argv[2];
const output = process.argv[3];

const DEPTH = 0.8;
const OVERLAP = 0;
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

function addVertex(x, y, z) {
  vertices.push(`v ${x} ${y} ${z}`);
}

function addUV(u, v) {
  uvs.push(`vt ${u} ${v}`);
}

function quadToTriangles(v1,v2,v3,v4, t1,t2,t3,t4) {

  faces.push(
    `f ${v1}/${t1} ${v2}/${t2} ${v3}/${t3}`
  );

  faces.push(
    `f ${v1}/${t1} ${v3}/${t3} ${v4}/${t4}`
  );
}

for (let y = 0; y < info.height; y++) {

  for (let x = 0; x < info.width; x++) {

    if (!isSolid(x, y))
      continue;

const px = x;
const py = info.height - y - 1;

const pz0 = -DEPTH / 2;
const pz1 = DEPTH / 2;

vertices.push(`v ${px} ${py} ${pz0}`);
vertices.push(`v ${px + 1} ${py} ${pz0}`);
vertices.push(`v ${px + 1} ${py + 1} ${pz0}`);
vertices.push(`v ${px} ${py + 1} ${pz0}`);

vertices.push(`v ${px} ${py} ${pz1}`);
vertices.push(`v ${px + 1} ${py} ${pz1}`);
vertices.push(`v ${px + 1} ${py + 1} ${pz1}`);
vertices.push(`v ${px} ${py + 1} ${pz1}`);

    const u1 = x / info.width;
    const u2 = (x + 1) / info.width;

    const v1 = (info.height - y - 1) / info.height;
    const v2 = (info.height - y) / info.height;

    addUV(u1, v1);
    addUV(u2, v1);
    addUV(u2, v2);
    addUV(u1, v2);

    quadToTriangles(
      vb+4, vb+5, vb+6, vb+7,
      tb, tb+1, tb+2, tb+3
    );

    quadToTriangles(
      vb+0, vb+3, vb+2, vb+1,
      tb, tb+3, tb+2, tb+1
    );

    if (!isSolid(x - 1, y)) {
      quadToTriangles(
        vb+0, vb+4, vb+7, vb+3,
        tb, tb, tb+3, tb+3
      );
    }

    if (!isSolid(x + 1, y)) {
      quadToTriangles(
        vb+1, vb+2, vb+6, vb+5,
        tb+1, tb+2, tb+2, tb+1
      );
    }

    if (!isSolid(x, y - 1)) {
      quadToTriangles(
        vb+3, vb+7, vb+6, vb+2,
        tb+3, tb+3, tb+2, tb+2
      );
    }

    if (!isSolid(x, y + 1)) {
      quadToTriangles(
        vb+0, vb+1, vb+5, vb+4,
        tb, tb+1, tb+1, tb
      );
    }

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

fs.copyFileSync(
  input,
  output.replace(".obj", ".png")
);

const zipPath = output.replace(".obj", ".zip");

const archive = archiver("zip", {
  zlib: { level: 9 }
});

const stream = fs.createWriteStream(zipPath);

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

console.log(
  `✅ Exported (${info.width}x${info.height})`
);
