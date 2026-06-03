import fs from 'fs';
import path from 'path';

const inputPath = process.argv[2];
const outputObjPath = process.argv[3];

if (!inputPath || !outputObjPath) {
    console.error("Usage: node json_to_obj.mjs <input.json> <output.obj>");
    process.exit(1);
}

try {
    let jsonText = fs.readFileSync(inputPath, 'utf8').replace(/\/\/.*$/gm, '');
    const json = JSON.parse(jsonText);
    
    let elements = [];
    let textureWidth = 64;
    let textureHeight = 64;
    let baseTexture = "texture";

    // تشخیص نوع فرمت
    if (json["minecraft:geometry"]) {
        // === Bedrock Format ===
        const geo = Array.isArray(json["minecraft:geometry"]) ? json["minecraft:geometry"][0] : json["minecraft:geometry"];
        if (geo.bones) {
            console.log("Detected: Bedrock Geometry");
            // ... (کد قبلی Bedrock) ...
            // برای اختصار فعلاً فقط Java را کامل می‌کنیم چون مشکل فعلی Java است
        }
    } else if (json.elements) {
        // === Java Edition Format ===
        console.log("Detected: Java Edition Model");
        elements = json.elements || [];
        textureWidth = json.texture_size?.[0] || 64;
        textureHeight = json.texture_size?.[1] || 64;
    } else {
        throw new Error(`Unknown format. Keys: ${Object.keys(json)}`);
    }

    let vertices = [], uvs = [], faces = [];
    let vCount = 1;
    const SCALE = 0.0625;

    elements.forEach((el, idx) => {
        const from = (el.from || [0,0,0]).map(v => v * SCALE);
        const to   = (el.to   || [1,1,1]).map(v => v * SCALE);
        const facesUV = el.faces || {};

        const c = [
            [from[0], from[1], from[2]],
            [to[0],   from[1], from[2]],
            [to[0],   to[1],   from[2]],
            [from[0], to[1],   from[2]],
            [from[0], from[1], to[2]],
            [to[0],   from[1], to[2]],
            [to[0],   to[1],   to[2]],
            [from[0], to[1],   to[2]],
        ];

        const vIds = c.map(p => {
            vertices.push(`v ${p[0].toFixed(6)} ${p[1].toFixed(6)} ${p[2].toFixed(6)}`);
            return vCount++;
        });

        const faceOrder = [
            {key: 'north', order: [3,2,1,0]},
            {key: 'east',  order: [2,6,5,1]},
            {key: 'south', order: [6,7,4,5]},
            {key: 'west',  order: [7,3,0,4]},
            {key: 'up',    order: [3,7,6,2]},
            {key: 'down',  order: [0,1,5,4]},
        ];

        faceOrder.forEach(f => {
            const faceData = facesUV[f.key];
            if (!faceData?.uv) return;

            const [u1, v1, u2, v2] = faceData.uv;
            const uvIds = [
                addUV(u1/textureWidth, v1/textureHeight),
                addUV(u2/textureWidth, v1/textureHeight),
                addUV(u2/textureWidth, v2/textureHeight),
                addUV(u1/textureWidth, v2/textureHeight),
            ];

            const o = f.order;
            faces.push(`f ${vIds[o[0]]}/${uvIds[0]}/1 ${vIds[o[1]]}/${uvIds[1]}/1 ${vIds[o[2]]}/${uvIds[2]}/1 ${vIds[o[3]]}/${uvIds[3]}/1`);
        });
    });

    function addUV(u, v) {
        const id = uvs.length + 1;
        uvs.push(`vt ${u.toFixed(6)} ${1 - v.toFixed(6)}`);
        return id;
    }

    const baseName = path.basename(outputObjPath, '.obj');

    const objContent = [
        `# Converted from Minecraft Java Model`,
        `mtllib ${baseName}.mtl`,
        ...vertices,
        ...uvs,
        'vn 0 1 0',
        ...faces
    ].join('\n');

    fs.writeFileSync(outputObjPath, objContent);
    fs.writeFileSync(outputObjPath.replace('.obj', '.mtl'), 
        `newmtl material\nKd 1 1 1\nmap_Kd ${baseName}.png\n`);

    console.log(`✅ Successfully converted Java Model: ${outputObjPath}`);
    process.exit(0);

} catch (err) {
    console.error("Error:", err.message);
    process.exit(1);
}
