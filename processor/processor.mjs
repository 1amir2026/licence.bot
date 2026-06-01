// processor/processor.mjs

import fs from "fs";
import path from "path";
import make from "./src.js"; // پردازش پک قبلی
import * as THREE from "three";
import { GLTFExporter } from "three/examples/jsm/exporters/GLTFExporter.js";
import { createCanvas, loadImage } from "canvas";

const __dirname = path.dirname(new URL(import.meta.url).pathname);

// ---------------------- MODE: PACK ----------------------
async function processPack(inputPath, outputPath) {
    const packBuffer = fs.readFileSync(inputPath);
    const packName = path.basename(inputPath);

    const imgBuffer = await make(
        packName,
        packBuffer,
        1,      // upscaleRate (فعلاً ثابت)
        0.7     // xpPercent (فعلاً ثابت)
    );

    fs.writeFileSync(outputPath, imgBuffer);
    console.log("OK_PACK");
}

// ---------------------- MODE: 3D ----------------------
async function process3D(inputPath, outputPath) {
    const texture = await loadImage(inputPath);

    const scene = new THREE.Scene();
    const camera = new THREE.PerspectiveCamera(75, 1, 0.1, 1000);
    camera.position.z = 2;

    const canvas = createCanvas(texture.width, texture.height);
    const ctx = canvas.getContext("2d");
    ctx.drawImage(texture, 0, 0);

    const tex = new THREE.CanvasTexture(canvas);
    const material = new THREE.MeshBasicMaterial({ map: tex, transparent: true });

    // مدل شبیه آیتم ماینکرافت
    const geometry = new THREE.BoxGeometry(1, 1, 0.08);
    const mesh = new THREE.Mesh(geometry, material);
    scene.add(mesh);

    const exporter = new GLTFExporter();
    exporter.parse(
        scene,
        (gltf) => {
            const data = Buffer.from(JSON.stringify(gltf));
            fs.writeFileSync(outputPath, data);
            console.log("OK_3D");
        },
        { binary: true }
    );
}

// ---------------------- MAIN ----------------------
async function main() {
    const args = process.argv.slice(2);

    if (args.length < 3) {
        console.error("Usage: node processor.mjs <input> <output> <mode>");
        process.exit(1);
    }

    const [inputPath, outputPath, mode] = args;

    try {
        if (mode === "pack") {
            await processPack(inputPath, outputPath);
            process.exit(0);
        }

        if (mode === "3d") {
            await process3D(inputPath, outputPath);
            process.exit(0);
        }

        console.error("Unknown mode:", mode);
        process.exit(1);

    } catch (err) {
        console.error("Error:", err);
        process.exit(1);
    }
}

main();
