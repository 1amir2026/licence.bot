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

    let vertices = [];
    let uvs = [];
    let normals = [];
    let faces = [];
    let vertexCounter = 1;

    const textureWidth = geometry.description?.texture_width || 64;
    const textureHeight = geometry.description?.texture_height || 64;

    geometry.bones.forEach(bone => {
        if (!bone.cubes) return;

        bone.cubes.forEach((cube, cubeIndex) => {
            const origin = cube.origin || [0, 0, 0];
            const size = cube.size || [1, 1, 1];
            const uvData = cube.uv || {}; // uv per face

            // تولید ۸ رأس مکعب
            const corners = [
                [origin[0],           origin[1],           origin[2]],
                [origin[0] + size[0], origin[1],           origin[2]],
                [origin[0] + size[0], origin[1] + size[1], origin[2]],
                [origin[0],           origin[1] + size[1], origin[2]],
                [origin[0],           origin[1],           origin[2] + size[2]],
                [origin[0] + size[0], origin[1],           origin[2] + size[2]],
                [origin[0] + size[0], origin[1] + size[1], origin[2] + size[2]],
                [origin[0],           origin[1] + size[1], origin[2] + size[2]],
            ];

            const vIndices = [];
            corners.forEach(p => {
                vertices.push(`v ${p[0].toFixed(6)} ${p[1].toFixed(6)} ${p[2].toFixed(6)}`);
                vIndices.push(vertexCounter++);
            });

            // UV ساده (بهبود یافته)
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
                const [u, v] = uvInfo.uv || [0, 0];
                const [uw, vh] = uvInfo.uv_size || [1, 1];

                const uvIndices = [];
                // 4 UV برای هر وجه
                uvIndices.push(addUV(u/ textureWidth, v/ textureHeight));
                uvIndices.push(addUV((u+uw)/ textureWidth, v/ textureHeight));
                uvIndices.push(addUV((u+uw)/ textureWidth, (v+vh)/ textureHeight));
                uvIndices.push(addUV(u/ textureWidth, (v+vh)/ textureHeight));

                // Face
                faces.push(`f ${vIndices[verts[0]]}/${uvIndices[0]}/1 ${vIndices[verts[1]]}/${uvIndices[1]}/1 ${vIndices[verts[2]]}/${uvIndices[2]}/1 ${vIndices[verts[3]]}/${uvIndices[3]}/1`);
            });
        });
    });

    function addUV(u, v) {
        const idx = uvs.length + 1;
        uvs.push(`vt ${u.toFixed(6)} ${1 - v.toFixed(6)}`); // Flip V for OBJ
        return idx;
    }

    const objContent = [
        `# Converted from Minecraft Bedrock Geometry`,
        `# Model: ${geometry.description?.identifier || 'unknown'}`,
        `mtllib ${path.basename(outputObjPath).replace('.obj', '.mtl')}`,
        ...vertices,
        ...uvs,
        'vn 0 1 0', // ساده‌سازی نرمال
        ...faces
    ].join('\n');

    fs.writeFileSync(outputObjPath, objContent);

    // ایجاد MTL
    const mtlPath = outputObjPath.replace('.obj', '.mtl');
    const mtlContent = `newmtl material\nKd 1 1 1\nmap_Kd texture.png\n`;
    fs.writeFileSync(mtlPath, mtlContent);

    console.log(`✅ Conversion successful: ${outputObjPath}`);
    process.exit(0);

} catch (err) {
    console.error("Error:", err.message);
    process.exit(1);
}
