"""Package a reviewed repository reference example; never install or grant trust.

This deliberately uses the existing reference assembler, not an arbitrary plugin
builder. Native addon files are read as data and never imported.
"""
from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path
import sys

sys.path.insert(0,str(Path(__file__).resolve().parent))
from reference_package import assemble


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--source',type=Path,default=Path(__file__).resolve().parents[1],
                        help='Reviewed source checkout containing plugins/ and platform_addons/')
    parser.add_argument('--example',required=True,choices=['notes','notes_labels','canvas','notes_stats','document_stats'])
    parser.add_argument('--output',required=True,type=Path,help='New .mplug file in an existing output directory')
    args=parser.parse_args()
    source=args.source.resolve(); output=args.output.absolute()
    if output.suffix!='.mplug':parser.error('Output must have the .mplug suffix')
    if output.exists() or output.is_symlink():parser.error('Output already exists; choose a fresh path')
    if not output.parent.is_dir():parser.error('Create the output directory explicitly first')
    manifest,raw,_=assemble(source,Path('plugins')/args.example/'plugin.toml')
    # Exclusive creation prevents overwriting an existing reviewed artifact.
    with output.open('xb') as stream:stream.write(raw)
    print(json.dumps(dict(result='assembled_reference_not_installed_or_trusted',
        plugin_id=manifest['plugin']['id'],version=manifest['plugin']['version'],
        digest='sha256:'+hashlib.sha256(raw).hexdigest(),bytes=len(raw),output=str(output),
        next_step='Independently review and validate this exact digest before catalog admission.')))


if __name__=='__main__':main()
