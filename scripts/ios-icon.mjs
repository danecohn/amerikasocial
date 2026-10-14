import sharp from 'sharp';
import {fileURLToPath} from 'node:url';
const svg='<svg xmlns="http://www.w3.org/2000/svg" width="1024" height="1024"><rect width="1024" height="1024" fill="#C62832"/><text x="512" y="750" font-family="Arial" font-size="760" font-weight="700" text-anchor="middle" fill="white">A</text></svg>';
await sharp(Buffer.from(svg)).png().toFile(fileURLToPath(new URL('../mobile/assets/icon.png',import.meta.url)));
