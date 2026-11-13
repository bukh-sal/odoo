#!/usr/local/bin/python3
"""Normalize pinned pip source paths without stripping native debug information.

Build-only front-end; trusted native dependency sources remain trusted. This is
not an execution sandbox. Compiler, build roots and policy are operator-owned.
"""
import os
from pathlib import PurePosixPath
import re
import sys


COMPILER='/usr/bin/gcc'


def compiler_arguments(arguments, cwd):
    path=PurePosixPath(cwd)
    parts=path.parts
    if (str(path)!=cwd or len(parts)<4 or parts[:2]!=('/','tmp')
            or not re.fullmatch(r'pip-install-[A-Za-z0-9_]+',parts[2])
            or '..' in parts):
        raise ValueError('Pinned pip source root required for reproducible native compilation')
    distribution=re.fullmatch(r'([A-Za-z0-9][A-Za-z0-9._-]*)_[0-9a-f]{32}',parts[3])
    if distribution is None:
        raise ValueError('Pinned pip distribution root required for reproducible native compilation')
    root=str(PurePosixPath(*parts[:4]))
    name=distribution[1].lower().replace('_','-')
    target='/usr/src/modular-native/'+name
    return [COMPILER,'-ffile-prefix-map='+root+'='+target,*arguments]


def main():
    arguments=compiler_arguments(sys.argv[1:],os.getcwd())
    os.execv(COMPILER,arguments)


if __name__=='__main__':main()
