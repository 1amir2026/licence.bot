import { createCanvas, loadImage } from "@napi-rs/canvas";
import fs from "fs";
import sharp from "sharp";

// Upscale image
export async function upscaleImage(input, scale) {
    const image = sharp(input);
    const metadata = await image.metadata();

    return await image
        .resize(metadata.width * scale, metadata.height * scale, {
            kernel: sharp.kernel.nearest,
        })
        .toBuffer();
}

// Combine multiple icons into one canvas
export async function combineIcons(icons) {
    // Calculate canvas size
    let maxWidth = 0;
    let maxHeight = 0;

    for (const icon of icons) {
        const { x, y, width, height } = icon.destCoordinates;
        maxWidth = Math.max(maxWidth, x + width);
        maxHeight = Math.max(maxHeight, y + height);
    }

    const canvas = createCanvas(maxWidth, maxHeight);
    const ctx = canvas.getContext("2d");

    for (const icon of icons) {
        const img = await loadImage(icon.path);
        ctx.drawImage(
            img,
            icon.destCoordinates.x,
            icon.destCoordinates.y,
            img.width,
            img.height
        );
    }

    return canvas;
}

// Crop icon from sprite sheet
export async function cropIcon(spriteSheet, outputPath, x, y, w, h) {
    const img = await loadImage(spriteSheet);
    const canvas = createCanvas(w, h);
    const ctx = canvas.getContext("2d");

    ctx.drawImage(img, x, y, w, h, 0, 0, w, h);

    fs.writeFileSync(outputPath, canvas.toBuffer("image/png"));
}

// Repeat icon horizontally
export async function repeatIcon(imagePath, times) {
    const img = await loadImage(imagePath);
    const canvas = createCanvas(img.width * times, img.height);
    const ctx = canvas.getContext("2d");

    for (let i = 0; i < times; i++) {
        ctx.drawImage(img, img.width * i, 0);
    }

    return canvas.toBuffer("image/png");
}

// Save PNG buffer
export function savePngBuffer(buffer, outputPath) {
    fs.writeFileSync(outputPath, buffer);
}
