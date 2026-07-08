import fs from "fs";
import unzipper from "unzipper";
import path from "path";
import { loadImage } from "@napi-rs/canvas";
import { Readable } from "stream";
function unzipFile(zipFileBuffer, outputDir) {
  return new Promise((resolve, reject) => {
    const bufferStream = new Readable();
    bufferStream.push(zipFileBuffer);
    bufferStream.push(null);
    bufferStream.pipe(unzipper.Extract({ path: outputDir })).on("close", () => {
      resolve();
    }).on("error", (err) => {
      reject(err);
    });
  });
}
function clean(paths) {
  for (const pth of paths) {
    if (!fs.existsSync(pth)) continue;
    fs.rmSync(pth, { recursive: true, force: true });
  }
  return;
}
async function getScale(spriteSheetPath) {
  if (!fs.existsSync(spriteSheetPath))
    throw new Error("Path does not exist: " + spriteSheetPath);
  return ~~((await loadImage(spriteSheetPath)).height / 256);
}
function checkAndMkdir(folderPath) {
  if (fs.existsSync(folderPath)) return;
  try {
    fs.mkdirSync(folderPath);
  } catch (err) {
    throw new Error("Error while creating directory: " + err);
  }
  return;
}
function checkBedrock(packPath) {
  let bedrock = false;
  if (!fs.existsSync(packPath))
    throw new Error("Path does not exist: " + packPath);
  if (!fs.lstatSync(packPath).isDirectory())
    throw new Error("Path is not a directory: " + packPath);
  if (packPath.split(".").pop() === "mcpack" && fs.readdirSync(packPath).includes("manifest.json")) {
    bedrock = true;
  }
  try {
    let subfiles = fs.readdirSync(packPath);
    if (subfiles.length <= 1) packPath = path.join(packPath, subfiles[0]);
    if (fs.readdirSync(packPath).includes("manifest.json")) bedrock = true;
  } catch (err) {
    throw new Error("Error while reading directory: " + err);
  }
  return bedrock;
}
function convertBedrock(parentDir) {
  if (!fs.existsSync(parentDir)) {
    console.error(`Source directory does not exist: ${parentDir}`);
    return;
  }
  const subfiles = fs.readdirSync(parentDir);
  if (subfiles.length === 1) {
    const subfolder = path.join(parentDir, subfiles[0]);
    if (fs.statSync(subfolder).isDirectory()) {
      const subfolderContents = fs.readdirSync(subfolder);
      for (const item of subfolderContents) {
        const itemPath = path.join(subfolder, item);
        const targetPath = path.join(parentDir, item);
        try {
          fs.renameSync(itemPath, targetPath);
        } catch (error) {
          console.error(
            `Error moving ${itemPath} to ${targetPath}:`,
            error
          );
        }
      }
      try {
        fs.rmdirSync(subfolder);
      } catch (error) {
        if (error.split(" ")[0] === "ENOTEMPTY") {
          console.warn(
            `Directory not empty after moving contents: ${subfolder}`
          );
        } else {
          console.error(
            `Error removing directory ${subfolder}:`,
            error
          );
        }
      }
    } else {
      console.error(
        `The only item in the directory is not a folder: ${subfolder}`
      );
    }
  }
  return;
}
export {
  checkAndMkdir,
  checkBedrock,
  clean,
  convertBedrock,
  getScale,
  unzipFile
};
