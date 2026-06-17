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

/**
 * جستجوی بازگشتی در تمام فولدرها برای پیدا کردن icons.png یا gui.png
 * @param {string} dir - دایرکتوری برای جستجو
 * @param {number} maxDepth - حداکثر عمق جستجو
 * @returns {string|null}
 */

// به جای امضای فعلی:
function findPngRecursive(dir, targetNames, maxDepth = 6) {
    if (maxDepth <= 0 || !fs.existsSync(dir)) return null;
    let entries;
    try { entries = fs.readdirSync(dir, { withFileTypes: true }); } catch { return null; }
    for (const entry of entries) {
        if (entry.isFile() && targetNames.includes(entry.name.toLowerCase())) {
            return path.join(dir, entry.name);
        }
    }
    for (const entry of entries) {
        if (entry.isDirectory()) {
            const found = findPngRecursive(path.join(dir, entry.name), targetNames, maxDepth - 1);
            if (found) return found;
        }
    }
    return null;
}

export function findGuiSprite(packRoot) {
    const candidates = [];

    const possibleDirs = [
        `${packRoot}/assets/minecraft/textures/gui`,
        `${packRoot}/assets/minecraft/textures/gui/container`,
        `${packRoot}/assets/minecraft/textures/ui`,
        `${packRoot}/assets/minecraft/textures/gui/sprites`,
        `${packRoot}/textures/gui`,
        `${packRoot}/textures/gui/container`,
        `${packRoot}/textures/ui`,
        `${packRoot}/textures/gui/sprites`,
    ];

    const possibleNames = [
        "icons.png",
        "gui.png",
        "icon.png",
        "icons1.png",
        "widgets.png",
        "ui.png",
        "hud.png",
        "hotbar.png"
    ];

    for (const dir of possibleDirs) {
        if (!fs.existsSync(dir)) continue;

        const files = fs.readdirSync(dir);
        for (const file of files) {
            if (possibleNames.includes(file.toLowerCase())) {
                candidates.push(path.join(dir, file));
            }
        }
    }

    // اگر چند فایل پیدا شد، icons.png را اولویت بده
    const best = candidates.find(p => p.toLowerCase().includes("icons.png"))
        || candidates.find(p => p.toLowerCase().includes("gui.png"))
        || candidates[0];

    if (best) {
        console.log("✅ GUI sprite found:", best);
        return best;
    }

    // fallback: deep search
    const deep = findPngRecursive(packRoot, possibleNames, 6);
    if (deep) {
        console.log("🔎 Found via deep search:", deep);
        return deep;
    }

    return null;
}

/**
 * ساختار فایل‌های پک رو برای نمایش در پیام خطا لاگ می‌کنه
 * @param {string} packRoot
 * @returns {string} - لیست فایل‌ها به صورت متن
 */
export function getPackStructureInfo(packRoot) {
    const lines = [];
    function walk(dir, depth = 0) {
        if (depth > 4) return;
        let entries;
        try {
            entries = fs.readdirSync(dir, { withFileTypes: true });
        } catch {
            return;
        }
        for (const entry of entries) {
            const indent = "  ".repeat(depth);
            lines.push(`${indent}${entry.isDirectory() ? "📁" : "📄"} ${entry.name}`);
            if (entry.isDirectory() && depth < 3) {
                walk(path.join(dir, entry.name), depth + 1);
            }
        }
    }
    walk(packRoot);
    return lines.slice(0, 40).join("\n"); // حداکثر ۴۰ خط
}

export function findWidgetsSprite(packRoot) {
    const directPaths = [
        `${packRoot}/assets/minecraft/textures/gui/widgets.png`,
        `${packRoot}/textures/gui/gui.png`,
        `${packRoot}/textures/gui/widgets.png`,
    ];
    for (const p of directPaths) if (fs.existsSync(p)) return p;

    const guiFolders = [
        `${packRoot}/assets/minecraft/textures/gui`,
        `${packRoot}/textures/gui`,
    ];
    for (const guiDir of guiFolders) {
        if (fs.existsSync(guiDir)) {
            for (const file of fs.readdirSync(guiDir)) {
                if (file.toLowerCase().includes("widget") && file.endsWith(".png")) {
                    return path.join(guiDir, file);
                }
            }
        }
    }
    return findPngRecursive(packRoot, ["widgets.png", "gui.png", "icon.png"], 6);
}
