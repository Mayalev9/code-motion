// Hinge kinematics for the 3D of `_quad3d.js`.
//
// Why it is needed: `renderQuads` takes `pos` + Euler rotation per quad, with no hierarchy.
// A panel hanging on another panel's hinge (a cube net, a folded map) needs composed
// transforms — and then decomposing the matrix back into angles IN THE SHADER'S CONVENTION.
//
// ⚠️ The shader's convention is not the standard: `mat3(...)` in GLSL is column-major,
// so `rotX(a)` there equals the standard Rx(-a) (same for Y and Z). The composition is
// `rotZ * rotY * rotX * local`. Instead of reasoning about signs — `selftest()` below proves
// a numeric round-trip. Do not trust this module without running it.

// ── mat3 row-major: m[r*3+c], applied to a column vector ──────────────────
export const I3 = [1,0,0, 0,1,0, 0,0,1];
export function mul3(a, b) {
  const o = new Array(9);
  for (let r = 0; r < 3; r++) for (let c = 0; c < 3; c++)
    o[r*3+c] = a[r*3]*b[c] + a[r*3+1]*b[3+c] + a[r*3+2]*b[6+c];
  return o;
}
export function apply3(m, v) {
  return [m[0]*v[0]+m[1]*v[1]+m[2]*v[2], m[3]*v[0]+m[4]*v[1]+m[5]*v[2], m[6]*v[0]+m[7]*v[1]+m[8]*v[2]];
}
// STANDARD right-handed rotations
export const Rx = a => { const c=Math.cos(a), s=Math.sin(a); return [1,0,0, 0,c,-s, 0,s,c]; };
export const Ry = a => { const c=Math.cos(a), s=Math.sin(a); return [c,0,s, 0,1,0, -s,0,c]; };
export const Rz = a => { const c=Math.cos(a), s=Math.sin(a); return [c,-s,0, s,c,0, 0,0,1]; };

// What the shader ACTUALLY computes from angles (rx,ry,rz): rotZ·rotY·rotX where each is
// the transpose of the standard. Defined explicitly here so the selftest can compare against it.
export function shaderMatrix([rx, ry, rz]) {
  const T = m => [m[0],m[3],m[6], m[1],m[4],m[7], m[2],m[5],m[8]];
  return mul3(mul3(T(Rz(rz)), T(Ry(ry))), T(Rx(rx)));
}

/** rotation matrix ⇒ Euler angles that the shader will turn back into the same matrix. */
export function eulerForShader(R) {
  // R = Rz(-c)·Ry(-b)·Rx(-a) ⇒ standard ZYX decomposition, then negate.
  const sb = -R[6];
  const b = Math.asin(Math.max(-1, Math.min(1, sb)));
  let a, c;
  if (Math.abs(sb) < 0.999999) { a = Math.atan2(R[7], R[8]); c = Math.atan2(R[3], R[0]); }
  else { a = Math.atan2(-R[5], R[4]); c = 0; }           // gimbal lock: fold into x
  return [-a, -b, -c];
}

// ── rigid transform {R, p}: world = R·local + p ───────────────────────────
export const compose = (A, B) => ({ R: mul3(A.R, B.R), p: add(apply3(A.R, B.p), A.p) });
export const add = (u, v) => [u[0]+v[0], u[1]+v[1], u[2]+v[2]];
export const sub = (u, v) => [u[0]-v[0], u[1]-v[1], u[2]-v[2]];
export const IDENT = { R: I3, p: [0,0,0] };

/** hinge: rotation R around a pivot point — x' = R(x − pivot) + pivot */
export function hinge(pivot, R) { return { R, p: sub(pivot, apply3(R, pivot)) }; }

/** a panel's normal (local +z) in world space */
export const normalOf = X => apply3(X.R, [0,0,1]);

// ── cross-shaped cube net: C in the centre, arms N S E W, tail T on S ─────
// `a` = fold angle (0 = flat · π/2 = cube · ~π = folded onto the centre)
export function cubeNet(P, a, aT = a, G = IDENT) {
  const h = P / 2;
  const C = IDENT;
  const E = hinge([ h, 0, 0], Ry( a));
  const W = hinge([-h, 0, 0], Ry(-a));
  const N = hinge([ 0, h, 0], Rx(-a));
  const S = hinge([ 0,-h, 0], Rx( a));
  const T = compose(S, hinge([0, -3*h, 0], Rx(aT)));
  const local = { C:[0,0,0], N:[0,P,0], S:[0,-P,0], E:[P,0,0], W:[-P,0,0], T:[0,-2*P,0] };
  const X = { C, N, S, E, W, T };
  const out = {};
  for (const k in X) {
    const Xw = compose(G, X[k]);
    out[k] = { center: add(apply3(Xw.R, local[k]), Xw.p), R: Xw.R, normal: normalOf(Xw) };
  }
  return out;
}

// ── selftest — proves, does not feel ──────────────────────────────────────
export function selftest(log = console.log) {
  let ok = true;
  const near = (u, v, e = 1e-6) => u.every((x, i) => Math.abs(x - v[i]) < e);
  // ① round-trip: an arbitrary matrix ⇒ Euler ⇒ the shader rebuilds it
  let seed = 7; const rnd = () => (seed = (seed * 48271) % 2147483647) / 2147483647;
  let worst = 0;
  for (let i = 0; i < 400; i++) {
    const R = mul3(mul3(Rz(rnd()*6.3-3.1), Ry(rnd()*3-1.5)), Rx(rnd()*6.3-3.1));
    const back = shaderMatrix(eulerForShader(R));
    worst = Math.max(worst, ...R.map((x, j) => Math.abs(x - back[j])));
  }
  ok &= worst < 1e-9;
  log(`  ${worst < 1e-9 ? '✅' : '🔴'} round-trip · 400 random matrices · max error ${worst.toExponential(2)}`);
  // ② at π/2 the net closes into a cube: centres on the six faces, normals outward
  const P = 2, net = cubeNet(P, Math.PI / 2);
  const want = { C:[[0,0,0],[0,0,1]], E:[[1,0,-1],[1,0,0]], W:[[-1,0,-1],[-1,0,0]],
                 N:[[0,1,-1],[0,1,0]], S:[[0,-1,-1],[0,-1,0]], T:[[0,0,-2],[0,0,-1]] };
  for (const k in want) {
    const good = near(net[k].center, want[k][0]) && near(net[k].normal, want[k][1]);
    ok &= good;
    log(`  ${good ? '✅' : '🔴'} ${k}: centre ${net[k].center.map(v => +v.toFixed(3))} · normal ${net[k].normal.map(v => +v.toFixed(3))}`);
  }
  // ③ negative control — at 0 the net is FLAT, not a cube
  const flat = cubeNet(P, 0);
  const isFlat = Object.values(flat).every(f => Math.abs(f.center[2]) < 1e-9 && near(f.normal, [0,0,1]));
  ok &= isFlat;
  log(`  ${isFlat ? '✅' : '🔴'} negative · a=0 ⇒ every panel at z=0 with normal +z`);
  // ④ folded (176°): the arms are BEHIND the centre, not in front of it
  //    Caught by the selftest: the tail with aT=+a came back to the centre plane (z≈0). A folded map
  //    is an ACCORDION — the tail folds the other way (aT=−a) and sits behind S, not on it.
  const A = Math.PI * 176 / 180;
  const fold = cubeNet(P, A, -A);
  const behind = ['E','W','N','S'].every(k => fold[k].center[2] < -1e-3);
  const tailDeeper = fold.T.center[2] < fold.S.center[2] - 1e-3;
  ok &= behind && tailDeeper;
  log(`  ${behind ? '✅' : '🔴'} folded · z of the arms: ${['E','N','S'].map(k => fold[k].center[2].toFixed(3)).join(' · ')} (negative = behind)`);
  log(`  ${tailDeeper ? '✅' : '🔴'} accordion · T (${fold.T.center[2].toFixed(3)}) deeper than S (${fold.S.center[2].toFixed(3)})`);
  // ⑤ control: aT=+a when folded WOULD bring T back to the plane — the bug must stay detectable
  const bad = cubeNet(P, A, A);
  const bugVisible = Math.abs(bad.T.center[2]) < 0.01;
  ok &= bugVisible;
  log(`  ${bugVisible ? '✅' : '🔴'} negative · aT=+a brings T back to z=${bad.T.center[2].toFixed(3)} — the original bug is still measurable`);
  log(`  ${ok ? 'PASS' : 'FAIL'} _hinge selftest`);
  return !!ok;
}
