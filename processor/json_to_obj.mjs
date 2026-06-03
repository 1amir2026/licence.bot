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
    const geo = json["minecraft:geometry"]?.[0];
    if (!geo) throw new Error("Geometry not found");

    const texW = geo.description?.texture_width || 64;
    const texH = geo.description?.texture_height || 64;
    const SCALE = 0.0625;

    let vertices = [], uvs = [], faces = [];
    let vCount = 1;

    geo.bones.forEach(bone => {
        if (!bone.cubes) return;

        bone.cubes.forEach(cube => {
            const origin = (cube.origin || [0,0,0]).map(v => v * SCALE);
            const size   = (cube.size   || [1,1,1]).map(v => v * SCALE);
            const uv     = cube.uv || {};

            // 8 corners
            const c = [
                [origin[0],          origin[1],          origin[2]],
                [origin[0]+size[0],  origin[1],          origin[2]],
                [origin[0]+size[0],  origin[1]+size[1],  origin[2]],
                [origin[0],          origin[1]+size[1],  origin[2]],
                [origin[0],          origin[1],          origin[2]+size[2]],
                [origin[0]+size[0],  origin[1],          origin[2]+size[2]],
                [origin[0]+size[0],  origin[1]+size[1],  origin[2]+size[2]],
                [origin[0],          origin[1]+size[1],  origin[2]+size[2]],
            ];

            const vIds = c.map(p => {
                vertices.push(`v ${p[0].toFixed(6)} ${p[1].toFixed(6)} ${p[2].toFixed(6)}`);
                return vCount++;
            });

            // 6 faces with correct UV mapping
            const faceDefs = [
                { name: 'north',  order: [3,2,1,0], uv: uv.north },
                { name: 'east',   order: [2,6,5,1], uv: uv.east },
                { name: 'south',  order: [6,7,4,5], uv: uv.south },
                { name: 'west',   order: [7,3,0,4], uv: uv.west },
                { name: 'up',     order: [3,7,6,2], uv: uv.up },
                { name: 'down',   order: [0,1,5,4], uv: uv.down },
            ];

            faceDefs.forEach(f => {
                if (!f.uv?.uv) return;
                const [u, v] = f.uv.uv;
                const [uw, vh] = f.uv.uv_size || [1,1];

                const uvIds = [
                    addUV(u/texW, v/texH),
                    addUV((u+uw)/texW, v/texH),
                    addUV((u+uw)/texW, (v+vh)/texH),
                    addUV(u/texW, (v+vh)/texH)
                ];

                const o = f.order;
                faces.push(`f ${vIds[o[0]]}/${uvIds[0]}/1 ${vIds[o[1]]}/${uvIds[1]}/1 ${vIds[o[2]]}/${uvIds[2]}/1 ${vIds[o[3]]}/${uvIds[3]}/1`);
            });
        });
    });

    function addUV(u, v) {
        const id = uvs.length + 1;
        uvs.push(`vt ${u.toFixed(6)} ${1 - v.toFixed(6)}`);
        return id;
    }

    const baseName = path.basename(outputObjPath, '.obj');

    const objContent = [
        `# Converted from Minecraft Bedrock Geometry`,
        `mtllib ${baseName}.mtl`,
        ...vertices,
        ...uvs,
        'vn 0 1 0',
        ...faces
    ].join('\n');

    fs.writeFileSync(outputObjPath, objContent);
    fs.writeFileSync(outputObjPath.replace('.obj', '.mtl'), 
        `newmtl material\nKd 1.0 1.0 1.0\nmap_Kd ${baseName}.png\n`);

    console.log(`✅ Converted: ${outputObjPath}`);
    process.exit(0);

} catch (err) {
    console.error("Error:", err.message);
    process.exit(1);
}
