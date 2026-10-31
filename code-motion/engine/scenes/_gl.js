// WebGL2 layer for the engine — for things canvas 2D cannot do:
// volumetric noise, domain warping, thresholded bloom and chromatic aberration.
// The context is created once and shared by every call (creating a context per frame leaks).

let CANVAS = null, GL = null;
const PROGS = new Map();
let QUAD = null;

const VERT = `#version 300 es
precision highp float;
out vec2 vUv;
void main() {
  // a single triangle that covers the whole screen — cheaper than two triangles
  vec2 p = vec2((gl_VertexID << 1) & 2, gl_VertexID & 2);
  vUv = p;
  gl_Position = vec4(p * 2.0 - 1.0, 0.0, 1.0);
}`;

function ctx(W, H) {
  if (!CANVAS) {
    CANVAS = new OffscreenCanvas(W, H);
    GL = CANVAS.getContext('webgl2', { premultipliedAlpha: false, antialias: false, alpha: true });
    if (!GL) throw new Error('WebGL2 is not available in this environment');
    QUAD = GL.createVertexArray();
  }
  if (CANVAS.width !== W || CANVAS.height !== H) { CANVAS.width = W; CANVAS.height = H; }
  return GL;
}

function program(gl, frag) {
  let p = PROGS.get(frag);
  if (p) return p;
  const mk = (type, src) => {
    const s = gl.createShader(type);
    gl.shaderSource(s, src); gl.compileShader(s);
    if (!gl.getShaderParameter(s, gl.COMPILE_STATUS)) {
      throw new Error('Shader compile error:\n' + gl.getShaderInfoLog(s));
    }
    return s;
  };
  p = gl.createProgram();
  gl.attachShader(p, mk(gl.VERTEX_SHADER, VERT));
  gl.attachShader(p, mk(gl.FRAGMENT_SHADER, frag));
  gl.linkProgram(p);
  if (!gl.getProgramParameter(p, gl.LINK_STATUS)) {
    throw new Error('Shader link error: ' + gl.getProgramInfoLog(p));
  }
  PROGS.set(frag, p);
  return p;
}

const TEXES = new Map();
function texture(gl, key, source) {
  let t = TEXES.get(key);
  if (!t) { t = gl.createTexture(); TEXES.set(key, t); }
  gl.bindTexture(gl.TEXTURE_2D, t);
  gl.texParameteri(gl.TEXTURE_2D, gl.TEXTURE_MIN_FILTER, gl.LINEAR);
  gl.texParameteri(gl.TEXTURE_2D, gl.TEXTURE_MAG_FILTER, gl.LINEAR);
  gl.texParameteri(gl.TEXTURE_2D, gl.TEXTURE_WRAP_S, gl.CLAMP_TO_EDGE);
  gl.texParameteri(gl.TEXTURE_2D, gl.TEXTURE_WRAP_T, gl.CLAMP_TO_EDGE);
  if (source && source.data instanceof Float32Array) {
    // data texture: {data, w, h} ⇒ RGBA32F, read with texelFetch — lists longer than any uniform limit
    gl.texParameteri(gl.TEXTURE_2D, gl.TEXTURE_MIN_FILTER, gl.NEAREST);
    gl.texParameteri(gl.TEXTURE_2D, gl.TEXTURE_MAG_FILTER, gl.NEAREST);
    gl.pixelStorei(gl.UNPACK_FLIP_Y_WEBGL, false);
    gl.texImage2D(gl.TEXTURE_2D, 0, gl.RGBA32F, source.w, source.h, 0, gl.RGBA, gl.FLOAT, source.data);
    return t;
  }
  gl.pixelStorei(gl.UNPACK_FLIP_Y_WEBGL, true);
  gl.texImage2D(gl.TEXTURE_2D, 0, gl.RGBA, gl.RGBA, gl.UNSIGNED_BYTE, source);
  return t;
}

/**
 * Renders a shader and returns a canvas you can paste straight into the 2D context.
 * uniforms: number → float · [x,y] → vec2 · [r,g,b] → vec3 · canvas → sampler2D
 *           Float32Array → float[] · {v2|v3|v4: Float32Array} → vec2[]/vec3[]/vec4[]
 *           {data: Float32Array, w, h} → sampler2D of RGBA32F (data texture)
 */
export function glDraw(W, H, frag, uniforms = {}) {
  const gl = ctx(W, H);
  const p = program(gl, frag);
  gl.useProgram(p);
  gl.bindVertexArray(QUAD);
  gl.viewport(0, 0, W, H);
  gl.disable(gl.DEPTH_TEST);
  gl.clearColor(0, 0, 0, 0);
  gl.clear(gl.COLOR_BUFFER_BIT);

  let unit = 0;
  const set = (n, v) => {
    const loc = gl.getUniformLocation(p, n);
    if (loc === null) return;
    if (typeof v === 'number') gl.uniform1f(loc, v);
    else if (Array.isArray(v) && v.length === 2) gl.uniform2f(loc, v[0], v[1]);
    else if (Array.isArray(v) && v.length === 3) gl.uniform3f(loc, v[0], v[1], v[2]);
    else if (Array.isArray(v) && v.length === 4) gl.uniform4f(loc, v[0], v[1], v[2], v[3]);
    // uniform arrays: Float32Array → float[] · {v2|v3|v4: Float32Array} → vecN[]
    else if (v instanceof Float32Array) gl.uniform1fv(loc, v);
    else if (v && v.v4 instanceof Float32Array) gl.uniform4fv(loc, v.v4);
    else if (v && v.v3 instanceof Float32Array) gl.uniform3fv(loc, v.v3);
    else if (v && v.v2 instanceof Float32Array) gl.uniform2fv(loc, v.v2);
    else { texture(gl, n, v); gl.activeTexture(gl.TEXTURE0 + unit); gl.bindTexture(gl.TEXTURE_2D, TEXES.get(n)); gl.uniform1i(loc, unit); unit++; }
  };
  set('uRes', [W, H]);
  for (const [k, v] of Object.entries(uniforms)) set(k, v);

  gl.drawArrays(gl.TRIANGLES, 0, 3);
  return CANVAS;
}

// helper: pastes shader output into the 2D context
export function glPaste(ctx2d, canvas, alpha = 1, op = 'lighter') {
  ctx2d.save();
  ctx2d.globalCompositeOperation = op;
  ctx2d.globalAlpha = alpha;
  ctx2d.filter = 'none';
  ctx2d.drawImage(canvas, 0, 0);
  ctx2d.restore();
}

// ── noise functions shared by the shaders ─────────────────────────────────
export const NOISE_GLSL = `
float hash(vec2 p){ return fract(sin(dot(p, vec2(127.1, 311.7))) * 43758.5453); }
float vnoise(vec2 p){
  vec2 i = floor(p), f = fract(p);
  vec2 u = f * f * (3.0 - 2.0 * f);
  return mix(mix(hash(i), hash(i + vec2(1,0)), u.x),
             mix(hash(i + vec2(0,1)), hash(i + vec2(1,1)), u.x), u.y);
}
float fbm(vec2 p){
  float v = 0.0, a = 0.5;
  for (int i = 0; i < 6; i++) { v += a * vnoise(p); p *= 2.03; a *= 0.5; }
  return v;
}
`;
