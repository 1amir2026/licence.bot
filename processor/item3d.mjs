import fs from "fs";
import sharp from "sharp";

const input = process.argv[2];
const output = process.argv[3];

const { data, info } = await sharp(input)
    .ensureAlpha()
    .raw()
    .toBuffer({ resolveWithObject: true });

let vertices = [];
let faces = [];
let index = 1;

function cube(x, y, z) {
    const v = [
        [x, y, z],
        [x+1, y, z],
        [x+1, y+1, z],
        [x, y+1, z],
        [x, y, z+1],
        [x+1, y, z+1],
        [x+1, y+1, z+1],
        [x, y+1, z+1]
    ];

    v.forEach(p => vertices.push(`v ${p[0]} ${p[1]} ${p[2]}`));

    faces.push(`f ${index} ${index+1} ${index+2} ${index+3}`);
    faces.push(`f ${index+4} ${index+5} ${index+6} ${index+7}`);

    index += 8;
}

for (let y = 0; y < info.height; y++) {
    for (let x = 0; x < info.width; x++) {
        const i = (y * info.width + x) * 4;

        const alpha = data[i + 3];

        if (alpha > 0) {
            cube(x, info.height - y, 0);
        }
    }
}

fs.writeFileSync(
    output,
    vertices.join("\n") + "\n" + faces.join("\n")
);

console.log("OBJ created");