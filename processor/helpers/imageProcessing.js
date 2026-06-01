import { getPaths } from "./paths.js";
import {
    combineIcons,
    cropIcon,
    repeatIcon,
    savePngBuffer,
    upscaleImage,
} from "../utils/imageUtils.js";
import { getCoordinates, getDestinationCoordinates } from "./coordinates.js";
import { loadImage } from "@napi-rs/canvas";
import { getConfig } from "../utils/configUtils.js";

export async function crop(type) {
    const systemPaths = getPaths("SYS");
    const imagePaths = getPaths(type);
    const imageCoordinates = getCoordinates(type);

    const spriteSheetPath =
        type === "ICON"
            ? systemPaths.packIconsPath
            : systemPaths.packWidgetsPath;

    const imagePathEntries = Object.entries(imagePaths);
    const imageCoordinateEntries = Object.entries(imageCoordinates);

    for (let i = 0; i < imagePathEntries.length; i++) {
        const [, path] = imagePathEntries[i];
        const [, coords] = imageCoordinateEntries[i];

        await cropIcon(
            spriteSheetPath,
            path,
            coords.x,
            coords.y,
            coords.width,
            coords.height
        );
    }
}

async function combine() {
    const iconsInfo = generateIconInfo("ICON");
    const guiInfo = generateIconInfo("GUI");

    let repeatKeys = ["heart", "armor", "hunger"];
    repeatKeys.push(...repeatKeys.map((x) => x + "Bg"));

    for (const icon of iconsInfo) {
        if (repeatKeys.includes(icon.name)) {
            icon.destCoordinates.width *= 3;
            icon.path = await repeatIcon(icon.path, 3);
        }
    }

    const iconsCanvas = await combineIcons(iconsInfo);
    const guiCanvas = await combineIcons(guiInfo);

    const finalIcons = {
        name: "icons",
        path: iconsCanvas.toBuffer("image/png"),
        destCoordinates: {
            x: 0,
            y: 0,
            width: iconsCanvas.width,
            height: iconsCanvas.height,
        },
    };

    const finalGui = {
        name: "gui",
        path: guiCanvas.toBuffer("image/png"),
        destCoordinates: {
            x: 0,
            y: iconsCanvas.height,
            width: guiCanvas.width,
            height: guiCanvas.height,
        },
    };

    const finalCanvas = await combineIcons([finalIcons, finalGui]);
    return finalCanvas.toBuffer("image/png");
}

function generateIconInfo(type) {
    const imagePaths = getPaths(type);
    const destCoords = getDestinationCoordinates(type);

    const entries = Object.entries(imagePaths);
    const coords = Object.entries(destCoords);

    return entries.map(([name, path], i) => ({
        name,
        path,
        destCoordinates: coords[i][1],
    }));
}

export async function processImage() {
    const uiBuffer = await combine();
    const upscaleRate = getUpscaleRate();

    if (upscaleRate > 1) {
        return await upscaleImage(uiBuffer, upscaleRate);
    }

    return uiBuffer;
}

function getUpscaleRate() {
    const config = getConfig();
    return config.upscaleRate;
}

export async function imageDimsFix(iconsPath, widgetsPath) {
    const widgetsDims = {
        width: (await loadImage(widgetsPath)).width,
        height: (await loadImage(widgetsPath)).height,
    };

    const iconsDims = {
        width: (await loadImage(iconsPath)).width,
        height: (await loadImage(iconsPath)).height,
    };

    if (widgetsDims.width === iconsDims.width) return;

    if (widgetsDims.width < iconsDims.width) {
        const buffer = await upscaleImage(
            widgetsPath,
            ~~(iconsDims.width / widgetsDims.width)
        );
        savePngBuffer(buffer, widgetsPath);
    } else {
        const buffer = await upscaleImage(
            iconsPath,
            ~~(widgetsDims.width / iconsDims.width)
        );
        savePngBuffer(buffer, iconsPath);
    }
}
