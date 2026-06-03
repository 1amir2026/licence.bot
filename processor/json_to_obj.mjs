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

    let elements = json.elements || [];
    const texW = json.texture_size?.[0] || 64;
    const texH = json.texture_size?.[1] || 64;

    let vertices = [], uvs = [], faces = [];
    let vCount = 1;
    const SCALE = 0.0625;

    elements.forEach((el, index) => {
        const from = el.from.map(v => v * SCALE);
        const to = el.to.map(v => v * SCALE);
        const facesData = el.faces || {};

        // 8 corners
        const corners = [
            [from[0], from[1], from[2]],
            [to[0],   from[1], from[2]],
            [to[0],   to[1],   from[2]],
            [from[0], to[1],   from[2]],
            [from[0], from[1], to[2]],
            [to[0],   from[1], to[2]],
            [to[0],   to[1],   to[2]],
            [from[0], to[1],   to[2]],
        ];

        const vIds = corners.map(p => {
            vertices.push(`v ${p[0].toFixed(6)} ${p[1].toFixed(6)} ${p[2].toFixed(6)}`);
            return vCount++;
        });

        const faceList = [
            { dir: 'north', order: [3,2,1,0], uv: facesData.north },
            { dir: 'east',  order: [2,6,5,1], uv: facesData.east },
            { dir: 'south', order: [6,7,4,5], uv: facesData.south },
            { dir: 'west',  order: [7,3,0,4], uv: facesData.west },
            { dir: 'up',    order: [3,7,6,2], uv: facesData.up },
            { dir: 'down',  order: [0,1,5,4], uv: facesData.down },
        ];

        faceList.forEach(f => {
            if (!f.uv?.uv) return;

            const [u1, v1, u2, v2] = f.uv.uv;
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
        `# Converted from Java Model`,
        `mtllib ${baseName}.mtl`,
        ...vertices,
        ...uvs,
        'vn 0 1 0',
        ...faces
    ].join('\n');

    fs.writeFileSync(outputObjPath, objContent);
    fs.writeFileSync(outputObjPath.replace('.obj', '.mtl'), 
        `newmtl material\nKd 1 1 1\nmap_Kd ${baseName}.png\n`);

    console.log(`✅ Converted: ${outputObjPath}`);
    process.exit(0);

} catch (err) {
    console.error("Error:", err.message);
    process.exit(1);
}
