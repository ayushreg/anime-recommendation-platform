/**
 * Poster tinting.
 *
 * Ideal path: pull the dominant colour straight off the cover art. Poster CDNs
 * do not all send CORS headers though, and reading pixels from a tainted canvas
 * throws, so there is a deterministic fallback that derives a hue from the
 * title. Same title, same colour, every time, with or without the canvas.
 */

const cache = new Map();

function hashHue(seed) {
  const text = String(seed || "kura");
  let hash = 0;
  for (let i = 0; i < text.length; i += 1) {
    hash = (hash << 5) - hash + text.charCodeAt(i);
    hash |= 0;
  }
  return Math.abs(hash) % 360;
}

export function fallbackTint(anime) {
  const hue = hashHue(anime?.title || anime?.id);
  return { hue, sat: 72, light: 56, source: "title" };
}

export function extractTint(anime, imageUrl) {
  const key = anime?.id ?? imageUrl;
  if (cache.has(key)) return Promise.resolve(cache.get(key));

  const fallback = fallbackTint(anime);
  if (!imageUrl || typeof document === "undefined") {
    cache.set(key, fallback);
    return Promise.resolve(fallback);
  }

  return new Promise((resolve) => {
    const img = new Image();
    img.crossOrigin = "anonymous";
    const done = (value) => {
      cache.set(key, value);
      resolve(value);
    };
    img.onerror = () => done(fallback);
    img.onload = () => {
      try {
        const size = 12;
        const canvas = document.createElement("canvas");
        canvas.width = size;
        canvas.height = size;
        const ctx = canvas.getContext("2d", { willReadFrequently: true });
        ctx.drawImage(img, 0, 0, size, size);
        const { data } = ctx.getImageData(0, 0, size, size);

        let r = 0;
        let g = 0;
        let b = 0;
        let count = 0;
        for (let i = 0; i < data.length; i += 4) {
          const alpha = data[i + 3];
          if (alpha < 200) continue;
          const max = Math.max(data[i], data[i + 1], data[i + 2]);
          const min = Math.min(data[i], data[i + 1], data[i + 2]);
          // Skip near-greys so a black letterbox does not decide the theme.
          if (max - min < 24) continue;
          r += data[i];
          g += data[i + 1];
          b += data[i + 2];
          count += 1;
        }
        if (!count) return done(fallback);

        r = r / count / 255;
        g = g / count / 255;
        b = b / count / 255;
        const max = Math.max(r, g, b);
        const min = Math.min(r, g, b);
        const light = (max + min) / 2;
        const delta = max - min;
        let hue = 0;
        if (delta > 0) {
          if (max === r) hue = ((g - b) / delta) % 6;
          else if (max === g) hue = (b - r) / delta + 2;
          else hue = (r - g) / delta + 4;
          hue = Math.round(hue * 60);
          if (hue < 0) hue += 360;
        }
        const sat = delta === 0 ? 0 : delta / (1 - Math.abs(2 * light - 1));
        return done({
          hue,
          sat: Math.round(Math.min(0.85, Math.max(0.35, sat)) * 100),
          light: 56,
          source: "poster",
        });
      } catch {
        return done(fallback);
      }
    };
    img.src = imageUrl;
  });
}

export function applyTint(node, tint) {
  if (!node || !tint) return;
  node.style.setProperty("--tint-h", String(tint.hue));
  node.style.setProperty("--tint-s", `${tint.sat}%`);
  node.style.setProperty("--tint-l", `${tint.light}%`);
}

export function clearTint(node) {
  if (!node) return;
  node.style.removeProperty("--tint-h");
  node.style.removeProperty("--tint-s");
  node.style.removeProperty("--tint-l");
}
