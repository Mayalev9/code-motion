// _homog.js — draws a texture through a 3×3 homography (texture px → screen px) in WebGL2, with
// perspective-correct interpolation: the vertex leaves in homogeneous coordinates (x', y', w') so the GPU divides by itself.
let CV = null, GL = null, PR = null, VAO = null;
const TEX = new WeakMap();
const VS = `#version 300 es
layout(location=0) in vec2 aUv;
uniform mat3 uH; uniform vec2 uTex; uniform vec2 uScr;
out vec2 vUv;
void main(){ vUv = aUv; vec3 p = uH * vec3(aUv * uTex, 1.0);
  gl_Position = vec4(p.x / uScr.x * 2.0 - p.z, p.z - p.y / uScr.y * 2.0, 0.0, p.z); }`;
const FS = `#version 300 es
precision highp float; in vec2 vUv; out vec4 o; uniform sampler2D uT; uniform float uA;
void main(){ vec4 c = texture(uT, vUv); o = c * uA; }`;
function init(W, H) {
  if (!CV) {
    CV = new OffscreenCanvas(W, H);
    GL = CV.getContext('webgl2', { premultipliedAlpha: true, antialias: true, alpha: true });
    const mk = (t, s) => { const x = GL.createShader(t); GL.shaderSource(x, s); GL.compileShader(x); if (!GL.getShaderParameter(x, GL.COMPILE_STATUS)) throw new Error(GL.getShaderInfoLog(x)); return x; };
    PR = GL.createProgram(); GL.attachShader(PR, mk(GL.VERTEX_SHADER, VS)); GL.attachShader(PR, mk(GL.FRAGMENT_SHADER, FS)); GL.linkProgram(PR);
    VAO = GL.createVertexArray(); GL.bindVertexArray(VAO);
    const b = GL.createBuffer(); GL.bindBuffer(GL.ARRAY_BUFFER, b);
    GL.bufferData(GL.ARRAY_BUFFER, new Float32Array([0, 0, 1, 0, 0, 1, 1, 1]), GL.STATIC_DRAW);
    GL.enableVertexAttribArray(0); GL.vertexAttribPointer(0, 2, GL.FLOAT, false, 0, 0);
  }
  if (CV.width !== W || CV.height !== H) { CV.width = W; CV.height = H; }
  return GL;
}
function upload(gl, src) {
  let t = TEX.get(src); if (!t) { t = gl.createTexture(); TEX.set(src, t); }
  gl.bindTexture(gl.TEXTURE_2D, t);
  gl.pixelStorei(gl.UNPACK_PREMULTIPLY_ALPHA_WEBGL, true);
  gl.texImage2D(gl.TEXTURE_2D, 0, gl.RGBA, gl.RGBA, gl.UNSIGNED_BYTE, src);
  gl.generateMipmap(gl.TEXTURE_2D);
  gl.texParameteri(gl.TEXTURE_2D, gl.TEXTURE_MIN_FILTER, gl.LINEAR_MIPMAP_LINEAR);
  gl.texParameteri(gl.TEXTURE_2D, gl.TEXTURE_MAG_FILTER, gl.LINEAR);
  gl.texParameteri(gl.TEXTURE_2D, gl.TEXTURE_WRAP_S, gl.CLAMP_TO_EDGE); gl.texParameteri(gl.TEXTURE_2D, gl.TEXTURE_WRAP_T, gl.CLAMP_TO_EDGE);
}
// items: [{src: canvas, H: [9 row-major], alpha}]  — drawn in order
export function drawHomog(W, H, items) {
  const gl = init(W, H);
  gl.viewport(0, 0, W, H); gl.clearColor(0, 0, 0, 0); gl.clear(gl.COLOR_BUFFER_BIT);
  gl.enable(gl.BLEND); gl.blendFunc(gl.ONE, gl.ONE_MINUS_SRC_ALPHA);
  gl.useProgram(PR); gl.bindVertexArray(VAO);
  for (const it of items) {
    upload(gl, it.src);
    const h = it.H;   // row-major → column-major for GLSL
    gl.uniformMatrix3fv(gl.getUniformLocation(PR, 'uH'), false, new Float32Array([h[0], h[3], h[6], h[1], h[4], h[7], h[2], h[5], h[8]]));
    gl.uniform2f(gl.getUniformLocation(PR, 'uTex'), it.src.width, it.src.height);
    gl.uniform2f(gl.getUniformLocation(PR, 'uScr'), W, H);
    gl.uniform1f(gl.getUniformLocation(PR, 'uA'), it.alpha ?? 1);
    gl.drawArrays(gl.TRIANGLE_STRIP, 0, 4);
  }
  return CV;
}
export function mulH(a, b) {
  const r = new Array(9).fill(0);
  for (let i = 0; i < 3; i++) for (let j = 0; j < 3; j++) for (let k = 0; k < 3; k++) r[i * 3 + j] += a[i * 3 + k] * b[k * 3 + j];
  return r;
}
export function applyH(h, x, y) { const w = h[6] * x + h[7] * y + h[8]; return [(h[0] * x + h[1] * y + h[2]) / w, (h[3] * x + h[4] * y + h[5]) / w]; }
