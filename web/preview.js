import { app } from "../../scripts/app.js";
import { api } from "../../scripts/api.js";

export function updateApngPreview(node, message) {
    const file = message?.true_apng_preview?.[0];
    let state = node.__trueApngImagePreview;
    if (!file) {
        if (state) {
            state.visible = false;
            state.box.style.display = "none";
            state.image.removeAttribute("src");
            node.setDirtyCanvas?.(true, true);
        }
        return;
    }
    if (!state) {
        const box = document.createElement("div");
        Object.assign(box.style, { width: "100%", height: "100%", display: "flex", flexDirection: "column", gap: "4px", overflow: "hidden" });
        const image = document.createElement("img");
        image.alt = "APNG";
        Object.assign(image.style, {
            width: "100%", height: "calc(100% - 28px)", minHeight: "0", objectFit: "contain",
            backgroundColor: "#444",
            backgroundImage: "linear-gradient(45deg,#666 25%,transparent 25%),linear-gradient(-45deg,#666 25%,transparent 25%),linear-gradient(45deg,transparent 75%,#666 75%),linear-gradient(-45deg,transparent 75%,#666 75%)",
            backgroundSize: "16px 16px", backgroundPosition: "0 0,0 8px,8px -8px,-8px 0px",
        });
        const link = document.createElement("a");
        link.target = "_blank";
        link.rel = "noopener noreferrer";
        Object.assign(link.style, { color: "#ddd", fontSize: "12px", overflow: "hidden", textOverflow: "ellipsis", whiteSpace: "nowrap" });
        box.append(image, link);
        state = { box, image, link, visible: true };
        const widget = node.addDOMWidget("true_apng_preview", "APNG_PREVIEW", box, { serialize: false });
        widget.computeSize = () => [240, state.visible ? 260 : 0];
        node.__trueApngImagePreview = state;
        const computed = node.computeSize?.();
        if (computed && node.setSize) node.setSize([Math.max(node.size?.[0] ?? 0, computed[0]), Math.max(node.size?.[1] ?? 0, computed[1])]);
    }
    state.visible = true;
    state.box.style.display = "flex";
    const query = new URLSearchParams({ filename: file.filename, subfolder: file.subfolder ?? "", type: file.type ?? "output", rand: String(Date.now()) });
    const url = api.apiURL(`/view?${query}`);
    // Serve the original APNG bytes. No video tag, thumbnail conversion or
    // channel=rgb conversion, which would discard animation/transparency.
    state.image.src = url;
    state.link.href = url;
    state.link.textContent = file.filename;
    node.setDirtyCanvas?.(true, true);
}

app.registerExtension({
    name: "TrueAPNG.AnimatedImagePreview",
    beforeRegisterNodeDef(nodeType, nodeData) {
        if (!["TrueAPNGSaveVideo", "TrueAPNGSaveImages"].includes(nodeData.name)) return;
        const original = nodeType.prototype.onExecuted;
        nodeType.prototype.onExecuted = function (message) {
            original?.apply(this, arguments);
            updateApngPreview(this, message);
        };
        const removed = nodeType.prototype.onRemoved;
        nodeType.prototype.onRemoved = function () {
            const state = this.__trueApngImagePreview;
            if (state) {
                state.image.removeAttribute("src");
                state.box.remove();
                delete this.__trueApngImagePreview;
            }
            return removed?.apply(this, arguments);
        };
    },
});
