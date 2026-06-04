import fs from "fs";
import path from "path";

// ====== PORT ======
function rotateAround(deg, pos, origin, axis = "y") {
    const r = -deg * Math.PI / 180;

    const axis_i = axis.charCodeAt(0) - 120; // 'x'=0, 'y'=1, 'z'=2

    const a = pos[(1 + axis_i) % 3];
    const b = pos[(2 + axis_i) % 3];
    const c = pos[(3 + axis_i) % 3];

    const m = origin[(1 + axis_i) % 3];
    const n = origin[(2 + axis_i) % 3];

    const new_pos = [0, 0, 0];
    new_pos[(1 + axis_i) % 3] = Math.cos(r) * (a - m) + (b - n) * Math.sin(r) + m;
    new_pos[(2 + axis_i) % 3] = -Math.sin(r) * (a - m) + Math.cos(r) * (b - n) + n;
    new_pos[(3 + axis_i) % 3] = c;

    const offset = [8, 0, 8];
    const scale = [1 / 16, 1 / 16, 1 / 16];

    return [
        -(new_pos[0] - offset[0]) * scale[0],
        (new_pos[2] - offset[2]) * scale[2],
        (new_pos[1] - offset[1]) * scale[1],
    ];
}

// ====== Element = add.element ======
function buildElement(elm_from = [0, 0, 0], elm_to = [16, 16, 16], rotation) {
    const rot_origin = rotation?.origin || [8, 8, 8];
    const rot_axis = rotation?.axis || "y";
    const rot_angle = rotation?.angle || 0;

    const verts = [
        rotateAround(rot_angle, [elm_from[0], elm_to[1], elm_from[2]], rot_origin, rot_axis),
        rotateAround(rot_angle, [elm_to[0],   elm_to[1], elm_from[2]], rot_origin, rot_axis),
        rotateAround(rot_angle, [elm_to[0],   elm_from[1], elm_from[2]], rot_origin, rot_axis),
        rotateAround(rot_angle, [elm_from[0], elm_from[1], elm_from[2]], rot_origin, rot_axis),
        rotateAround(rot_angle, [elm_from[0], elm_to[1], elm_to[2]], rot_origin, rot_axis),
        rotateAround(rot_angle, [elm_to[0],   elm_to[1], elm_to[2]], rot_origin, rot_axis),
        rotateAround(rot_angle, [elm_to[0],   elm_from[1], elm_to[2]], rot_origin, rot_axis),
        rotateAround(rot_angle, [elm_from[0], elm_from[1], elm_to[2]], rot_origin, rot_axis),
    ];

    const faces = [
        [0, 1, 2, 3], // north
        [5, 4, 7, 6], // south
        [1, 0, 4, 5], // up
        [7, 6, 2, 3], // down
        [4, 0, 3, 7], // west
        [1, 5, 6, 2], // east
    ];

    return { verts, faces };
}

// ====== MAIN ======
if (process.argv.length < 4) {
    console.error("Usage: node json_to_obj.mjs input.json output.obj");
    process.exit(1);
}

const inputJson = process.argv[2];
const outputObj = process.argv[3];
const outputMtl = outputObj.replace(".obj", ".mtl");

if (!fs.existsSync(inputJson)) {
    console.error("JSON file not found:", inputJson);
    process.exit(1);
}

const raw = JSON.parse(fs.readFileSync(inputJson, "utf8"));
const elements = raw.elements || [];

if (!elements.length) {
    console.error("❌ No elements in JSON (این فایل خودش geometry ندارد).");
    process.exit(1);
}

let obj = "";
let mtl = "";
let vCount = 1;

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

for (const e of elements) {
    if (!e.from || !e.to) continue;

    const { verts, faces } = buildElement(e.from, e.to, e.rotation);

    for (const v of verts) {
        obj += `v ${v[0]} ${v[1]} ${v[2]}\n`;
    }

    for (const f of faces) {
        obj += `f ${f[0] + vCount} ${f[1] + vCount} ${f[2] + vCount} ${f[3] + vCount}\n`;
    }

    vCount += 8;
}

fs.writeFileSync(outputObj, obj, "utf8");
fs.writeFileSync(outputMtl, mtl, "utf8");

console.log("✔ JSON → OBJ done (با روتیشن مثل بلندر).");
