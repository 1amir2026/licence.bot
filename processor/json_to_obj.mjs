import fs from 'fs';
import path from 'path';

const [,, inputJson, outputObj] = process.argv;

if (!inputJson || !outputObj) {
    console.error("Usage: node json_to_obj.mjs <input.json> <output.obj>");
    process.exit(1);
}

try {
    const data = JSON.parse(fs.readFileSync(inputJson, 'utf8'));
    const baseName = path.basename(outputObj, '.obj');

    const elements = data.elements || [];
    const texW = data.texture_size?.[0] || 64;
    const texH = data.texture_size?.[1] || 64;

    let objLines = [];
    let vertexCount = 1;
    let uvCount = 1;
    const SCALE = 0.0625;

    function addVertex(x, y, z) {
        objLines.push(`v ${(x * SCALE).toFixed(6)} ${(y * SCALE).toFixed(6)} ${(z * SCALE).toFixed(6)}`);
        return vertexCount++;
    }

    function addUV(u, v) {
        objLines.push(`vt ${u.toFixed(6)} ${(1 - v).toFixed(6)}`);
        return uvCount++;
    }

    // چرخش کامل (3 محور + pivot) - مثل MCPrep/Blockbench
    function applyRotation(corners, rotation) {
        if (!rotation?.origin) return corners;
        const [ox, oy, oz] = rotation.origin;
        const rx = (rotation.x || 0) * Math.PI / 180;
        const ry = (rotation.y || 0) * Math.PI / 180;
        const rz = (rotation.z || 0) * Math.PI / 180;

        return corners.map(([x, y, z]) => {
            x -= ox; y -= oy; z -= oz;

            // Z rotation
            let tx = x * Math.cos(rz) - y * Math.sin(rz);
            let ty = x * Math.sin(rz) + y * Math.cos(rz);
            x = tx; y = ty;

            // Y rotation
            tx = x * Math.cos(ry) + z * Math.sin(ry);
            let tz = -x * Math.sin(ry) + z * Math.cos(ry);
            x = tx; z = tz;

            // X rotation
            ty = y * Math.cos(rx) - z * Math.sin(rx);
            tz = y * Math.sin(rx) + z * Math.cos(rx);
            y = ty; z = tz;

            return [x + ox, y + oy, z + oz];
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
            [el.from[0], el.to[1],   el.to[2]]
        ];

        corners = applyRotation(corners, el.rotation);

        const vIds = corners.map(v => addVertex(...v));

        // ترتیب face دقیق‌تر (مشابه Blockbench)
        const faceDefs = [
            { dir: 'north', order: [3, 2, 1, 0] },
            { dir: 'east',  order: [2, 6, 5, 1] },
            { dir: 'south', order: [6, 7, 4, 5] },
            { dir: 'west',  order: [7, 3, 0, 4] },
            { dir: 'up',    order: [3, 7, 6, 2] },
            { dir: 'down',  order: [0, 1, 5, 4] }
        ];

        faceDefs.forEach(({ dir, order }) => {
            const face = el.faces?.[dir];
            if (!face?.uv) return;

            const [u1, v1, u2, v2] = face.uv.map(n => Number(n));

            const uvIds = [
                addUV(u1 / texW, v1 / texH),
                addUV(u2 / texW, v1 / texH),
                addUV(u2 / texW, v2 / texH),
                addUV(u1 / texW, v2 / texH)
            ];

            objLines.push(`f ${vIds[order[0]]}/${uvIds[0]} ${vIds[order[1]]}/${uvIds[1]} ${vIds[order[2]]}/${uvIds[2]} ${vIds[order[3]]}/${uvIds[3]}`);
        });
    });

    const objContent = [
        `# JSON to OBJ - Improved for MCPrep/Blockbench`,
        `mtllib ${baseName}.mtl`,
        ...objLines,
        'vn 0 1 0'
    ].join('\n');

    fs.writeFileSync(outputObj, objContent);

    const mtlPath = outputObj.replace('.obj', '.mtl');
    fs.writeFileSync(mtlPath, `newmtl material\nKd 1 1 1\nmap_Kd ${baseName}.png\n`);

    console.log(`✅ Converted successfully: ${outputObj}`);

} catch (err) {
    console.error("Error:", err.message);
    process.exit(1);
}
