import fs from "fs";
import path from "path";

// ====================== CONFIG ======================

// اگر ریسورس پک را جایی خاص نگه می‌داری، اینجا ست کن
const RESOURCE_ROOT = path.resolve("resourcepack"); 
// مثلا: ./resourcepack/assets/minecraft/models/...

// ====================== MODEL LOADER (با parent) ======================

function loadModel(filePath, visited = new Set()) {
    filePath = path.resolve(filePath);

    if (!fs.existsSync(filePath)) {
        console.error("Model file not found:", filePath);
        return { elements: [], textures: {} };
    }

    if (visited.has(filePath)) {
        console.error("Circular parent reference detected:", filePath);
        return { elements: [], textures: {} };
    }
    visited.add(filePath);

    const raw = JSON.parse(fs.readFileSync(filePath, "utf8"));

    let elements = raw.elements || [];
    let textures = raw.textures || {};

    if (raw.parent) {
        let parentPath;

        if (raw.parent.includes(":")) {
            // مثال: minecraft:block/cube_all
            const [ns, p] = raw.parent.split(":");
            parentPath = path.join(
                RESOURCE_ROOT,
                "assets",
                ns,
                "models",
                p + ".json"
            );
        } else {
            // parent نسبی کنار همین مدل
            parentPath = path.join(path.dirname(filePath), raw.parent + ".json");
        }

        if (fs.existsSync(parentPath)) {
            const parent = loadModel(parentPath, visited);

            // اگر child elements دارد، همان استفاده می‌شود
            if (!elements.length && parent.elements.length) {
                elements = parent.elements;
            }

            // textures: child روی parent override می‌شود
            textures = { ...parent.textures, ...textures };
        } else {
            console.warn("Parent model not found:", raw.parent, "->", parentPath);
        }
    }

    return { elements, textures };
}

// ====================== ریاضی روتیشن و تبدیل مختصات ======================

// دقیقا مطابق منطق MCprep: rotate_around + تبدیل به محور بلندر/OBJ
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
    } else if (axis === "y") {
        rx = px * Math.cos(angle) + pz * Math.sin(angle);
        rz = -px * Math.sin(angle) + pz * Math.cos(angle);
    } else if (axis === "z") {
        rx = px * Math.cos(angle) - py * Math.sin(angle);
        ry = px * Math.sin(angle) + py * Math.cos(angle);
    }

    return [rx + ox, ry + oy, rz + oz];
}

// تبدیل مختصات ماینکرافت به فضای OBJ (همان منطق MCprep)
function mcToObj([x, y, z]) {
    const offset = [8, 0, 8];
    const scale = [1 / 16, 1 / 16, 1 / 16];

    const nx = -(x - offset[0]) * scale[0];
    const ny = (z - offset[2]) * scale[2];
    const nz = (y - offset[1]) * scale[1];

    return [nx, ny, nz];
}

// ====================== ساخت مکعب از from/to ======================

function buildCube(from, to, rotation) {
    const vertsMc = [
        [from[0], to[1], from[2]],
        [to[0],   to[1], from[2]],
        [to[0],   from[1], from[2]],
        [from[0], from[1], from[2]],
        [from[0], to[1], to[2]],
        [to[0],   to[1], to[2]],
        [to[0],   from[1], to[2]],
        [from[0], from[1], to[2]],
    ];

    const rot = rotation || { angle: 0, axis: "y", origin: [8, 8, 8] };

    const rotated = vertsMc.map(v =>
        rot.angle !== 0
            ? rotatePoint(v, rot.origin, rot.axis, rot.angle)
            : v
    );

    const vertsObj = rotated.map(mcToObj);

    const faces = [
        [0, 1, 2, 3], // north
        [5, 4, 7, 6], // south
        [1, 0, 4, 5], // up
        [7, 6, 2, 3], // down
        [4, 0, 3, 7], // west
        [1, 5, 6, 2], // east
    ];

    return { verts: vertsObj, faces };
}

// ====================== MAIN ======================

if (process.argv.length < 4) {
    console.error("Usage: node json_to_obj.mjs input.json output.obj");
    process.exit(1);
}

const inputJson = process.argv[2];
const outputObj = process.argv[3];
const outputMtl = outputObj.replace(".obj", ".mtl");

const { elements, textures } = loadModel(inputJson);

if (!elements || !elements.length) {
    console.error("❌ No elements found in model (after resolving parents).");
    process.exit(1);
}

let obj = "";
let mtl = "";
let vCount = 1;

// متریال ساده – اسم تکسچر را بعداً در ZIP درست می‌کنی
const textureName = "texture.png";

mtl += `newmtl material0\n`;
mtl += `Kd 1.000 1.000 1.000\n`;
mtl += `Ka 0.000 0.000 0.000\n`;
mtl += `Ks 0.000 0.000 0.000\n`;
mtl += `d 1.0\n`;
mtl += `illum 1\n`;
mtl += `map_Kd ${textureName}\n\n`;

obj += `mtllib ${path.basename(outputMtl)}\n`;
obj += `usemtl material0\n`;

for (const el of elements) {
    if (!el.from || !el.to) continue;

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

fs.writeFileSync(outputObj, obj, "utf8");
fs.writeFileSync(outputMtl, mtl, "utf8");

console.log("✔ JSON → OBJ done (geometry + material).");
