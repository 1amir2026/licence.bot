import path from "path";
import { getConfig } from "../utils/configUtils.js";
import { configPath } from "../utils/configUtils.js";
import { checkAndMkdir } from "../utils/utils.js";
function getPaths(type) {
  const configValues = getConfigValues();
  if (!configValues) {
    throw new Error("Couldn't fetch config - paths.");
  }
  let { bedrock, packFileName } = configValues;
  const tempPath = path.join(process.cwd(), "temp");
  let packSavePath = path.join(tempPath, packFileName);
  const guiFolderPath = bedrock === true ? path.join(packSavePath, "textures", "gui") : bedrock === false ? path.join(packSavePath, "assets", "minecraft", "textures", "gui") : bedrock === void 0 ? "" : "";
  const iconsPath = path.join(guiFolderPath, "icons.png");
  const widgetsPath = bedrock === true ? path.join(guiFolderPath, "gui.png") : bedrock === false ? path.join(guiFolderPath, "widgets.png") : bedrock === void 0 ? "" : "";
  const iconsSavePath = path.join(tempPath, "icons");
  const widgetsSavePath = path.join(tempPath, "widgets");
  const _configPath = configPath;
  const sysPaths = {
    tempPath,
    packFolder: packSavePath,
    packGuiFolder: guiFolderPath,
    packIconsPath: iconsPath,
    packWidgetsPath: widgetsPath,
    tempIconsPath: iconsSavePath,
    tempWidgetsPath: widgetsSavePath,
    configPath: _configPath
  };
  if (type === "SYS") return sysPaths;
  const iconsPaths = {
    xpBg: path.join(iconsSavePath, "xpBg.png"),
    hungerBg: path.join(iconsSavePath, "hungerBg.png"),
    heartBg: path.join(iconsSavePath, "heartBg.png"),
    xp: path.join(iconsSavePath, "xp.png"),
    hunger: path.join(iconsSavePath, "hunger.png"),
    heart: path.join(iconsSavePath, "heart.png"),
    armor: path.join(iconsSavePath, "armor.png")
  };
  if (type === "ICON") return iconsPaths;
  const guiPaths = {
    twoSlots: path.join(widgetsSavePath, "firstTwoSlots.png"),
    lastSlot: path.join(widgetsSavePath, "lastSlot.png"),
    selector: path.join(widgetsSavePath, "selector.png")
  };
  if (type === "GUI") return guiPaths;
  throw new Error(`Invalid type: ${type}`);
}
function getConfigValues() {
  try {
    const config = getConfig();
    const bedrock = config.bedrock ?? void 0;
    const packFileName = config.packFileName ?? void 0;
    return { bedrock, packFileName };
  } catch (err) {
    console.error("Error fetching config: ", err);
    return void 0;
  }
}
function initializePaths(paths) {
  for (const pth in paths) {
    if (paths[pth] === void 0) continue;
    try {
      checkAndMkdir(paths[pth]);
    } catch (err) {
      console.error("Error while initialising paths: " + err);
    }
  }
}
export {
  getPaths,
  initializePaths
};
