import { readFile } from "node:fs/promises";
import assert from "node:assert/strict";

const calls = [];
globalThis.testApp = {
    async handleFile(file, ...args) { calls.push({ file, args, context: this }); return "loaded"; },
    registerExtension(extension) { this.extension = extension; },
};
globalThis.testMetadata = { workflow: '{"nodes":[]}' };
let source = await readFile(new URL("../web/apng.js", import.meta.url), "utf8");
source = source.replace(/^import .*;$/gm, "");
source = "const app = globalThis.testApp; const getPngMetadata = async () => { if(globalThis.parseError) throw Error('bad'); return globalThis.testMetadata; };\n" + source;
const { normalizeWorkflowFile } = await import(`data:text/javascript;base64,${Buffer.from(source).toString("base64")}`);

const input = new File(["original bytes"], "sample.apng", { type: "image/apng", lastModified: 12345 });
const normalized = await normalizeWorkflowFile(input);
assert.equal(normalized.name, "sample.png");
assert.equal(normalized.type, "image/png");
assert.equal(normalized.lastModified, 12345);
assert.equal(await normalized.text(), await input.text());
assert.equal(input.name, "sample.apng");
assert.equal((await normalizeWorkflowFile(new File(["x"], "OLD.APNG"))).name, "OLD.png");
const ordinary = new File(["x"], "photo.png", { type: "image/png" });
assert.equal(await normalizeWorkflowFile(ordinary), ordinary);
globalThis.testMetadata = {};
assert.equal(await normalizeWorkflowFile(input), input);
globalThis.parseError = true;
assert.equal(await normalizeWorkflowFile(input), input);
globalThis.parseError = false;
globalThis.testMetadata = { workflow: '{"nodes":[]}' };
testApp.extension.setup();
const wrapped = testApp.handleFile;
testApp.extension.setup();
assert.equal(testApp.handleFile, wrapped);
assert.equal(await testApp.handleFile(input, "file_drop", { deferWarnings: true }), "loaded");
assert.equal(calls.length, 1);
assert.equal(calls[0].file.type, "image/png");
assert.equal(calls[0].context, testApp);
assert.deepEqual(calls[0].args, ["file_drop", { deferWarnings: true }]);
console.log("APNG workflow import tests passed (normalization, passthrough, errors, context and arguments).");
