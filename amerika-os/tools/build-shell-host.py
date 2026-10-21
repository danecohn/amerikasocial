#!/usr/bin/env python3
"""Compile a dedicated shell executable against Ubuntu's maintained libpython."""
import argparse
import os
from pathlib import Path
import shlex
import shutil
import subprocess
import sysconfig


def build(out):
    root=Path(__file__).resolve().parents[1]
    cc=shlex.split(os.environ.get('AMERIKA_CC') or os.environ.get('CC') or 'cc')
    if not shutil.which(cc[0]):raise SystemExit('Install build-essential, or set AMERIKA_CC to a C compiler.')
    library=Path(sysconfig.get_config_var('LIBDIR'))/sysconfig.get_config_var('INSTSONAME')
    if not library.is_file():raise SystemExit('The distribution libpython shared library is required.')
    out=Path(out);out.parent.mkdir(parents=True,exist_ok=True)
    flags=['-Wall','-Werror']
    if 'tcc' not in Path(cc[0]).name:flags+=['-O2','-fPIE','-pie','-Wl,-z,relro,-z,now']
    subprocess.run([*cc,*flags,str(root/'src/os/native/shell-host.c'),str(library),'-o',str(out)],check=True)
    out.chmod(0o755)
    return out


if __name__=='__main__':
    ap=argparse.ArgumentParser();ap.add_argument('--out',required=True)
    build(ap.parse_args().out)
