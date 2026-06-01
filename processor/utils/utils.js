import fs from "fs";
import unzipper from "unzipper";
import path from "path";
import { loadImage } from "@napi-rs/canvas";
import { Readable } from "stream";

export function unzipFile(zipBuffer, outputDir) {
    return new Promise((resolve, reject) => {
        const stream = new Readable();
        stream.push(zipBuffer);
        stream.push(null);

        stream
            .pipe(unzipper.Extract({ path: outputDir }))
            .on("close", resolve)
            .on("error", reject);
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
    if (!fs.existsSync(folderPath)) fs.mkdirSync(folderPath);
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
