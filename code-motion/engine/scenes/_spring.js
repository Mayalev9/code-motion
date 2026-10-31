// Springs — the five registers published by `motion.dev/ui`, verbatim.
//
// Why a spring and not a bezier: the whole genre of interface motion is built on PHYSICS, not
//    on drawn curves. `easeOut` looks like "an animation"; a spring with a small overshoot looks
//    like "an interface". That is the single biggest difference in a UI shot.
//
// The numbers were published by the source (`motion.theme.ts` on the page), not measured from frames.
// Details and sources: the skill's `references/UI-EXPLAINER.md`.

export const SPRINGS = {
  snap:    { k: 1218, c: 70 },   // instant, almost no overshoot
  ui:      { k:  305, c: 33 },   // ← the default: menus, cards, reveals
  gentle:  { k:  110, c: 20 },
  lively:  { k:  622, c: 17 },   // noticeable overshoot
  ambient: { k:   43, c: 13 },   // background, very slow
};

// stagger between items in a staggered entrance (seconds)
export const STAGGER = { tight: 0.04, base: 0.08, relaxed: 0.15 };
// entrance distance (pixels @1080)
export const TRAVEL  = { hover: 4, enter: 24, section: 48 };

// Analytic solution of a damped spring, mass=1, from 0 to 1, initial velocity 0.
// Returns the value at time t (seconds). Fully deterministic — the engine's ground rule.
export function spring(t, name = 'ui') {
  if (t <= 0) return 0;
  const s = SPRINGS[name] || SPRINGS.ui;
  const k = s.k, c = s.c;
  const zeta = c / (2 * Math.sqrt(k));      // damping ratio
  const wn = Math.sqrt(k);                  // natural frequency
  if (zeta < 1) {                           // under-damped — overshoots
    const wd = wn * Math.sqrt(1 - zeta * zeta);
    return 1 - Math.exp(-zeta * wn * t) *
           (Math.cos(wd * t) + (zeta * wn / wd) * Math.sin(wd * t));
  }
  if (zeta === 1) return 1 - Math.exp(-wn * t) * (1 + wn * t);
  const r = wn * Math.sqrt(zeta * zeta - 1); // over-damped
  const a = -zeta * wn + r, b = -zeta * wn - r;
  return 1 - (b * Math.exp(a * t) - a * Math.exp(b * t)) / (b - a);
}

// how long the spring takes to settle within a threshold — derive durations instead of guessing them
export function settleTime(name = 'ui', eps = 0.001, max = 4) {
  for (let t = 0; t < max; t += 1 / 240) {
    let ok = true;
    for (let u = t; u < t + 0.2 && u < max; u += 1 / 240) {
      if (Math.abs(spring(u, name) - 1) > eps) { ok = false; break; }
    }
    if (ok) return t;
  }
  return max;
}
