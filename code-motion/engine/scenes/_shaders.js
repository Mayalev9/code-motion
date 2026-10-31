import { NOISE_GLSL } from './_gl.js';

const HEAD = `#version 300 es
precision highp float;
in vec2 vUv;
out vec4 o;
uniform vec2 uRes;
// uv in the 2D canvas convention: (0,0) top-left
vec2 canvasUv() { return vec2(vUv.x, 1.0 - vUv.y); }
`;

// ── aurora ────────────────────────────────────────────────────────────────
// What replaced blurry blobs: domain-warped noise curtains that spread
// down from the apex of the arms, with lobes along both arms.
export const AURORA = `${HEAD}
${NOISE_GLSL}
uniform float uTime;
uniform float uAmp;      // overall strength (0..1 on entry, then breathing)
uniform vec2  uApex;     // apex of the arms in uv units
uniform float uArmAng;   // angle of the arms in radians below the horizon

vec3 ramp(float k) {
  vec3 green = vec3(0.18, 0.88, 0.60);
  vec3 cyan  = vec3(0.04, 0.75, 0.78);
  vec3 blue  = vec3(0.00, 0.47, 0.77);
  vec3 white = vec3(0.90, 1.00, 1.00);
  vec3 c = mix(green, cyan, smoothstep(0.0, 0.45, k));
  c = mix(c, blue, smoothstep(0.45, 0.85, k));
  return mix(c, white, smoothstep(0.86, 1.0, k));
}

void main() {
  vec2 uv = canvasUv();
  float aspect = uRes.y / uRes.x;
  vec2 d = vec2(uv.x - uApex.x, (uv.y - uApex.y) * aspect);
  float r = length(d);
  float a = atan(d.y, d.x);          // +π/2 = straight down

  // curtains: the noise is stretched radially and moves outward over time
  vec2 warp = vec2(a * 1.55, r * 5.2 - uTime * 0.55);
  float w1 = fbm(warp * vec2(1.6, 1.0) + fbm(warp * 0.7) * 1.1);
  float w2 = fbm(warp * vec2(3.4, 2.1) - uTime * 0.22);
  float curtain = mix(w1, w2, 0.35);

  // shape: a lobe downward + a lobe per arm
  float down = pow(max(0.0, sin(a)), 0.62);
  float lobeL = exp(-8.0 * pow(a - (3.14159 - uArmAng), 2.0));
  float lobeR = exp(-8.0 * pow(a - uArmAng, 2.0));
  float shape = clamp(down * 0.78 + (lobeL + lobeR) * 0.62, 0.0, 1.4);

  // radial falloff + a hot core at the apex
  float fall = smoothstep(0.50, 0.015, r);
  float core = exp(-r * r * 230.0);

  // multiply, not add — that keeps dark bands between curtains instead of a flat sheet
  float tex = clamp(curtain * 1.55 - 0.28, 0.0, 1.0);
  float v = tex * shape * fall;
  v = pow(max(v, 0.0), 1.30) * 1.30 * uAmp;
  v += core * 1.15 * uAmp;

  vec3 col = ramp(clamp(curtain * 0.55 + (0.5 - abs(a - 1.5708) * 0.30), 0.0, 1.0));
  col = mix(col, vec3(1.0), clamp(core * 1.6, 0.0, 0.92));

  // a dim blue base that holds the bottom under the curtains
  float base = smoothstep(0.62, 0.05, r) * pow(max(0.0, sin(a)), 0.9);
  vec3 deep = vec3(0.04, 0.20, 0.56);
  vec3 rgbOut = col * v + deep * base * 0.42 * uAmp;

  o = vec4(rgbOut, clamp(v + base * 0.30, 0.0, 1.0));
}`;

// ── bright pass: keeps only what is above the threshold ───────────────────
export const BRIGHT = `${HEAD}
uniform sampler2D uTex;
uniform float uThreshold;
void main() {
  vec4 c = texture(uTex, vUv);
  float l = dot(c.rgb, vec3(0.2126, 0.7152, 0.0722));
  float k = smoothstep(uThreshold, uThreshold + 0.28, l);
  o = vec4(c.rgb * k, 1.0);
}`;

// ── separable gaussian blur ───────────────────────────────────────────────
export const BLUR = `${HEAD}
uniform sampler2D uTex;
uniform vec2 uDir;      // (1,0) horizontal · (0,1) vertical
uniform float uRadius;  // in pixels of the intermediate layer
void main() {
  vec2 px = uDir / uRes;
  vec3 sum = texture(uTex, vUv).rgb * 0.1964;
  float w[5] = float[](0.1749, 0.1216, 0.0540, 0.0162, 0.0033);
  for (int i = 1; i <= 5; i++) {
    vec2 off = px * float(i) * uRadius;
    sum += (texture(uTex, vUv + off).rgb + texture(uTex, vUv - off).rgb) * w[i - 1];
  }
  o = vec4(sum, 1.0);
}`;

// ── chromatic aberration + dither ─────────────────────────────────────────
// Channels are sampled with a radial offset that grows from the centre; dither breaks banding in gradients.
export const CHROMA = `${HEAD}
uniform sampler2D uTex;
uniform float uAmount;
float dither(vec2 p) { return fract(sin(dot(p, vec2(12.9898, 78.233))) * 43758.5453); }
void main() {
  vec2 c = vUv - 0.5;
  float k = dot(c, c) * uAmount;
  vec3 col;
  col.r = texture(uTex, vUv + c * k * 1.00).r;
  col.g = texture(uTex, vUv).g;
  col.b = texture(uTex, vUv - c * k * 1.00).b;
  col += (dither(vUv * uRes) - 0.5) / 255.0 * 1.6;
  o = vec4(col, 1.0);
}`;

// ── turbulent displace ────────────────────────────────────────────────────
// The equivalent of After Effects' Turbulent Displace: every pixel is sampled from a shifted spot,
// and the shift comes from two noise fields. uEvo is the Evolution — when it is stepped in time
// (posterizeTime) you get the jitter of a hand-drawn line.
export const TURBULENT = `${HEAD}
${NOISE_GLSL}
uniform sampler2D uTex;
uniform float uAmount;   // like Amount in AE
uniform float uSize;     // like Size — the noise scale
uniform float uEvo;      // Evolution
void main() {
  float n1 = fbm(vUv * uSize + uEvo);
  float n2 = fbm(vUv * uSize + uEvo + 37.7);
  vec2 d = (vec2(n1, n2) - 0.5) * uAmount / uRes;
  o = texture(uTex, vUv + d);
}`;
