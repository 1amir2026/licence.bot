// processor/src.js
import fs from "fs";
import { configPath, createConfig, setValue } from "./utils/configUtils.js";
import { getPaths, initializePaths } from "./helpers/paths.js";
import {
    checkBedrock,
    clean,
    convertBedrock,
    getScale,
    unzipFile,
    findGuiSprite,
    findWidgetsSprite
} from "./utils/utils.js";
import { crop, imageDimsFix, processImage } from "./helpers/imageProcessing.js";

async function initialize(
    packFileName,
    packZipBuffer,
    upscaleRate,
    xpPercent
) {
    createConfig();

    try {
        setValue("packFileName", packFileName, "insert");

        const folderPaths = getPaths("SYS");

        if (fs.existsSync(folderPaths.packFolder)) {
            fs.rmSync(folderPaths.packFolder, { recursive: true, force: true });
        }

        await unzipFile(packZipBuffer, folderPaths.packFolder);

        console.log("📦 Unzip completed. Root:", fs.readdirSync(folderPaths.packFolder));

        const bedrock = checkBedrock(folderPaths.packFolder);
        if (bedrock) convertBedrock(folderPaths.packFolder);

        setValue("bedrock", bedrock, "insert");

        initializePaths(getPaths("SYS"));

        // === بخش جدید: پیدا کردن icons.png هوشمند ===
    const iconsPath = findGuiSprite(folderPaths.packFolder);
    if (!iconsPath) {
        throw new Error("MANUAL_SPRITE_NEEDED: sprite (icons.png/gui.png) not found in pack");
    }
    setValue("packIconsPath", iconsPath, "insert");

    const widgetsPath = findWidgetsSprite(folderPaths.packFolder) || iconsPath;
    setValue("packWidgetsPath", widgetsPath, "insert");

    const scalingFactor = await getScale(iconsPath);

        setValue("upscaleRate", upscaleRate, "insert");
        setValue("xpPercent", xpPercent, "insert");

    } catch (err) {
        console.error("Initialization failed:", err.message || err);
        throw new Error("Error while initialising: " + (err.message || err));
    }
}

export default async function main(
    packName,
    packZipBuffer,
    upscaleRate,
    xpPercent
) {
    await initialize(packName, packZipBuffer, upscaleRate, xpPercent);

    const systemPaths = getPaths("SYS");

    // Fix image dimensions
    try {
        await imageDimsFix(
            systemPaths.packIconsPath,
            systemPaths.packWidgetsPath
        );
    } catch (err) {
        throw new Error(err.toString());
    }

    // Crop icons and GUI
    await crop("ICON");
    await crop("GUI");

    // Process final UI image
    const uiImageBuffer = await processImage();

    // Cleanup
    clean([systemPaths.tempPath, configPath]);

    return uiImageBuffer;
}

export async function continueProcessing(upscaleRate, xpPercent) {
    const systemPaths = getPaths("SYS");
    const scalingFactor = await getScale(systemPaths.packIconsPath);
    setValue("scalingFactor", scalingFactor, "insert");
    setValue("upscaleRate", upscaleRate, "insert");
    setValue("xpPercent", xpPercent, "insert");

    await imageDimsFix(systemPaths.packIconsPath, systemPaths.packWidgetsPath);
    await crop("ICON");
    await crop("GUI");
    const uiImageBuffer = await processImage();
    clean([systemPaths.tempPath, configPath]);
    return uiImageBuffer;
}
