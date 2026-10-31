// The colour path for encoding — one source of truth, imported by render.mjs.
//
// Default (untagged bt601) matches how ffmpeg reads untagged reference videos,
// so side-by-side measurements of reference vs. render are comparable.
// `--tag709` writes an explicitly tagged bt709 file — use it for delivery
// when the target player reads untagged HD as bt709 (Chrome, macOS do).

export const COLOR_UNTAGGED_VF =
  'scale=out_color_matrix=bt601:out_range=tv,'
  + 'setparams=colorspace=unknown:range=unspecified';
export const COLOR_UNTAGGED_ARGS = [];

export const COLOR_709_VF = 'scale=out_color_matrix=bt709:out_range=tv';
export const COLOR_709_ARGS = [
  '-colorspace', 'bt709', '-color_range', 'tv',
  '-x264-params', 'colorprim=bt709:transfer=bt709:colormatrix=bt709',
];

export function colorPath(tag709) {
  return tag709
    ? { vf: COLOR_709_VF, args: COLOR_709_ARGS, name: 'bt709-tagged' }
    : { vf: COLOR_UNTAGGED_VF, args: COLOR_UNTAGGED_ARGS, name: 'untagged' };
}
