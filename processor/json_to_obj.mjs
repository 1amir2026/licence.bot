import fs from 'fs';
import path from 'path';

const inputPath = process.argv[2];
const outputObjPath = process.argv[3];

if (!inputPath || !outputObjPath) {
    console.error("Usage: node json_to_obj.mjs <input.json> <output.obj>");
    process.exit(1);
}

try {
    let json = JSON.parse(fs.readFileSync(inputPath, 'utf8'));
    const baseName = path.basename(outputObjPath, '.obj');

    // پشتیبانی از هر دو فرمت Java و Bedrock
    const elements = json.elements || (json.minecraft && json.minecraft.geometry ? json.minecraft.geometry[0].bones.flatMap(b => b.cubes || []) : []);
    const texW = json.texture_size?.[0] || json.texture_width || 64;
    const texH = json.texture_size?.[1] || json.texture_height || 64;

    let vertices = [], uvs = [], faces = [];
    let vCount = 1;
    const SCALE = 0.0625; // 1/16

    function addVertex(x, y, z) {
        vertices.push(`v ${(x * SCALE).toFixed(6)} ${(y * SCALE).toFixed(6)} ${(z * SCALE).toFixed(6)}`);
        return vCount++;
    }

    function addUV(u, v) {
        const id = uvs.length + 1;
        uvs.push(`vt ${u.toFixed(6)} ${(1 - v).toFixed(6)}`);
        return id;
    }

    // تابع چرخش پیشرفته با Pivot
    function applyRotation(corners, rotation) {
        if (!rotation) return corners;
        const origin = rotation.origin || [0, 0, 0];
        const rx = (rotation.x || 0) * Math.PI / 180;
        const ry = (rotation.y || 0) * Math.PI / 180;
        const rz = (rotation.z || 0) * Math.PI / 180;

        return corners.map(([x, y, z]) => {
            x -= origin[0]; y -= origin[1]; z -= origin[2];

            // Rotation Z
            let tx = x * Math.cos(rz) - y * Math.sin(rz);
            let ty = x * Math.sin(rz) + y * Math.cos(rz);
            x = tx; y = ty;

            // Rotation Y
            tx = x * Math.cos(ry) + z * Math.sin(ry);
            let tz = -x * Math.sin(ry) + z * Math.cos(ry);
            x = tx; z = tz;

            // Rotation X
            ty = y * Math.cos(rx) - z * Math.sin(rx);
            tz = y * Math.sin(rx) + z * Math.cos(rx);
            y = ty; z = tz;

            return [x + origin[0], y + origin[1], z + origin[2]];
        });
    }

    elements.forEach(el => {
        if (!el.from || !el.to) return;

        let corners = [
            [el.from[0], el.from[1], el.from[2]],
            [el.to[0],   el.from[1], el.from[2]],
            [el.to[0],   el.to[1],   el.from[2]],
            [el.from[0], el.to[1],   el.from[2]],
            [el.from[0], el.from[1], el.to[2]],
            [el.to[0],   el.from[1], el.to[2]],
            [el.to[0],   el.to[1],   el.to[2]],
            [el.from[0], el.to[1],   el.to[2]],
        ];

        corners = applyRotation(corners, el.rotation);

        const vIds = corners.map(p => addVertex(p[0], p[1], p[2]));

        const faceDefs = [
            {key: 'north', order: [3,2,1,0]},
            {key: 'east',  order: [2,6,5,1]},
            {key: 'south', order: [6,7,4,5]},
            {key: 'west',  order: [7,3,0,4]},
            {key: 'up',    order: [3,7,6,2]},
            {key: 'down',  order: [0,1,5,4]},
        ];

        const facesData = el.faces || {};

        faceDefs.forEach(f => {
            const face = facesData[f.key];
            if (!face || !face.uv) return;

            let [u1, v1, u2, v2] = face.uv;
            const uvIds = [
                addUV(u1 / texW, v1 / texH),
                addUV(u2 / texW, v1 / texH),
                addUV(u2 / texW, v2 / texH),
                addUV(u1 / texW, v2 / texH)
            ];

            const o = f.order;
            faces.push(`f ${vIds[o[0]]}/${uvIds[0]}/1 ${vIds[o[1]]}/${uvIds[1]}/1 ${vIds[o[2]]}/${uvIds[2]}/1 ${vIds[o[3]]}/${uvIds[3]}/1`);
        });
    });

    const objContent = [
        `# Minecraft JSON to OBJ - Advanced Conversion`,
        `mtllib ${baseName}.mtl`,
        ...vertices,
        ...uvs,
        'vn 0 1 0',
        ...faces
    ].join('\n');

    fs.writeFileSync(outputObjPath, objContent);
    fs.writeFileSync(outputObjPath.replace('.obj', '.mtl'), 
        `newmtl material\nKd 1 1 1\nmap_Kd ${baseName}.png\n`);

    console.log(`✅ Conversion completed: ${outputObjPath}`);
    process.exit(0);

} catch (err) {
    console.error("Error:", err.message);
    process.exit(1);
}
