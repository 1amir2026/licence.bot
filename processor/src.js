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
} from "./utils/utils.js";
import { crop, imageDimsFix, processImage } from "./helpers/imageProcessing.js";

async function initialize(
    packFileName,
    packZipBuffer,
    upscaleRate,
    xpPercent
) {
    createConfig(); // Create config.json

    try {
        // Save pack name
        setValue("packFileName", packFileName, "insert");

        const folderPaths = getPaths("SYS");

        // پاک کردن فولدر قبلی
        if (fs.existsSync(folderPaths.packFolder)) {
            fs.rmSync(folderPaths.packFolder, { recursive: true, force: true });
        }

        // Unzip pack
        await unzipFile(packZipBuffer, folderPaths.packFolder);

        // لاگ برای دیباگ (بعد از unzip)
        console.log("Unzip completed. Root contents:", fs.readdirSync(folderPaths.packFolder));

        const bedrock = checkBedrock(folderPaths.packFolder);
        if (bedrock) convertBedrock(folderPaths.packFolder);

        setValue("bedrock", bedrock, "insert");

        initializePaths(getPaths("SYS"));

        // چک icons.png
        const iconsPath = getPaths("SYS").packIconsPath;
        if (!fs.existsSync(iconsPath)) {
            console.error("Missing icons.png at:", iconsPath);
            console.log("GUI folder contents:", fs.existsSync(getPaths("SYS").packGuiFolder) 
                ? fs.readdirSync(getPaths("SYS").packGuiFolder) 
                : "GUI folder not found");
            throw new Error(`Missing sprite sheet: ${iconsPath}`);
        }

        const scalingFactor = await getScale(iconsPath);
        setValue("scalingFactor", scalingFactor, "insert");

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
