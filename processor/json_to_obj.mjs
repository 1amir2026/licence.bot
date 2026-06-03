import fs from 'fs';
import path from 'path';

const inputPath = process.argv[2];
const outputObjPath = process.argv[3];

if (!inputPath || !outputObjPath) {
    console.error("Usage: node json_to_obj.mjs <input.json> <output.obj>");
    process.exit(1);
}

try {
    const jsonData = JSON.parse(fs.readFileSync(inputPath, 'utf8'));
    const geometry = jsonData["minecraft:geometry"]?.[0];
    
    if (!geometry || !geometry.bones) {
        throw new Error("فرمت JSON معتبر ماینکرافت پیدا نشد.");
    }

    const textureWidth = geometry.description?.texture_width || 64;
    const textureHeight = geometry.description?.texture_height || 64;

    let vertices = [];
    let uvs = [];
    let faces = [];
    let vertexCounter = 1;

    // مقیاس‌دهی مناسب برای ماینکرافت (بسیار مهم!)
    const SCALE = 0.0625; // 1/16 — استاندارد Bedrock Geometry

    geometry.bones.forEach(bone => {
        if (!bone.cubes) return;

        bone.cubes.forEach(cube => {
            let origin = cube.origin || [0, 0, 0];
            const size = cube.size || [1, 1, 1];
            const uvData = cube.uv || {};

            // اعمال مقیاس
            origin = origin.map(v => v * SCALE);

            const corners = [
                [origin[0],           origin[1],           origin[2]],
                [origin[0] + size[0]*SCALE, origin[1],           origin[2]],
                [origin[0] + size[0]*SCALE, origin[1] + size[1]*SCALE, origin[2]],
                [origin[0],           origin[1] + size[1]*SCALE, origin[2]],
                [origin[0],           origin[1],           origin[2] + size[2]*SCALE],
                [origin[0] + size[0]*SCALE, origin[1],           origin[2] + size[2]*SCALE],
                [origin[0] + size[0]*SCALE, origin[1] + size[1]*SCALE, origin[2] + size[2]*SCALE],
                [origin[0],           origin[1] + size[1]*SCALE, origin[2] + size[2]*SCALE],
            ];

            const vIndices = [];
            corners.forEach(p => {
                vertices.push(`v ${p[0].toFixed(6)} ${p[1].toFixed(6)} ${p[2].toFixed(6)}`);
                vIndices.push(vertexCounter++);
            });

            const faceOrder = [
                {face: 'north',  verts: [0,1,5,4]},
                {face: 'east',   verts: [1,2,6,5]},
                {face: 'south',  verts: [2,3,7,6]},
                {face: 'west',   verts: [3,0,4,7]},
                {face: 'up',     verts: [4,5,6,7]},
                {face: 'down',   verts: [0,3,2,1]}
            ];

            faceOrder.forEach(({face, verts}) => {
                const uvInfo = uvData[face] || {uv: [0,0], uv_size: [1,1]};
                let [u, v] = uvInfo.uv || [0, 0];
                let [uw, vh] = uvInfo.uv_size || [1, 1];

                u /= textureWidth;
                v /= textureHeight;
                uw /= textureWidth;
                vh /= textureHeight;

                const uvIndices = [];
                uvIndices.push(addUV(u, v));
                uvIndices.push(addUV(u + uw, v));
                uvIndices.push(addUV(u + uw, v + vh));
                uvIndices.push(addUV(u, v + vh));

                faces.push(`f ${vIndices[verts[0]]}/${uvIndices[0]}/1 ${vIndices[verts[1]]}/${uvIndices[1]}/1 ${vIndices[verts[2]]}/${uvIndices[2]}/1 ${vIndices[verts[3]]}/${uvIndices[3]}/1`);
            });
        });
    });

    function addUV(u, v) {
        const idx = uvs.length + 1;
        uvs.push(`vt ${u.toFixed(6)} ${1 - v.toFixed(6)}`);
        return idx;
    }

    const baseName = path.basename(outputObjPath, '.obj');
    const mtlName = `${baseName}.mtl`;

    const objContent = [
        `# Converted from Minecraft Bedrock`,
        `mtllib ${mtlName}`,
        ...vertices,
        ...uvs,
        'vn 0 1 0',
        ...faces
    ].join('\n');

    fs.writeFileSync(outputObjPath, objContent);

    // MTL با نام تکسچر واقعی (بعداً در بات جایگزین می‌شود)
    const mtlPath = outputObjPath.replace('.obj', '.mtl');
    const mtlContent = `newmtl material\nKd 1 1 1\nmap_Kd ${baseName}.png\n`;
    fs.writeFileSync(mtlPath, mtlContent);

    console.log(`✅ Conversion successful: ${outputObjPath} (Scaled)`);
    process.exit(0);

} catch (err) {
    console.error("Error:", err.message);
    process.exit(1);
}
