import fs from "fs";
import sharp from "sharp";

const DEPTH = 0.2;
const input = process.argv[2];
const output = process.argv[3];

const { data, info } = await sharp(input)
  .ensureAlpha()
  .raw()
  .toBuffer({ resolveWithObject: true });

let vertices = [];
let faces = [];
let index = 1;

function addCube(x, y) {
  const z0 = 0;
  const z1 = DEPTH;

  const start = index;

  const v = [
    [x, y, z0],
    [x + 1, y, z0],
    [x + 1, y + 1, z0],
    [x, y + 1, z0],

    [x, y, z1],
    [x + 1, y, z1],
    [x + 1, y + 1, z1],
    [x, y + 1, z1]
  ];

  v.forEach(p => vertices.push(`v ${p[0]} ${p[1]} ${p[2]}`));

  faces.push(`f ${start} ${start+1} ${start+2} ${start+3}`); // front
  faces.push(`f ${start+4} ${start+5} ${start+6} ${start+7}`); // back

  faces.push(`f ${start} ${start+4} ${start+7} ${start+3}`); // left
  faces.push(`f ${start+1} ${start+5} ${start+6} ${start+2}`); // right

  faces.push(`f ${start+3} ${start+2} ${start+6} ${start+7}`); // top
  faces.push(`f ${start} ${start+1} ${start+5} ${start+4}`); // bottom

  index += 8;
}

for (let y = 0; y < info.height; y++) {
  for (let x = 0; x < info.width; x++) {
    const i = (y * info.width + x) * 4;
    const alpha = data[i + 3];

    if (alpha > 0) {
      addCube(x, info.height - y);
    }
  }
}

fs.writeFileSync(
  output,
  vertices.join("\n") + "\n" + faces.join("\n")
);

console.log("OBJ created:", output);
