import { app } from "../../scripts/app.js";
import { getPngMetadata } from "../../scripts/pnginfo.js";

// APNG has the PNG binary structure, but its MIME type/extension is not
// recognized by every ComfyUI workflow importer. Only normalize files that
// actually carry workflow metadata; leave ordinary animation imports alone.
export async function normalizeWorkflowFile(file) {
    if (!file || !(/\.apng$/i.test(file.name ?? "") || file.type === "image/apng")) {
        return file;
    }
    let metadata;
    try {
        metadata = await getPngMetadata(file);
    } catch {
        return file;
    }
    if (!metadata?.workflow && !metadata?.prompt && !metadata?.parameters) {
        return file;
    }
    const name = /\.apng$/i.test(file.name) ? file.name.replace(/\.apng$/i, ".png") : `${file.name}.png`;
    // Virtual File only: never rename or alter the original file on disk.
    return new File([file], name, { type: "image/png", lastModified: file.lastModified });
}

app.registerExtension({
    name: "TrueAPNG.WorkflowImport",
    setup() {
        const original = app.handleFile;
        if (typeof original !== "function" || original.__trueAPNGImport) return;
        const handler = async function (file, ...args) {
            return original.call(this, await normalizeWorkflowFile(file), ...args);
        };
        handler.__trueAPNGImport = true;
        app.handleFile = handler;
    },
});
