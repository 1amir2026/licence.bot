import fs from "fs";
import path from "path";

export const configPath = path.join(process.cwd(), "config.json");

export function createConfig() {
    if (fs.existsSync(configPath)) fs.rmSync(configPath);
    fs.writeFileSync(configPath, JSON.stringify({}));
    return configPath;
}

export function getConfig() {
    if (!fs.existsSync(configPath))
        throw new Error("Config file not found: " + configPath);
    return JSON.parse(fs.readFileSync(configPath).toString());
}

export function setValue(key, value, mode = "insert") {
    if (!fs.existsSync(configPath))
        throw new Error("Config file missing: " + configPath);

    let configJson = JSON.parse(fs.readFileSync(configPath).toString());

    if (mode === "insert" && key in configJson)
        throw new Error(`Key "${key}" already exists.`);

    if (mode === "modify" && !(key in configJson))
        throw new Error(`Key "${key}" does not exist.`);

    configJson[key] = value;
    fs.writeFileSync(configPath, JSON.stringify(configJson));
}

export function deleteValue(key) {
    if (!fs.existsSync(configPath))
        throw new Error("Config file missing: " + configPath);

    let configJson = JSON.parse(fs.readFileSync(configPath).toString());

    if (!(key in configJson))
        throw new Error(`Key "${key}" does not exist.`);

    delete configJson[key];
    fs.writeFileSync(configPath, JSON.stringify(configJson));
}
