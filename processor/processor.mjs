// processor/processor.mjs
import fs from "fs";
import path from "path";
import make from "./src.js"; // همون main از src.txt

const __dirname = path.dirname(new URL(import.meta.url).pathname);

async function main() {
    const args = process.argv.slice(2);

    if (args.length < 4) {
        console.error("Usage: node processor.mjs <inputPack> <outputPng> <xpPercent> <upscaleRate>");
        process.exit(1);
    }

        // Read CLI arguments
    const args = process.argv.slice(2);

    const [inputPath, outputPath, xpPercentRaw, upscaleRateRaw] = args;

    const xpPercent = Number(xpPercentRaw);
    const upscaleRate = Number(upscaleRateRaw);

    if (Number.isNaN(xpPercent) || Number.isNaN(upscaleRate)) {
        console.error("xpPercent and upscaleRate must be numbers.");
        process.exit(1);
    }

    try {
        const packBuffer = fs.readFileSync(inputPath);
        const packName = path.basename(inputPath);

        const imgBuffer = await make(
            packName,
            packBuffer,
            upscaleRate,
            xpPercent
        );

        fs.writeFileSync(outputPath, imgBuffer);
        console.log("OK");
        process.exit(0);
    } catch (err) {
        console.error("Error while processing pack:", err);
        process.exit(1);
    }
}

if (args[0] === "--paths") {
    const { getPaths } = await import("./helpers/paths.js");
    console.log(JSON.stringify(getPaths("SYS")));
    process.exit(0);
}

if (args[0] === "--resume") {
    const [, outputPath, xpPercentRaw, upscaleRateRaw] = args;
    try {
        const imgBuffer = await continueProcessing(Number(upscaleRateRaw), Number(xpPercentRaw));
        fs.writeFileSync(outputPath, imgBuffer);
        console.log("OK");
        process.exit(0);
    } catch (err) {
        console.error("Error while resuming:", err);
        process.exit(1);
    }
}


main();
