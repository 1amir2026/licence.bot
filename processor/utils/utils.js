import fs from "fs";
import unzipper from "unzipper";
import path from "path";
import { loadImage } from "@napi-rs/canvas";
import { Readable } from "stream";

export function unzipFile(zipBuffer, outputDir) {
    return new Promise((resolve, reject) => {
        if (!zipBuffer || zipBuffer.length === 0) {
            return reject(new Error("Empty or invalid zip buffer"));
        }

        const stream = new Readable();
        stream.push(zipBuffer);
        stream.push(null);

        stream
            .pipe(unzipper.Extract({ path: outputDir }))
            .on("close", () => {
                // چک اضافی بعد از unzip
                if (!fs.existsSync(outputDir) || fs.readdirSync(outputDir).length === 0) {
                    reject(new Error("Unzip failed - no files extracted"));
                } else {
                    resolve();
                }
            })
            .on("error", (err) => {
                console.error("Unzip error:", err.message);
                reject(new Error("Unzip failed: " + err.message));
            });
    });
}

export function clean(paths) {
    for (const p of paths) {
        if (fs.existsSync(p)) fs.rmSync(p, { recursive: true, force: true });
    }
}

export async function getScale(spriteSheetPath) {
    if (!fs.existsSync(spriteSheetPath))
        throw new Error("Missing sprite sheet: " + spriteSheetPath);
    return ~~((await loadImage(spriteSheetPath)).height / 256);
}

export function checkAndMkdir(folderPath) {
    if (!folderPath) return;
    try {
        if (!fs.existsSync(folderPath)) {
            fs.mkdirSync(folderPath, { recursive: true });
        }
    } catch (err) {
        if (!folderPath.endsWith('.png') && !folderPath.endsWith('.json')) {
            console.error(`Failed to mkdir: ${folderPath}`, err.message);
        }
    }
}

export function checkBedrock(packPath) {
    if (!fs.existsSync(packPath))
        throw new Error("Missing pack path: " + packPath);

    let bedrock = false;

    if (fs.readdirSync(packPath).includes("manifest.json"))
        bedrock = true;

    return bedrock;
}

export function convertBedrock(parentDir) {
    const subfiles = fs.readdirSync(parentDir);
    if (subfiles.length !== 1) return;

    const subfolder = path.join(parentDir, subfiles[0]);
    if (!fs.statSync(subfolder).isDirectory()) return;

    for (const item of fs.readdirSync(subfolder)) {
        fs.renameSync(
            path.join(subfolder, item),
            path.join(parentDir, item)
        );
    }

    fs.rmdirSync(subfolder);
}

export function findGuiSprite(packRoot) {
    const possiblePaths = [
        // مسیر اصلی
        `${packRoot}/assets/minecraft/textures/gui/icons.png`,
        `${packRoot}/assets/minecraft/textures/gui/gui.png`,
        `${packRoot}/textures/gui/icons.png`,
        `${packRoot}/textures/gui/gui.png`,
        `${packRoot}/textures/gui/icon.png`,
        `${packRoot}/textures/gui/icons1.png`,
        
        // مسیرهای رایج Bedrock
        `${packRoot}/assets/minecraft/textures/gui/container/icons.png`,
        `${packRoot}/textures/gui/container/icons.png`,
        
        // جستجوی عمیق‌تر (اگر لازم شد)
        // `${packRoot}/**/*icons*.png`  ← بعداً اگر لازم شد پیاده‌سازی کن
    ];

    for (const path of possiblePaths) {
        if (fs.existsSync(path)) {
            return path;
        }
    }

    // جستجوی ساده در gui فولدر
    const guiFolders = [
        `${packRoot}/assets/minecraft/textures/gui`,
        `${packRoot}/textures/gui`,
        `${packRoot}/assets/minecraft/textures/gui/container`
    ];

    for (const guiDir of guiFolders) {
        if (fs.existsSync(guiDir)) {
            const files = fs.readdirSync(guiDir);
            console.log(`GUI folder ${guiDir} contains:`, files);
            
            for (const file of files) {
                if (file.toLowerCase().includes('icon') && file.endsWith('.png')) {
                    return `${guiDir}/${file}`;
                }
            }
        }
    }

    return null;
}
