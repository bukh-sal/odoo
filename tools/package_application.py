"""Build a reviewed native application archive; never install or grant trust."""
import argparse
import hashlib
import json
from pathlib import Path
import sys

ROOT=Path(__file__).resolve().parents[1]
sys.path[:0]=[str(ROOT/'tools'),str(ROOT/'packages/platform_sdk')]
from application_package import assemble_application


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--source',required=True,type=Path,help='Reviewed source checkout')
    parser.add_argument('--recipe',required=True,help='Portable recipe path relative to the checkout')
    parser.add_argument('--output',required=True,type=Path,help='New .mplug path in an existing directory')
    args=parser.parse_args()
    output=args.output.absolute()
    if output.suffix!='.mplug':parser.error('Output must have the .mplug suffix')
    if output.exists() or output.is_symlink():parser.error('Output already exists; choose a new path')
    if not output.parent.is_dir():parser.error('Create the output directory explicitly first')
    manifest,raw,_=assemble_application(args.source,args.recipe)
    with output.open('xb') as stream:stream.write(raw)
    print(json.dumps(dict(result='assembled_native_application_not_installed_or_trusted',
        plugin_id=manifest['plugin']['id'],version=manifest['plugin']['version'],
        digest='sha256:'+hashlib.sha256(raw).hexdigest(),bytes=len(raw),output=str(output),
        next_step='Review source, dependencies and exact digest independently before curated catalog admission.')))


if __name__=='__main__':main()
