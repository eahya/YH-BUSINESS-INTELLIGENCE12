import { deflateSync } from "node:zlib";
import { mkdir, writeFile } from "node:fs/promises";
import { fileURLToPath } from "node:url";
import path from "node:path";

const scriptDir = path.dirname(fileURLToPath(import.meta.url));
const iconDir = path.resolve(scriptDir, "../src-tauri/icons");
await mkdir(iconDir, { recursive: true });

const crcTable = new Uint32Array(256);
for (let n = 0; n < 256; n++) {
  let c = n;
  for (let k = 0; k < 8; k++) c = c & 1 ? 0xedb88320 ^ (c >>> 1) : c >>> 1;
  crcTable[n] = c >>> 0;
}
function crc32(buffer) {
  let c = 0xffffffff;
  for (const byte of buffer) c = crcTable[(c ^ byte) & 0xff] ^ (c >>> 8);
  return (c ^ 0xffffffff) >>> 0;
}
function pngChunk(type, data) {
  const name = Buffer.from(type, "ascii");
  const body = Buffer.concat([name, data]);
  const result = Buffer.alloc(12 + data.length);
  result.writeUInt32BE(data.length, 0);
  body.copy(result, 4);
  result.writeUInt32BE(crc32(body), 8 + data.length);
  return result;
}
function roundedRect(x, y, left, top, right, bottom, radius) {
  if (x < left || x >= right || y < top || y >= bottom) return false;
  const cx = x < left + radius ? left + radius : x >= right - radius ? right - radius - 1 : x;
  const cy = y < top + radius ? top + radius : y >= bottom - radius ? bottom - radius - 1 : y;
  const dx = x - cx, dy = y - cy;
  return dx * dx + dy * dy <= radius * radius;
}
function render(size) {
  const pixels = Buffer.alloc(size * size * 4, 0);
  const s = size / 512;
  const color = (x, y, hex) => {
    const i = (y * size + x) * 4;
    pixels[i] = parseInt(hex.slice(1, 3), 16);
    pixels[i + 1] = parseInt(hex.slice(3, 5), 16);
    pixels[i + 2] = parseInt(hex.slice(5, 7), 16);
    pixels[i + 3] = 255;
  };
  const outer = [62 * s, 62 * s, 450 * s, 450 * s, 67 * s];
  const inner = [72 * s, 72 * s, 440 * s, 440 * s, 58 * s];
  for (let y = 0; y < size; y++) for (let x = 0; x < size; x++) {
    if (roundedRect(x, y, ...outer)) color(x, y, "#b18f4e");
    if (roundedRect(x, y, ...inner)) color(x, y, "#151615");
  }
  const glyphs = [
    ["10001", "10001", "01010", "00100", "00100", "00100", "00100"],
    ["10001", "10001", "10001", "11111", "10001", "10001", "10001"],
  ];
  const unit = 36 * s, gap = 35 * s, glyphWidth = 5 * unit;
  const x0 = Math.round((size - (glyphWidth * 2 + gap)) / 2);
  const y0 = Math.round(137 * s);
  for (let g = 0; g < glyphs.length; g++) {
    for (let row = 0; row < 7; row++) for (let col = 0; col < 5; col++) {
      if (glyphs[g][row][col] !== "1") continue;
      const left = Math.round(x0 + g * (glyphWidth + gap) + col * unit);
      const top = Math.round(y0 + row * unit);
      const right = Math.round(x0 + g * (glyphWidth + gap) + (col + 1) * unit);
      const bottom = Math.round(y0 + (row + 1) * unit);
      for (let y = top; y < bottom; y++) for (let x = left; x < right; x++) color(x, y, "#e2c879");
    }
  }
  for (let y = Math.round(397 * s); y < Math.round(404 * s); y++)
    for (let x = Math.round(185 * s); x < Math.round(327 * s); x++) color(x, y, "#8e7845");

  const rows = Buffer.alloc(size * (size * 4 + 1));
  for (let y = 0; y < size; y++) pixels.copy(rows, y * (size * 4 + 1) + 1, y * size * 4, (y + 1) * size * 4);
  const header = Buffer.alloc(13);
  header.writeUInt32BE(size, 0); header.writeUInt32BE(size, 4);
  header[8] = 8; header[9] = 6;
  return Buffer.concat([
    Buffer.from([137, 80, 78, 71, 13, 10, 26, 10]),
    pngChunk("IHDR", header), pngChunk("IDAT", deflateSync(rows)), pngChunk("IEND", Buffer.alloc(0)),
  ]);
}

for (const [size, filename] of [[32, "32x32.png"], [128, "128x128.png"],
  [256, "128x128@2x.png"], [512, "icon.png"]]) {
  await writeFile(path.join(iconDir, filename), render(size));
}
const png = render(256);
const ico = Buffer.alloc(22);
ico.writeUInt16LE(0, 0); ico.writeUInt16LE(1, 2); ico.writeUInt16LE(1, 4);
ico[6] = 0; ico[7] = 0; ico[8] = 0; ico[9] = 0;
ico.writeUInt16LE(1, 10); ico.writeUInt16LE(32, 12);
ico.writeUInt32LE(png.length, 14); ico.writeUInt32LE(22, 18);
await writeFile(path.join(iconDir, "icon.ico"), Buffer.concat([ico, png]));
console.log(`Generated YH desktop icons in ${iconDir}`);
