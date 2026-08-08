/**
 * UI sound design, synthesised in the browser.
 *
 * No audio files ship with the app: every cue is a couple of oscillators
 * through a gain envelope, so there is nothing to license and nothing to
 * download. Off by default, because unexpected noise is rude.
 */

let ctx = null;
let on = false;

export function setSoundEnabled(value) {
  on = Boolean(value);
}

function audio() {
  if (!on) return null;
  if (typeof window === "undefined") return null;
  const Ctor = window.AudioContext || window.webkitAudioContext;
  if (!Ctor) return null;
  if (!ctx) ctx = new Ctor();
  if (ctx.state === "suspended") ctx.resume().catch(() => {});
  return ctx;
}

function blip({ freq = 660, duration = 0.12, type = "sine", gain = 0.05, slide = 0 }) {
  const context = audio();
  if (!context) return;
  const osc = context.createOscillator();
  const amp = context.createGain();
  const now = context.currentTime;

  osc.type = type;
  osc.frequency.setValueAtTime(freq, now);
  if (slide) osc.frequency.exponentialRampToValueAtTime(Math.max(60, freq + slide), now + duration);

  amp.gain.setValueAtTime(0.0001, now);
  amp.gain.exponentialRampToValueAtTime(gain, now + 0.012);
  amp.gain.exponentialRampToValueAtTime(0.0001, now + duration);

  osc.connect(amp).connect(context.destination);
  osc.start(now);
  osc.stop(now + duration + 0.02);
}

export const sfx = {
  tick: () => blip({ freq: 720, duration: 0.09, gain: 0.04 }),
  rate: () => blip({ freq: 520, slide: 260, duration: 0.16, type: "triangle" }),
  complete: () => {
    blip({ freq: 523, duration: 0.14, type: "triangle", gain: 0.05 });
    setTimeout(() => blip({ freq: 659, duration: 0.14, type: "triangle", gain: 0.05 }), 110);
    setTimeout(() => blip({ freq: 784, duration: 0.22, type: "triangle", gain: 0.05 }), 220);
  },
  open: () => blip({ freq: 880, duration: 0.07, gain: 0.03 }),
  nope: () => blip({ freq: 220, duration: 0.14, type: "sawtooth", gain: 0.03 }),
};
