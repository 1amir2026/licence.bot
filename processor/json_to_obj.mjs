import fs from "fs";
import path from "path";

// ====================== LOAD MODEL WITH PARENT ======================

function loadModel(filePath, visited = new Set()) {
    if (visited.has(filePath)) return { elements: [], textures: {} };
    visited.add(filePath);

    const raw = JSON.parse(fs.readFileSync(filePath, "utf8"));

    let elements = raw.elements || [];
    let textures = raw.textures || {};

    if (raw.parent) {
        let parentPath;

        if (raw.parent.includes(":")) {
            const [ns, p] = raw.parent.split(":");
            parentPath = path.join("resourcepack/assets", ns, "models", p + ".json");
        } else {
            parentPath = path.join(path.dirname(filePath), raw.parent + ".json");
        }

        if (fs.existsSync(parentPath)) {
            const parent = loadModel(parentPath, visited);

            // child overwrites parent
            elements = elements.length ? elements : parent.elements;
            textures = { ...parent.textures, ...textures };
        }
    }

    return { elements, textures };
}

// ====================== ROTATION ======================

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

function mcToObj([x, y, z]) {
    return [
        -(x - 8) / 16,
        (z - 8) / 16,
        (y - 8) / 16
    ];
}

// ====================== BUILD CUBE ======================

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

const inputJson = process.argv[2];
const outputObj = process.argv[3];
const outputMtl = outputObj.replace(".obj", ".mtl");

const { elements, textures } = loadModel(inputJson);

if (!elements.length) {
    console.error("❌ No elements found. Model is empty.");
    process.exit(1);
}

let obj = "";
let mtl = "";
let vCount = 1;

mtl += `newmtl material0\n`;
mtl += `map_Kd texture.png\n\n`;

obj += `mtllib ${path.basename(outputMtl)}\n`;
obj += `usemtl material0\n`;

for (const el of elements) {
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
