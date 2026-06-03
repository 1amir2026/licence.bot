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

    if (!geometry) {
        throw new Error("فرمت JSON معتبر ماینکرافت پیدا نشد.");
    }

    let vertices = [];
    let uvs = [];
    let faces = [];
    let vertexIndex = 1;

    const bones = geometry.bones || [];

    bones.forEach(bone => {
        if (!bone.cubes) return;

        bone.cubes.forEach(cube => {
            const origin = cube.origin || [0, 0, 0];
            const size = cube.size || [1, 1, 1];
            const rotation = cube.rotation || [0, 0, 0];
            const pivot = cube.pivot || origin;

            // تولید ۸ راس مکعب
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

            // ساده‌سازی: فعلاً rotation کامل اعمال نمی‌شود (برای شروع)
            corners.forEach(p => {
                vertices.push(`v ${p[0].toFixed(6)} ${p[1].toFixed(6)} ${p[2].toFixed(6)}`);
            });

            // UV ساده (نیاز به بهبود دارد)
            uvs.push(`vt 0 0`, `vt 1 0`, `vt 1 1`, `vt 0 1`);

            // Faces (6 وجه)
            const idx = vertexIndex;
            faces.push(
                `f ${idx} ${idx+1} ${idx+2} ${idx+3}`,
                `f ${idx+4} ${idx+5} ${idx+6} ${idx+7}`,
                `f ${idx} ${idx+1} ${idx+5} ${idx+4}`,
                `f ${idx+3} ${idx+2} ${idx+6} ${idx+7}`,
                `f ${idx+1} ${idx+2} ${idx+6} ${idx+5}`,
                `f ${idx} ${idx+3} ${idx+7} ${idx+4}`
            );

            vertexIndex += 8;
        });
    });

    const objContent = [
        `# Converted from Minecraft Geometry`,
        `# Model: ${geometry.description?.identifier || 'unknown'}`,
        ...vertices,
        ...uvs,
        ...faces,
        ''
    ].join('\n');

    fs.writeFileSync(outputObjPath, objContent);

    // ایجاد MTL ساده
    const mtlPath = outputObjPath.replace('.obj', '.mtl');
    const mtlContent = `newmtl material\nKd 1 1 1\nmap_Kd texture.png\n`;
    fs.writeFileSync(mtlPath, mtlContent);

    // ایجاد texture.png placeholder
    const pngPath = path.join(path.dirname(outputObjPath), 'texture.png');
    if (!fs.existsSync(pngPath)) {
        fs.writeFileSync(pngPath, Buffer.from('iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAYAAAAfFcSJAAAADUlEQVR42mP8/5+hHgAHggJ/PchI7wAAAABJRU5ErkJggg==', 'base64'));
    }

    console.log(`✅ Conversion successful: ${outputObjPath}`);
    process.exit(0);

} catch (err) {
    console.error("Error:", err.message);
    process.exit(1);
}