import fs from "fs";
import path from "path";

// ====================== HELPERS ======================

// چرخش یک نقطه حول محور X/Y/Z
function rotatePoint([x, y, z], origin, axis, angleDeg) {
    const angle = -angleDeg * Math.PI / 180;
    let [ox, oy, oz] = origin;

    let px = x - ox;
    let py = y - oy;
    let pz = z - oz;

    let rx = px, ry = py, rz = pz;

    if (axis === "x") {
        ry = py * Math.cos(angle) - pz * Math.sin(angle);
        rz = py * Math.sin(angle) + pz * Math.cos(angle);
    }
    if (axis === "y") {
        rx = px * Math.cos(angle) + pz * Math.sin(angle);
        rz = -px * Math.sin(angle) + pz * Math.cos(angle);
    }
    if (axis === "z") {
        rx = px * Math.cos(angle) - py * Math.sin(angle);
        ry = px * Math.sin(angle) + py * Math.cos(angle);
    }

    return [rx + ox, ry + oy, rz + oz];
}

// تبدیل مختصات ماینکرافت به OBJ (مقیاس 1/16)
function mcToObj([x, y, z]) {
    return [
        -(x - 8) / 16,
        (z - 8) / 16,
        (y - 8) / 16
    ];
}

// ساخت مکعب از from/to
function buildCube(from, to, rotation) {
    const verts = [
        [from[0], to[1], from[2]],
        [to[0], to[1], from[2]],
        [to[0], from[1], from[2]],
        [from[0], from[1], from[2]],
        [from[0], to[1], to[2]],
        [to[0], to[1], to[2]],
        [to[0], from[1], to[2]],
        [from[0], from[1], to[2]],
    ];

    const rotated = verts.map(v =>
        rotation.angle !== 0
            ? rotatePoint(v, rotation.origin, rotation.axis, rotation.angle)
            : v
    );

    const finalVerts = rotated.map(mcToObj);

    const faces = [
        [0, 1, 2, 3], // north
        [5, 4, 7, 6], // south
        [1, 0, 4, 5], // up
        [7, 6, 2, 3], // down
        [4, 0, 3, 7], // west
        [1, 5, 6, 2]  // east
    ];

    return { verts: finalVerts, faces };
}

// ====================== MAIN ======================

if (process.argv.length < 4) {
    console.error("Usage: node json_to_obj.mjs input.json output.obj");
    process.exit(1);
}

const inputJson = process.argv[2];
const outputObj = process.argv[3];
const outputMtl = outputObj.replace(".obj", ".mtl");

const data = JSON.parse(fs.readFileSync(inputJson, "utf8"));

let obj = "";
let mtl = "";
let vCount = 1;

const textureName = "texture.png";

mtl += `newmtl material0\n`;
mtl += `map_Kd ${textureName}\n\n`;

obj += `mtllib ${path.basename(outputMtl)}\n`;
obj += `usemtl material0\n`;

for (const el of data.elements) {
    const from = el.from;
    const to = el.to;

    const rotation = el.rotation || { angle: 0, axis: "y", origin: [8, 8, 8] };

    const cube = buildCube(from, to, rotation);

    for (const v of cube.verts) {
        obj += `v ${v[0]} ${v[1]} ${v[2]}\n`;
    }

    for (const f of cube.faces) {
        obj += `f ${f[0] + vCount} ${f[1] + vCount} ${f[2] + vCount} ${f[3] + vCount}\n`;
    }

    vCount += 8;
}

fs.writeFileSync(outputObj, obj);
fs.writeFileSync(outputMtl, mtl);

console.log("✔ JSON → OBJ Done!");
