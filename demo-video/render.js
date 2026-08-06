/**
 * Render the DemoVideo composition to MP4 using Remotion's renderMedia API.
 * Provides onBrowserDownload to use system Chrome instead of downloading.
 */
const { bundle } = require("@remotion/bundler");
const { renderMedia, selectComposition } = require("@remotion/renderer");
const path = require("path");
const fs = require("fs");

const CHROME_PATH = "C:\\Program Files\\Google\\Chrome\\Application\\chrome.exe";

async function render() {
  console.log("[1/3] Bundling Remotion project...");
  const entryPoint = path.resolve(__dirname, "src", "index.ts");
  const bundled = await bundle({
    entryPoint,
    publicDir: path.resolve(__dirname, "public"),
    onProgress: (progress) => {
      if (progress % 25 === 0) {
        console.log(`  Bundle progress: ${progress}%`);
      }
    },
  });
  console.log("  Bundle complete:", bundled);

  const browserExecutable = CHROME_PATH;
  console.log("  Using Chrome:", browserExecutable);
  console.log("  Chrome exists:", fs.existsSync(browserExecutable));

  console.log("[2/3] Selecting composition...");
  const composition = await selectComposition({
    serveUrl: bundled,
    id: "DemoVideo",
    inputProps: {},
    browserExecutable,
    onBrowserDownload: () => {
      // Return the system Chrome path instead of downloading
      return {
        executablePath: browserExecutable,
      };
    },
  });
  console.log("  Composition:", {
    id: composition.id,
    durationInFrames: composition.durationInFrames,
    fps: composition.fps,
    width: composition.width,
    height: composition.height,
  });

  console.log("[3/3] Rendering video...");
  const outputPath = path.resolve(__dirname, "out", "demo-video.mp4");

  await renderMedia({
    composition,
    serveUrl: bundled,
    codec: "h264",
    outputLocation: outputPath,
    browserExecutable,
    onProgress: ({ progress }) => {
      const pct = Math.round(progress * 100);
      if (pct % 5 === 0) {
        process.stdout.write(`\r  Render: ${pct}%`);
      }
    },
    concurrency: 2,
    imageFormat: "jpeg",
    crf: 18,
    pixelFormat: "yuv420p",
  });

  console.log("\n  Render complete:", outputPath);
  const stats = fs.statSync(outputPath);
  console.log("  File size:", (stats.size / 1024 / 1024).toFixed(2), "MB");
}

render()
  .then(() => {
    console.log("=== Done ===");
    process.exit(0);
  })
  .catch((err) => {
    console.error("=== Error ===");
    console.error(err.message || err);
    if (err.stack) {
      console.error(err.stack.split("\n").slice(0, 5).join("\n"));
    }
    process.exit(1);
  });
