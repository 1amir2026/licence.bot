// processor/src.js
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

        // پاک کردن فولدر قبلی (جلوگیری از تداخل)
        if (fs.existsSync(folderPaths.packFolder)) {
            fs.rmSync(folderPaths.packFolder, { recursive: true, force: true });
        }

        // Unzip pack into temp folder
        await unzipFile(packZipBuffer, folderPaths.packFolder);

        const bedrock = checkBedrock(folderPaths.packFolder);
        if (bedrock) convertBedrock(folderPaths.packFolder);

        setValue("bedrock", bedrock, "insert");

        initializePaths(getPaths("SYS"));

        const scalingFactor = await getScale(getPaths("SYS").packIconsPath);
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
    // Initialize config and paths
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
