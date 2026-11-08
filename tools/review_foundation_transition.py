"""Produce a private data-only review for an explicitly selected owned recipe.

This command is read-only against the deployment. Stage, review, approval,
checkpoint and apply are separate operator actions.
"""
import argparse
import json
from pathlib import Path
import sys

ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT/'packages/platform_sdk'))
from modular_platform.contracts import load_json
from modular_platform.deployment import DockerObserver,inspect_image
from modular_platform.foundation_transition import declare_transition
from modular_platform.operator_os import verify_private_directory
from modular_platform.operator_store import _write_new,OperatorStore
from modular_platform.plans import data_digest


def main():
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument('--deployment-config',required=True,type=Path)
    p.add_argument('--image-id',required=True)
    p.add_argument('--output',required=True,type=Path)
    p.add_argument('--recipe',choices=['owned-addon-extraction-46-47-v1','owned-native-tasks-adoption-47-49-v1'],default='owned-addon-extraction-46-47-v1')
    a=p.parse_args()
    OperatorStore._regular(a.deployment_config)
    verify_private_directory(a.output.resolve().parent)
    configuration=load_json(a.deployment_config.read_bytes())
    DockerObserver(configuration).read()
    declaration=declare_transition(configuration,a.image_id,inspect_image(configuration['image_id']),inspect_image(a.image_id),recipe=a.recipe)
    _write_new(a.output,declaration)
    print(json.dumps(dict(result='review_required_not_approved',declaration_digest=data_digest(declaration),
        source=configuration['image_id'],target=a.image_id,changed_files=len(declaration['source_changes']),
        sites=len(declaration['site_effects']))))


if __name__=='__main__':main()
