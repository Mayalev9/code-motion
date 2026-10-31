import { NOISE_GLSL } from './_gl.js';

// A volumetric tunnel with a real camera.
// There are no "shapes" here — a ray leaves every pixel, marches forward through space,
// and gathers light at every step. What reads as 3D is the grid on the wall:
// lines along the depth and rings across it, which look smaller the farther away they are.
export const TUNNEL = `#version 300 es
precision highp float;
in vec2 vUv;
out vec4 o;
uniform vec2  uRes;
uniform float uTime;
uniform float uZ;        // camera position on the depth axis
uniform float uRoll;     // camera roll
uniform float uFov;      // focal distance — small = wide lens
uniform float uBass;
uniform float uMid;
uniform float uHigh;
uniform float uShock;    // 0..1 — progress of the page since the last beat
uniform float uShockZ;
uniform float uSway;

${NOISE_GLSL}

const float PI = 3.14159265;

// explicit blend of three colours — a cosine palette fell into muddy brown and is hard to steer
vec3 pal(float t) {
  vec3 blue   = vec3(0.22, 0.52, 1.00);
  vec3 violet = vec3(0.62, 0.32, 1.00);
  vec3 cyan   = vec3(0.20, 0.92, 0.98);
  float k = fract(t);
  vec3 c = mix(blue, violet, smoothstep(0.00, 0.42, k));
  c = mix(c, cyan, smoothstep(0.42, 0.78, k));
  return mix(c, blue, smoothstep(0.78, 1.00, k));
}

void main() {
  vec2 uv = vec2(vUv.x, 1.0 - vUv.y);
  vec2 q = uv - 0.5;
  q.x *= uRes.x / uRes.y;

  float s = sin(uRoll), cr = cos(uRoll);
  q = mat2(cr, -s, s, cr) * q;

  vec3 ro = vec3(uSway, uSway * 0.55, uZ);
  vec3 rd = normalize(vec3(q * 2.0, uFov));

  const int STEPS = 72;
  const float DZ = 0.135;
  vec3 acc = vec3(0.0);
  float z = 0.20;

  for (int i = 0; i < STEPS; i++) {
    vec3 p = ro + rd * z;
    float r = length(p.xy);
    float a = atan(p.y, p.x);

    // the tunnel wall — narrow and sharp, otherwise everything smears into flat rings
    float radius = 1.22 + 0.075 * sin(p.z * 0.5 + uTime * 0.45);
    float wall = exp(-pow(r - radius, 2.0) * 46.0);

    // the grid: 18 lines along the depth + a ring every 2 units
    float la = abs(fract(a / (2.0 * PI) * 18.0 + 0.5) - 0.5);
    float lz = abs(fract(p.z * 1.0) - 0.5);
    float lineA = exp(-la * la * 900.0);
    float lineZ = exp(-lz * lz * 420.0);
    float grid = lineA * 0.75 + lineZ * (1.05 + 2.4 * uBass);

    // fine dust that flickers with the highs
    float dust = smoothstep(0.62, 0.98, fbm(vec2(a * 2.2, p.z * 1.1 - uTime * 0.7)));
    dust *= 0.20 + uHigh * 1.3;

    float dens = wall * (grid + 0.045 + dust);

    // a shock page born on the beat that travels forward along the tunnel
    float swPos = uShockZ + uShock * 8.5;
    float sw = exp(-pow(p.z - swPos, 2.0) * 9.0) * (1.0 - uShock);
    dens += wall * sw * 3.4;

    vec3 col = pal(p.z * 0.05 + uTime * 0.03 + uMid * 0.05);
    col = mix(col, vec3(1.0), clamp(lineZ * uBass * 0.55 + sw * 0.8, 0.0, 0.9));

    // falloff with distance — without it all depths merge into one wall
    acc += col * dens * DZ * exp(-z * 0.20);
    z += DZ;
  }

  // a dark core in the centre: the far opening. Without it a bright blob appears instead of depth.
  float d2 = dot(q, q);
  acc *= smoothstep(0.0, 0.045, d2) * 0.55 + 0.45;
  acc += pal(uTime * 0.06) * exp(-d2 * 90.0) * (0.10 + uBass * 0.55);

  acc = pow(max(acc, 0.0), vec3(0.88)) * 1.55;
  o = vec4(acc, 1.0);
}`;
