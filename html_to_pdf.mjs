import puppeteer from "puppeteer-core";
import { resolve } from "path";
import { pathToFileURL } from "url";

const htmlFile = resolve("qxdm_ca_project_slides.html");
const outputArg = process.argv[2];
const pdfFile = resolve(outputArg || "qxdm_ca_project_slides.pdf");

const browser = await puppeteer.launch({
  executablePath:
    "C:\\Program Files (x86)\\Microsoft\\Edge\\Application\\msedge.exe",
  headless: true,
});

const page = await browser.newPage();

// Set viewport to match 16:9 slide dimensions (96 DPI)
await page.setViewport({ width: 1280, height: 720 });

await page.goto(pathToFileURL(htmlFile).href, { waitUntil: "networkidle0" });

// Hide nav overlay
await page.evaluate(() => document.body.classList.add("export-mode"));

await page.pdf({
  path: pdfFile,
  width: "13.333in",
  height: "7.5in",
  printBackground: true,
  margin: { top: 0, right: 0, bottom: 0, left: 0 },
  preferCSSPageSize: false,
});

await browser.close();
console.log(`PDF saved to ${pdfFile}`);
