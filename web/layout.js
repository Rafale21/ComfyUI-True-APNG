import { app } from "../../scripts/app.js";

// Older workflows store widget values positionally. Move the resize selector
// together with its value before ComfyUI configures the new widget layout.
export function migrateWidgetLayout(graphData) {
    const stack = [graphData];
    const visited = new WeakSet();
    const filters = ["lanczos", "lanczos_progressive", "box", "bicubic", "bilinear", "hamming", "nearest"];
    while (stack.length) {
        const item = stack.pop();
        if (!item || typeof item !== "object" || visited.has(item)) continue;
        visited.add(item);
        if (["TrueAPNGSaveVideo", "TrueAPNGSaveImages"].includes(item.type) && Array.isArray(item.widgets_values)) {
            const offset = item.type === "TrueAPNGSaveVideo" ? 2 : 0;
            const values = item.widgets_values;
            const current = item.properties?.true_apng_layout >= 7 ||
                (filters.includes(values[offset + 6]) && typeof values[offset + 2] === "number" && typeof values[offset + 3] === "number");
            if (!current) {
                if (typeof values[offset + 4] === "boolean") {
                    const filter = filters.includes(values[offset + 7]) ? values.splice(offset + 7, 1)[0] : "lanczos";
                    values.splice(offset + 4, 0, filter);
                }
                const defaults = ["APNG/ComfyUI", 0, 6, 0, "lanczos", true, true, 100, true, 100, true];
                const old = defaults.map((value, i) => values[offset + i] ?? value);
                old[9] = (100 - old[9]) / 10; // accuracy -> tolerance, preserving the behavior.
                const prefix = values.slice(0, offset);
                const tail = values.slice(offset + defaults.length);
                values.splice(0, values.length, ...prefix, old[0], old[1], 0, 0, ...old.slice(2), ...tail);
            } else if (!(item.properties?.true_apng_layout >= 8)) {
                // 1.7 used a 0..100 slider capped at 10% actual tolerance.
                if (typeof values[offset + 11] === "number") values[offset + 11] /= 10;
            }
            item.properties ??= {};
            item.properties.true_apng_layout = 8;
        }
        for (const value of Object.values(item)) {
            if (value && typeof value === "object") stack.push(value);
        }
    }
}

app.registerExtension({
    name: "TrueAPNG.WidgetLayout",
    beforeRegisterNodeDef(nodeType, nodeData) {
        if (!["TrueAPNGSaveVideo", "TrueAPNGSaveImages"].includes(nodeData.name)) return;
        const original = nodeType.prototype.onSerialize;
        nodeType.prototype.onSerialize = function (data) {
            const result = original?.apply(this, arguments);
            if (data) {
                data.properties ??= {};
                data.properties.true_apng_layout = 8;
            }
            return result;
        };
    },
    beforeConfigureGraph(graphData) {
        migrateWidgetLayout(graphData);
    },
});
