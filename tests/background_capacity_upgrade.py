"""Approved core-only capacity estimator correction on the populated BX-04 site."""
import argparse
from pathlib import Path

from background_retention_lifecycle import approved
from background_site import load,write
from background_workers import Probe


def snapshot(probe):
    return {table:probe.sql('SELECT md5(string_agg(md5(to_jsonb(r)::text),\'\' ORDER BY id)) FROM '+table+' r')
        for table in ('mp_background_task','mp_background_notification','mp_example_note')}


def main(candidate,version=42):
    probe=Probe('bx-04-capacity-01');assert not probe.operator._lanes()
    path=probe.site.local/f'bx04-core{version}-upgrade.json';assert not path.exists()
    before=snapshot(probe)
    image=load(candidate)['image_id']
    operation,native=approved(probe,image,'core_upgrade')
    record=dict(phase='applying',operation=operation,previous_image=probe.target['image_id'],image=image,business_before=before)
    write(path,record)
    result=native.apply(operation)
    assert result['state']=='completed' and result['traffic_resumed']
    after=Probe('bx-04-capacity-01')
    assert after.target['image_id']==image and snapshot(after)==before
    assert after.sql("SELECT latest_version FROM ir_module_module WHERE name='mp_example_background'")=='19.0.0.2.1'
    assert after.sql("SELECT latest_version FROM ir_module_module WHERE name='mp_core'")==f'19.0.0.1.{version}'
    record.update(phase='passed',result=result,business_after=snapshot(after),reference_unchanged=True)
    write(path,record)
    print(dict(phase='passed',operation=operation,business_preserved=True),flush=True)


if __name__=='__main__':
    parser=argparse.ArgumentParser(description=__doc__);parser.add_argument('candidate',type=Path)
    parser.add_argument('--version',type=int,choices=[42,43],default=42)
    args=parser.parse_args();main(args.candidate,args.version)
