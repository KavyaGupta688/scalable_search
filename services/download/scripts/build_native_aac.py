"""Build isolated experimental native AAC hooks against a pinned FFmpeg release.

Source download is explicit; no system libraries or binaries are replaced.
"""
import argparse
import hashlib
import os
from pathlib import Path
import shutil
import subprocess
import tarfile
import urllib.request

ROOT = Path(__file__).resolve().parent.parent
VERSION = "7.1"


def patch_once(path, old, new):
    text = path.read_text()
    if new in text:
        return
    if text.count(old) != 1:
        raise RuntimeError(f"Unexpected upstream layout: {path}")
    path.write_text(text.replace(old, new))


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--jobs", type=int, default=4)
    parser.add_argument("--sysroot", help="Optional SDK directory when the default SDK and linker do not match")
    args = parser.parse_args()
    base = ROOT / "work" / "native"
    base.mkdir(parents=True, exist_ok=True)
    archive = base / f"ffmpeg-{VERSION}.tar.xz"
    if not archive.exists():
        urllib.request.urlretrieve(f"https://ffmpeg.org/releases/ffmpeg-{VERSION}.tar.xz", archive)
    expected = "40973d44970dbc83ef302b0609f2e74982be2d85916dd2ee7472d30678a7abe6"
    if hashlib.sha256(archive.read_bytes()).hexdigest() != expected:
        raise RuntimeError("FFmpeg source archive checksum mismatch")
    source = base / f"ffmpeg-{VERSION}"
    if not source.exists():
        with tarfile.open(archive) as tar:
            tar.extractall(base, filter="data")
    shutil.copyfile(ROOT / "native" / "aac_watermark.h", source / "libavcodec" / "agy_aac_watermark.h")
    shutil.copyfile(ROOT / "native" / "mp3_watermark.h", source / "libavcodec" / "agy_mp3_watermark.h")
    shutil.copyfile(ROOT / "native" / "video_watermark.h", source / "libavcodec" / "agy_video_watermark.h")
    patch_once(source / "libavcodec" / "aacenc.c", '#include "aacenc.h"', '#include "aacenc.h"\n#include "agy_aac_watermark.h"')
    patch_once(source / "libavcodec" / "aacenc.c",
               '            apply_window_and_mdct(s, sce, overlap);',
               '            apply_window_and_mdct(s, sce, overlap);\n            agy_aac_embed(sce->coeffs, avctx->frame_num - 1, sce->ics.window_sequence[0] == EIGHT_SHORT_SEQUENCE);\n            memcpy(sce->pcoeffs, sce->coeffs, sizeof(sce->pcoeffs));')
    patch_once(source / "libavcodec" / "aac" / "aacdec.c", '#include "aacdec.h"', '#include "aacdec.h"\n#include "libavcodec/agy_aac_watermark.h"')
    patch_once(source / "libavcodec" / "aac" / "aacdec.c",
               '                    imdct_and_window(ac, &che->ch[0]);',
               '                    if (!ac->is_fixed && type <= TYPE_CPE)\n                        agy_aac_extract(che->ch[0].coeffs, ac->avctx->frame_num, che->ch[0].ics.window_sequence[0] == EIGHT_SHORT_SEQUENCE);\n                    imdct_and_window(ac, &che->ch[0]);')
    patch_once(source / "libavcodec" / "mpegaudiodec_template.c", '#include "mpegaudio.h"',
               '#include "mpegaudio.h"\n#if USE_FLOATS\n#include "agy_mp3_watermark.h"\n#endif')
    patch_once(source / "libavcodec" / "mpegaudiodec_template.c", '            compute_antialias(s, g);',
               '            #if USE_FLOATS\n            if (ch == 0) agy_aac_extract(g->sb_hybrid, s->avctx->frame_num * nb_granules + gr, g->block_type == 2);\n            #endif\n            compute_antialias(s, g);')
    patch_once(source / "libavcodec/h264_cabac.c", '#include "h264dec.h"', '#include "h264dec.h"\n#include "agy_video_watermark.h"')
    patch_once(source / "libavcodec/h264_cabac.c",
               '            node_ctx = coeff_abs_level_transition[0][node_ctx]; \\\n',
               '            node_ctx = coeff_abs_level_transition[0][node_ctx]; \\\n            if (!is_dc && (cat == 1 || cat == 2) && j == 5) agy_video_extract((long long)h->avctx->frame_num*h->mb_width*h->mb_height+sl->mb_y*h->mb_width+sl->mb_x, 1); \\\n')
    patch_once(source / "libavcodec/h264_cabac.c",
               '            if( is_dc ) { \\\n                ((type*)block)[j] = get_cabac_bypass_sign( CC, -coeff_abs );',
               '            if (!is_dc && (cat == 1 || cat == 2) && j == 5) agy_video_extract((long long)h->avctx->frame_num*h->mb_width*h->mb_height+sl->mb_y*h->mb_width+sl->mb_x, coeff_abs); \\\n            if( is_dc ) { \\\n                ((type*)block)[j] = get_cabac_bypass_sign( CC, -coeff_abs );')
    patch_once(source / "libavcodec/hevc/cabac.c", '#include "hevcdec.h"', '#include "hevcdec.h"\n#include "libavcodec/agy_video_watermark.h"')
    patch_once(source / "libavcodec/hevc/cabac.c", '                coeff_sign_flag <<= 1;',
               '                coeff_sign_flag <<= 1;\n                if (c_idx == 0 && x_c == 1 && y_c == 1)\n                    agy_video_extract((long long)s->avctx->frame_num*sps->ctb_width*sps->ctb_height+(y0>>sps->log2_ctb_size)*sps->ctb_width+(x0>>sps->log2_ctb_size), abs(trans_coeff_level));')
    configure = ["./configure", "--disable-everything", "--disable-autodetect", "--disable-doc", "--disable-debug", "--disable-asm",
                 "--enable-ffmpeg", "--enable-ffprobe", "--enable-protocol=file,pipe", "--enable-encoder=aac,pcm_s16le,pcm_f32le",
                 "--enable-decoder=aac,mp3float,h264,hevc,rawvideo,pcm_s16le,pcm_s24le,pcm_f32le", "--enable-demuxer=wav,aac,mov,mp3,h264,hevc,matroska,rawvideo", "--enable-parser=aac,mpegaudio,h264,hevc",
                 "--enable-muxer=adts,ipod,wav,null,mp4,matroska,rawvideo", "--enable-encoder=rawvideo", "--enable-filter=aresample,anull,aformat,format,scale", "--enable-swresample"]
    if args.sysroot:
        configure.append("--sysroot=" + str(Path(args.sysroot).resolve()))
    subprocess.run(configure, cwd=source, check=True)
    subprocess.run(["make", f"-j{max(1, args.jobs)}"], cwd=source, check=True)
    print(f"Native experimental AAC tool: {source / 'ffmpeg'}")


if __name__ == "__main__":
    main()
