import sharp from 'sharp'
import { fileURLToPath } from 'node:url'
import { dirname, join } from 'node:path'

const root = join(dirname(fileURLToPath(import.meta.url)), '..')
const logoPath = join(root, 'public', 'logo.png')
const outPath = join(root, 'public', 'og-image.png')

const WIDTH = 1200
const HEIGHT = 630
const LOGO_MAX_HEIGHT = 420

// Match the HollyWing logo plate (gold mark on black).
const background = Buffer.from(`<svg width="${WIDTH}" height="${HEIGHT}" xmlns="http://www.w3.org/2000/svg">
  <rect width="100%" height="100%" fill="#000000"/>
</svg>`)

const logo = await sharp(logoPath)
  .resize({ height: LOGO_MAX_HEIGHT, fit: 'inside' })
  .png()
  .toBuffer()

const { width = 0, height = 0 } = await sharp(logo).metadata()

await sharp(background)
  .composite([{
    input: logo,
    left: Math.round((WIDTH - width) / 2),
    top: Math.round((HEIGHT - height) / 2),
  }])
  .png()
  .toFile(outPath)

console.log(`Wrote ${outPath} (${WIDTH}x${HEIGHT}) from public/logo.png`)
