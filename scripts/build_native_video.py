"""Build experimental native H.264/H.265 encoders from pinned source commits."""
import argparse
import os
from pathlib import Path
import shutil
import subprocess

from build_native_aac import ROOT, patch_once

PINS = {
    "x264": ("https://code.videolan.org/videolan/x264.git", "0480cb05fa188d37ae87e8f4fd8f1aea3711f7ee"),
    "x265": ("https://bitbucket.org/multicoreware/x265_git.git", "b81f650e21e8aacbe6a9ad04ce14aefc05b932c0"),
}


def checkout(base, name):
    url, commit = PINS[name]
    path = base / name
    if not path.exists():
        subprocess.run(["git", "clone", "--no-checkout", url, str(path)], check=True)
        subprocess.run(["git", "checkout", "--detach", commit], cwd=path, check=True)
    actual = subprocess.check_output(["git", "rev-parse", "HEAD"], cwd=path, text=True).strip()
    if actual != commit:
        raise RuntimeError(f"Expected pinned {name} revision {commit}; refusing to patch a different checkout")
    return path


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument("codec", choices=("h264", "h265"))
    parser.add_argument("--sysroot")
    parser.add_argument("--jobs",type=int,default=4)
    args=parser.parse_args()
    base=ROOT/"work/native"
    base.mkdir(parents=True,exist_ok=True)
    name="x264" if args.codec=="h264" else "x265"
    source=checkout(base,name)
    header=source/("encoder" if name=="x264" else "source/common")/"agy_video_watermark.h"
    shutil.copyfile(ROOT/"native/video_watermark.h",header)
    if name=="x264":
        file=source/"encoder/macroblock.c"
        patch_once(file,'#include "macroblock.h"','#include "macroblock.h"\n#include "agy_video_watermark.h"')
        old='            nz = h->quantf.quant_4x4x4( &dct4x4[i8x8*4], h->quant4_mf[i_quant_cat][i_qp], h->quant4_bias[i_quant_cat][i_qp] );'
        patch_once(file,old,old+'\n            if (p == 0 && agy_video_enabled()) {\n                for (int agy_i=0; agy_i<4; agy_i++)\n                    dct4x4[i8x8*4+agy_i][5] = agy_video_embed(dct4x4[i8x8*4+agy_i][5], (long long)h->fenc->i_frame*h->mb.i_mb_count+h->mb.i_mb_xy);\n                nz = 15;\n            }')
        macroblock_header=source/"encoder/macroblock.h"
        patch_once(macroblock_header,'#include "common/macroblock.h"','#include "common/macroblock.h"\n#include "agy_video_watermark.h"')
        i4_old='    nz = x264_quant_4x4( h, dct4x4, i_qp, ctx_cat_plane[DCT_LUMA_4x4][p], 1, p, idx );'
        patch_once(macroblock_header,i4_old,i4_old+'\n    if (p == 0 && agy_video_enabled()) {\n        dct4x4[5] = agy_video_embed(dct4x4[5], (long long)h->fenc->i_frame*h->mb.i_mb_count+h->mb.i_mb_xy);\n        nz = 1;\n    }')
        command=["./configure","--disable-asm","--disable-opencl","--disable-avs","--disable-lavf","--disable-swscale","--disable-ffms","--bit-depth=8","--chroma-format=420"]
        if args.sysroot:
            command += ["--sysroot="+str(Path(args.sysroot).resolve())]
        subprocess.run(command,cwd=source,check=True)
        subprocess.run(["make",f"-j{max(1,args.jobs)}"],cwd=source,check=True)
        print(source/"x264")
    else:
        file=source/"source/common/quant.cpp"
        patch_once(file,'#include "quant.h"','#include "quant.h"\n#include "agy_video_watermark.h"')
        old='        uint32_t numSig = primitives.quant(m_resiDctCoeff, quantCoeff, deltaU, coeff, qbits, add, numCoeff);'
        patch_once(file,old,old+'\n        if (isLuma && agy_video_enabled()) {\n            int pos=(1 << log2TrSize)+1;\n            int before=coeff[pos];\n            coeff[pos]=agy_video_embed(before, (long long)cu.m_slice->m_poc*cu.m_slice->m_sps->numCUsInFrame+cu.m_cuAddr);\n            if (!before && coeff[pos]) numSig++;\n        }')
        cmake=shutil.which("cmake") or str(ROOT/".venv/bin/cmake")
        build=base/"x265-build"
        command=[cmake,"-S",str(source/"source"),"-B",str(build),"-DENABLE_ASSEMBLY=OFF","-DENABLE_SHARED=OFF","-DENABLE_CLI=ON","-DHIGH_BIT_DEPTH=OFF","-DCMAKE_BUILD_TYPE=Release","-DCMAKE_POLICY_VERSION_MINIMUM=3.5"]
        if args.sysroot:
            command += ["-DCMAKE_OSX_SYSROOT="+str(Path(args.sysroot).resolve())]
        subprocess.run(command,check=True)
        subprocess.run([cmake,"--build",str(build),"--parallel",str(max(1,args.jobs))],check=True)
        print(build/"x265")


if __name__=="__main__":
    main()
