"""Build the experimental LAME 3.100 MDCT encoder; pair with build_native_aac.py."""
import argparse
import hashlib
import os
from pathlib import Path
import shutil
import subprocess
import tarfile
import urllib.request

from build_native_aac import ROOT, patch_once


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--sysroot")
    parser.add_argument("--jobs", type=int, default=4)
    args = parser.parse_args()
    base = ROOT / "work/native"
    base.mkdir(parents=True, exist_ok=True)
    archive = base / "lame-3.100.tar.gz"
    if not archive.exists():
        urllib.request.urlretrieve("https://downloads.sourceforge.net/project/lame/lame/3.100/lame-3.100.tar.gz", archive)
    expected = "ddfe36cab873794038ae2c1210557ad34857a4b6bdc515785d1da9e175b1da1e"
    if hashlib.sha256(archive.read_bytes()).hexdigest() != expected:
        raise RuntimeError("LAME source checksum mismatch")
    source = base / "lame-3.100"
    if not source.exists():
        with tarfile.open(archive) as tar:
            tar.extractall(base, filter="data")
    for source_name, destination in (("aac_watermark.h", "agy_aac_watermark.h"), ("mp3_watermark.h", "agy_mp3_watermark.h")):
        shutil.copyfile(ROOT / "native" / source_name, source / "libmp3lame" / destination)
    patch_once(source / "libmp3lame/encoder.c", '#include "encoder.h"', '#include "encoder.h"\n#include "agy_mp3_watermark.h"')
    patch_once(source / "libmp3lame/encoder.c", '    mdct_sub48(gfc, inbuf[0], inbuf[1]);',
               '    mdct_sub48(gfc, inbuf[0], inbuf[1]);\n    for (gr = 0; gr < cfg->mode_gr; gr++)\n        for (ch = 0; ch < cfg->channels_out; ch++)\n            agy_aac_embed(gfc->l3_side.tt[gr][ch].xr, gfc->ov_enc.frame_number * cfg->mode_gr + gr, gfc->l3_side.tt[gr][ch].block_type == SHORT_TYPE);')
    env = dict(os.environ)
    env["CFLAGS"] = "-O2"
    env["LDFLAGS"] = ""
    if args.sysroot:
        env["CFLAGS"] += " -isysroot " + str(Path(args.sysroot).resolve())
        env["LDFLAGS"] += " -isysroot " + str(Path(args.sysroot).resolve())
    subprocess.run(["./configure", "--disable-shared", "--disable-decoder", "--disable-nasm"], cwd=source, env=env, check=True)
    subprocess.run(["make", f"-j{max(1, args.jobs)}"], cwd=source, env=env, check=True)
    print(f"Native MP3 tool: {source / 'frontend/lame'}")


if __name__ == "__main__":
    main()
