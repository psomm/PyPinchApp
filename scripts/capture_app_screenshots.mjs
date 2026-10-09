import { spawn } from "node:child_process";
import { mkdir, rm, writeFile } from "node:fs/promises";
import path from "node:path";
import process from "node:process";

const chromePath = "C:\\Program Files\\Google\\Chrome\\Application\\chrome.exe";
const appUrl = "http://127.0.0.1:8550";
const outputDir = path.resolve("docs/images");
const profileDir = path.resolve(".chrome-screenshot-profile");

await mkdir(outputDir, { recursive: true });
await rm(profileDir, { recursive: true, force: true });

const chrome = spawn(
  chromePath,
  [
    "--headless=new",
    "--use-angle=swiftshader",
    "--enable-unsafe-swiftshader",
    "--force-renderer-accessibility",
    "--hide-scrollbars",
    "--remote-debugging-pipe",
    `--user-data-dir=${profileDir}`,
    "--window-size=1440,1000",
    appUrl,
  ],
  { stdio: ["ignore", "ignore", "ignore", "pipe", "pipe"] },
);

const pause = (milliseconds) => new Promise((resolve) => setTimeout(resolve, milliseconds));

let commandId = 0;
let targetSessionId = null;
const pending = new Map();
let pipeBuffer = Buffer.alloc(0);
chrome.stdio[4].on("data", (chunk) => {
  pipeBuffer = Buffer.concat([pipeBuffer, chunk]);
  let separator = pipeBuffer.indexOf(0);
  while (separator !== -1) {
    const message = JSON.parse(pipeBuffer.subarray(0, separator).toString("utf8"));
    pipeBuffer = pipeBuffer.subarray(separator + 1);
    if (message.id && pending.has(message.id)) {
      const { resolve, reject } = pending.get(message.id);
      pending.delete(message.id);
      if (message.error) reject(new Error(message.error.message));
      else resolve(message.result);
    }
    separator = pipeBuffer.indexOf(0);
  }
});

function cdp(method, params = {}) {
  commandId += 1;
  const id = commandId;
  return new Promise((resolve, reject) => {
    pending.set(id, { resolve, reject });
    const message = { id, method, params };
    if (targetSessionId) message.sessionId = targetSessionId;
    chrome.stdio[3].write(`${JSON.stringify(message)}\0`);
  });
}

async function evaluate(expression) {
  const result = await cdp("Runtime.evaluate", {
    expression,
    awaitPromise: true,
    returnByValue: true,
  });
  if (result.exceptionDetails) throw new Error(result.exceptionDetails.text);
  return result.result.value;
}

async function waitForText(text) {
  for (let attempt = 0; attempt < 80; attempt += 1) {
    await evaluate(`document.querySelector("flt-semantics-placeholder")?.click()`);
    const nodes = (await cdp("Accessibility.getFullAXTree")).nodes;
    const found = nodes.some((candidate) => candidate.name?.value?.includes(text));
    if (found) return;
    await pause(250);
  }
  const diagnostics = await evaluate(`({
    url: location.href,
    title: document.title,
    bodyText: document.body?.innerText,
    bodyHtml: document.body?.innerHTML.slice(0, 2000),
    scripts: [...document.scripts].map(script => script.src || "inline"),
    resources: performance.getEntriesByType("resource").map(entry => entry.name)
  })`);
  throw new Error(`Text did not appear: ${text}\n${JSON.stringify(diagnostics, null, 2)}`);
}

async function clickText(text) {
  const nodes = (await cdp("Accessibility.getFullAXTree")).nodes;
  const node = nodes.find(
    (candidate) =>
      (candidate.name?.value === text || candidate.name?.value?.startsWith(`${text} `)) &&
      ["button", "tab", "menuitem", "radio", "link"].includes(candidate.role?.value),
  );
  if (!node?.backendDOMNodeId) throw new Error(`Clickable control not found: ${text}`);

  const box = await cdp("DOM.getBoxModel", { backendNodeId: node.backendDOMNodeId });
  const [x1, y1, x2, y2, x3, y3, x4, y4] = box.model.border;
  const x = (x1 + x2 + x3 + x4) / 4;
  const y = (y1 + y2 + y3 + y4) / 4;
  await cdp("Input.dispatchMouseEvent", { type: "mousePressed", x, y, button: "left", clickCount: 1 });
  await cdp("Input.dispatchMouseEvent", { type: "mouseReleased", x, y, button: "left", clickCount: 1 });
  await pause(500);
}

async function setViewport(width, height, mobile = false) {
  await cdp("Emulation.setDeviceMetricsOverride", {
    width,
    height,
    deviceScaleFactor: 1,
    mobile,
  });
  await pause(700);
}

async function screenshot(name) {
  const { data } = await cdp("Page.captureScreenshot", {
    format: "png",
    fromSurface: true,
    captureBeyondViewport: false,
  });
  await writeFile(path.join(outputDir, name), Buffer.from(data, "base64"));
}

try {
  const targets = await cdp("Target.getTargets");
  const target = targets.targetInfos.find(
    (candidate) => candidate.type === "page" && candidate.url === appUrl + "/",
  );
  if (!target) throw new Error("Chrome did not expose the PyPinch page target.");
  const attached = await cdp("Target.attachToTarget", { targetId: target.targetId, flatten: true });
  targetSessionId = attached.sessionId;

  await cdp("Page.enable");
  await cdp("Runtime.enable");
  await cdp("DOM.enable");
  await cdp("Accessibility.enable");
  await cdp("Page.reload", { ignoreCache: true });
  await setViewport(1440, 1000);
  await evaluate(`document.querySelector("flt-semantics-placeholder")?.click()`);
  await waitForText("Beispiel laden");

  await clickText("Beispiel laden");
  await waitForText("4 Streams geladen");
  await screenshot("desktop-input.png");

  await clickText("Analyse starten");
  await waitForText("Ergebnisübersicht");
  await screenshot("desktop-overview.png");

  await clickText("Details");
  await waitForText("Detaillierte Ergebnisse");
  await screenshot("desktop-details.png");

  await clickText("Übersicht");
  await setViewport(412, 915, true);
  await waitForText("Ergebnisübersicht");
  await screenshot("mobile-overview.png");
} finally {
  chrome.kill();
  if (chrome.exitCode === null) {
    await Promise.race([
      new Promise((resolve) => chrome.once("exit", resolve)),
      pause(5000),
    ]);
  }
  for (let attempt = 0; attempt < 10; attempt += 1) {
    try {
      await rm(profileDir, { recursive: true, force: true });
      break;
    } catch (error) {
      if (error.code !== "EBUSY" || attempt === 9) throw error;
      await pause(250);
    }
  }
}
