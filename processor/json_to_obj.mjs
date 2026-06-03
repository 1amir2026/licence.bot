import fs from 'fs';
import path from 'path';

const inputPath = process.argv[2];
const outputObjPath = process.argv[3];

if (!inputPath || !outputObjPath) {
    console.error("Usage: node json_to_obj.mjs <input.json> <output.obj>");
    process.exit(1);
}

try {
    const json = JSON.parse(fs.readFileSync(inputPath, 'utf8'));
    const baseName = path.basename(outputObjPath, '.obj');

    const elements = json.elements || [];
    const texW = json.texture_size?.[0] || 64;
    const texH = json.texture_size?.[1] || 64;

    let vertices = [], uvs = [], faces = [];
    let vCount = 1;
    const SCALE = 0.0625;

    // Helper functions for rotation
    function rotatePoint(point, rotation) {
        if (!rotation) return point;
        let [x, y, z] = point;
        const radX = (rotation.x || 0) * Math.PI / 180;
        const radY = (rotation.y || 0) * Math.PI / 180;
        const radZ = (rotation.z || 0) * Math.PI / 180;
        const origin = rotation.origin || [0, 0, 0];

        // Translate to origin
        x -= origin[0];
        y -= origin[1];
        z -= origin[2];

        // Rotate Z
        let temp = x;
        x = x * Math.cos(radZ) - y * Math.sin(radZ);
        y = temp * Math.sin(radZ) + y * Math.cos(radZ);

        // Rotate Y
        temp = x;
        x = x * Math.cos(radY) + z * Math.sin(radY);
        z = -temp * Math.sin(radY) + z * Math.cos(radY);

        // Rotate X
        temp = y;
        y = y * Math.cos(radX) - z * Math.sin(radX);
        z = temp * Math.sin(radX) + z * Math.cos(radX);

        // Translate back
        return [
            x + origin[0],
            y + origin[1],
            z + origin[2]
        ];
    }

    elements.forEach(el => {
        const from = el.from.map(v => v * SCALE);
        const to = el.to.map(v => v * SCALE);
        const rotation = el.rotation;
        const facesData = el.faces || {};

        // Generate 8 corners
        let corners = [
            [from[0], from[1], from[2]],
            [to[0],   from[1], from[2]],
            [to[0],   to[1],   from[2]],
            [from[0], to[1],   from[2]],
            [from[0], from[1], to[2]],
            [to[0],   from[1], to[2]],
            [to[0],   to[1],   to[2]],
            [from[0], to[1],   to[2]],
        ];

        // Apply rotation if exists
        if (rotation) {
            corners = corners.map(p => rotatePoint(p, rotation));
        }

        const vIds = corners.map(p => {
            vertices.push(`v ${p[0].toFixed(6)} ${p[1].toFixed(6)} ${p[2].toFixed(6)}`);
            return vCount++;
        });

        const faceDefs = [
            {key: 'north', order: [3,2,1,0]},
            {key: 'east',  order: [2,6,5,1]},
            {key: 'south', order: [6,7,4,5]},
            {key: 'west',  order: [7,3,0,4]},
            {key: 'up',    order: [3,7,6,2]},
            {key: 'down',  order: [0,1,5,4]},
        ];

        faceDefs.forEach(f => {
            const face = facesData[f.key];
            if (!face?.uv) return;

            const [u1, v1, u2, v2] = face.uv;
            const uvIds = [
                addUV(u1/texW, v1/texH),
                addUV(u2/texW, v1/texH),
                addUV(u2/texW, v2/texH),
                addUV(u1/texW, v2/texH)
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

    const objContent = [
        `# Advanced Conversion from Java Model`,
        `mtllib ${baseName}.mtl`,
        ...vertices,
        ...uvs,
        'vn 0 1 0',
        ...faces
    ].join('\n');

    fs.writeFileSync(outputObjPath, objContent);
    fs.writeFileSync(outputObjPath.replace('.obj', '.mtl'), 
        `newmtl material\nKd 1 1 1\nmap_Kd ${baseName}.png\n`);

    console.log(`✅ Advanced conversion completed: ${outputObjPath}`);
    process.exit(0);

} catch (err) {
    console.error("Error:", err.message);
    process.exit(1);
}
