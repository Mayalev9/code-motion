// Renders textured quads in real 3D.
//
// Why it is needed: canvas 2D only knows affine transforms — you can rotate and stretch a rectangle,
// but not foreshorten it in perspective. So a card tilted in space comes out flat, and that is exactly
// what gives a fake away. Here every card is a texture on a quad in space,
// with a perspective camera, depth sorting and depth of field.

let CANVAS = null, GL = null, PROG = null, VAO = null, VBO = null;
const TEX = new WeakMap();

const VERT = `#version 300 es
precision highp float;
layout(location = 0) in vec2 aCorner;     // (0,0)..(1,1)
uniform mat4 uMVP;
uniform vec3 uCenter;
uniform vec2 uSize;
uniform vec3 uRot;                         // rotation around X,Y,Z
out vec2 vUv;

mat3 rotX(float a){ float c=cos(a),s=sin(a); return mat3(1.,0.,0., 0.,c,-s, 0.,s,c); }
mat3 rotY(float a){ float c=cos(a),s=sin(a); return mat3(c,0.,s, 0.,1.,0., -s,0.,c); }
mat3 rotZ(float a){ float c=cos(a),s=sin(a); return mat3(c,-s,0., s,c,0., 0.,0.,1.); }

void main() {
  vUv = vec2(aCorner.x, 1.0 - aCorner.y);
  vec3 local = vec3((aCorner - 0.5) * uSize, 0.0);
  local = rotZ(uRot.z) * rotY(uRot.y) * rotX(uRot.x) * local;
  gl_Position = uMVP * vec4(uCenter + local, 1.0);
}`;

const FRAG = `#version 300 es
precision highp float;
in vec2 vUv;
out vec4 o;
uniform sampler2D uTex;
uniform float uAlpha;
void main() {
  vec4 c = texture(uTex, vUv);
  o = vec4(c.rgb, c.a * uAlpha);
}`;

function init(W, H) {
  if (!CANVAS) {
    CANVAS = new OffscreenCanvas(W, H);
    GL = CANVAS.getContext('webgl2', { premultipliedAlpha: false, antialias: true, alpha: true });
    if (!GL) throw new Error('WebGL2 is not available');
    const mk = (type, src) => {
      const s = GL.createShader(type);
      GL.shaderSource(s, src); GL.compileShader(s);
      if (!GL.getShaderParameter(s, GL.COMPILE_STATUS)) throw new Error(GL.getShaderInfoLog(s));
      return s;
    };
    PROG = GL.createProgram();
    GL.attachShader(PROG, mk(GL.VERTEX_SHADER, VERT));
    GL.attachShader(PROG, mk(GL.FRAGMENT_SHADER, FRAG));
    GL.linkProgram(PROG);
    if (!GL.getProgramParameter(PROG, GL.LINK_STATUS)) throw new Error(GL.getProgramInfoLog(PROG));

    VAO = GL.createVertexArray();
    GL.bindVertexArray(VAO);
    VBO = GL.createBuffer();
    GL.bindBuffer(GL.ARRAY_BUFFER, VBO);
    GL.bufferData(GL.ARRAY_BUFFER, new Float32Array([0, 0, 1, 0, 0, 1, 1, 1]), GL.STATIC_DRAW);
    GL.enableVertexAttribArray(0);
    GL.vertexAttribPointer(0, 2, GL.FLOAT, false, 0, 0);
  }
  if (CANVAS.width !== W || CANVAS.height !== H) { CANVAS.width = W; CANVAS.height = H; }
  return GL;
}

// ── matrices ──────────────────────────────────────────────────────────────
function perspective(fovy, aspect, near, far) {
  const f = 1 / Math.tan(fovy / 2);
  return [f / aspect, 0, 0, 0, 0, f, 0, 0, 0, 0, (far + near) / (near - far), -1,
          0, 0, (2 * far * near) / (near - far), 0];
}
function lookAt(eye, at, up) {
  const sub = (a, b) => [a[0] - b[0], a[1] - b[1], a[2] - b[2]];
  const norm = v => { const l = Math.hypot(...v) || 1; return [v[0] / l, v[1] / l, v[2] / l]; };
  const cross = (a, b) => [a[1] * b[2] - a[2] * b[1], a[2] * b[0] - a[0] * b[2], a[0] * b[1] - a[1] * b[0]];
  const dot = (a, b) => a[0] * b[0] + a[1] * b[1] + a[2] * b[2];
  const z = norm(sub(eye, at));
  const x = norm(cross(up, z));
  const y = cross(z, x);
  return [x[0], y[0], z[0], 0, x[1], y[1], z[1], 0, x[2], y[2], z[2], 0,
          -dot(x, eye), -dot(y, eye), -dot(z, eye), 1];
}
function mul(a, b) {  // a·b, both column-major
  const o = new Array(16).fill(0);
  for (let i = 0; i < 4; i++) for (let j = 0; j < 4; j++)
    for (let k = 0; k < 4; k++) o[j * 4 + i] += a[k * 4 + i] * b[j * 4 + k];
  return o;
}

function upload(gl, canvas) {
  let t = TEX.get(canvas);
  if (!t) { t = gl.createTexture(); TEX.set(canvas, t); }
  gl.bindTexture(gl.TEXTURE_2D, t);
  gl.texParameteri(gl.TEXTURE_2D, gl.TEXTURE_MIN_FILTER, gl.LINEAR);
  gl.texParameteri(gl.TEXTURE_2D, gl.TEXTURE_MAG_FILTER, gl.LINEAR);
  gl.texParameteri(gl.TEXTURE_2D, gl.TEXTURE_WRAP_S, gl.CLAMP_TO_EDGE);
  gl.texParameteri(gl.TEXTURE_2D, gl.TEXTURE_WRAP_T, gl.CLAMP_TO_EDGE);
  gl.pixelStorei(gl.UNPACK_PREMULTIPLY_ALPHA_WEBGL, true);
  gl.texImage2D(gl.TEXTURE_2D, 0, gl.RGBA, gl.RGBA, gl.UNSIGNED_BYTE, canvas);
  return t;
}

/**
 * @param quads [{tex: canvas, pos:[x,y,z], size:[w,h], rot:[rx,ry,rz], alpha}]
 * @param cam   {eye:[x,y,z], at:[x,y,z], fov}
 */
export function renderQuads(W, H, quads, cam) {
  const gl = init(W, H);
  gl.viewport(0, 0, W, H);
  gl.clearColor(0, 0, 0, 0);
  gl.clear(gl.COLOR_BUFFER_BIT);
  gl.enable(gl.BLEND);
  gl.blendFunc(gl.ONE, gl.ONE_MINUS_SRC_ALPHA);   // premultiplied alpha
  gl.disable(gl.DEPTH_TEST);                       // sorted by hand for correct transparency

  const P = perspective(cam.fov, W / H, 1, 12000);
  // standard up. An upside-down up flips the handedness and the image comes out mirrored.
  // The caller is responsible for flipping the Y sign if it thinks in canvas coordinates.
  const V = lookAt(cam.eye, cam.at, [0, 1, 0]);
  const MVP = mul(P, V);

  gl.useProgram(PROG);
  gl.bindVertexArray(VAO);
  gl.uniformMatrix4fv(gl.getUniformLocation(PROG, 'uMVP'), false, new Float32Array(MVP));
  const uCenter = gl.getUniformLocation(PROG, 'uCenter');
  const uSize = gl.getUniformLocation(PROG, 'uSize');
  const uRot = gl.getUniformLocation(PROG, 'uRot');
  const uAlpha = gl.getUniformLocation(PROG, 'uAlpha');
  const uTex = gl.getUniformLocation(PROG, 'uTex');

  // far → near, otherwise transparency accumulates in reverse
  // Sorting by CENTRE distance is not plane sorting. A wide background board
  //   at z=-3 can be closer to the eye than the centre of a small card at z=-1 sitting far off-axis
  //   ⇒ the board was drawn AFTER the card and covered it (most of a grid of cards vanished,
  //   only the central ones survived).
  //   ⇒ optional `q.sortKey`: larger = farther = drawn first. A scene that knows its
  //   layers declares them instead of trusting geometry.
  const dist = q => (q.pos[0] - cam.eye[0]) ** 2 + (q.pos[1] - cam.eye[1]) ** 2 + (q.pos[2] - cam.eye[2]) ** 2;
  const key = q => (q.sortKey !== undefined ? q.sortKey * 1e12 : dist(q));
  const sorted = [...quads].sort((a, b) => key(b) - key(a));

  for (const q of sorted) {
    if ((q.alpha ?? 1) <= 0.004) continue;
    upload(gl, q.tex);
    gl.activeTexture(gl.TEXTURE0);
    gl.uniform1i(uTex, 0);
    gl.uniform3f(uCenter, q.pos[0], q.pos[1], q.pos[2]);
    gl.uniform2f(uSize, q.size[0], q.size[1]);
    gl.uniform3f(uRot, q.rot?.[0] || 0, q.rot?.[1] || 0, q.rot?.[2] || 0);
    gl.uniform1f(uAlpha, q.alpha ?? 1);
    gl.drawArrays(gl.TRIANGLE_STRIP, 0, 4);
  }
  return CANVAS;
}
