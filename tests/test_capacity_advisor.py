"""Capacity advice must honor time, scope pins, slots and shared headroom."""
import copy
from datetime import datetime,timedelta,timezone
from pathlib import Path
import sys
import unittest

sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'packages/platform_sdk'))
from modular_platform.capacity_advisor import advise,CapacityError

NOW=datetime(2026,11,7,tzinfo=timezone.utc)


def fixtures():
    policy=dict(protocol=1,maximum_age_seconds=30,startup_seconds=10,drain_seconds=60,
        pools=dict(urgent=dict(minimum=1,maximum=1,start_target_seconds=3),
                   bulk=dict(minimum=1,maximum=6,start_target_seconds=60)),
        handlers={'report:2':dict(pool='bulk',default_seconds=2,arrival_per_second=0)},
        headroom=dict(web_p95_ms=500,db_cpu_fraction=.85,connection_fraction=.7,lock_wait_seconds=2))
    groups=[dict(pool='bulk',handler='report',version=2,workspace=n,current=True,ready=20,running=0,
        future=0,held=0,expired=0,unknown=0,retry=0,original_wait_ms=0,min_validity_ms=180000) for n in range(6)]
    observation=dict(protocol=1,observed_at=NOW.isoformat(),complete=True,dispatch='enabled',fleet_state='ready',
        producer_lanes=1,groups=groups,samples=[],pins={'release':'a'},ready_lanes=dict(urgent=1,bulk=2),
        database=dict(max_connections=100,connections=10,longest_lock_wait_seconds=0),
        health=dict(observed_at=NOW.isoformat(),web_p95_ms=100,db_cpu_fraction=.2,lock_wait_seconds=0))
    return observation,policy


class AdviceTests(unittest.TestCase):
    def run_advice(self,o=None,p=None):
        original,policy=fixtures()
        return advise(o or original,p or policy,now=NOW,expected_pins={'release':'a'})

    def test_estimated_seconds_include_startup_and_explicit_defaults(self):
        result=self.run_advice()
        self.assertEqual(result['state'],'advised')
        bulk=result['pools']['bulk']
        self.assertEqual((bulk['worker_seconds'],bulk['needed_lanes'],bulk['advised_lanes']),(240,5,5))
        self.assertEqual(bulk['predicted_drain_seconds'],54)
        self.assertTrue(result['estimates']['report:2']['fallback'])
        self.assertFalse(result['mutation_authorized'])

    def test_hot_workspace_cannot_use_extra_lanes(self):
        o,p=fixtures();o['groups']=[dict(o['groups'][0],ready=120)]
        result=self.run_advice(o,p)['pools']['bulk']
        self.assertEqual(result['advised_lanes'],1)
        self.assertIn('workspace_serial_limit',result['constraints'])
        self.assertEqual(result['predicted_drain_seconds'],240)

    def test_nonrunnable_and_foreign_release_work_never_becomes_demand(self):
        o,p=fixtures()
        for row in o['groups']:row.update(ready=0,future=100,expired=100,held=100,unknown=100)
        o['groups'].append(dict(o['groups'][0],ready=100000,current=False))
        self.assertEqual(self.run_advice(o,p)['pools']['bulk']['worker_seconds'],0)

    def test_stale_release_headroom_dispatch_and_truncation_hold_no_recommendation(self):
        for field,value,reason in [('observed_at',(NOW-timedelta(seconds=31)).isoformat(),'stale_or_future_observation'),
            ('pins',{'release':'b'},'release_or_resource_pins_changed'),('dispatch','paused','dispatch_not_enabled'),
            ('complete',False,'incomplete_queue_observation'),('health',None,'missing_headroom'),
            ('fleet_state','partial','fleet_not_ready')]:
            with self.subTest(field=field):
                o,p=fixtures();o[field]=value;result=self.run_advice(o,p)
                self.assertEqual(result['state'],'hold');self.assertIn(reason,result['reasons'])
                self.assertIsNone(result['pools']['bulk']['advised_lanes'])

    def test_headroom_pressure_and_missing_measurements_hold(self):
        for key,value in [('db_cpu_fraction',.86),('web_p95_ms',501),('lock_wait_seconds',3)]:
            o,p=fixtures();o['health'][key]=value
            self.assertIn('headroom_'+key,self.run_advice(o,p)['reasons'])
        o,p=fixtures();o['health'].pop('web_p95_ms')
        self.assertIn('missing_web_p95_ms',self.run_advice(o,p)['reasons'])
        o,p=fixtures();o['database']['longest_lock_wait_seconds']=3
        self.assertIn('headroom_database_lock_wait',self.run_advice(o,p)['reasons'])

    def test_connection_budget_is_shared_between_pools(self):
        o,p=fixtures();o['database']['connections']=67
        p['pools']['urgent']['maximum']=2;p['pools']['bulk']['maximum']=5
        p['handlers']['urgent:1']=dict(pool='urgent',default_seconds=2,arrival_per_second=0)
        o['groups'] += [dict(o['groups'][0],pool='urgent',handler='urgent',version=1,workspace=n,ready=50) for n in range(3)]
        result=self.run_advice(o,p)
        self.assertEqual(result['pools']['urgent']['advised_lanes'],2)
        self.assertEqual(result['pools']['bulk']['advised_lanes'],2)

    def test_original_wait_and_short_expiry_warn_about_late_reactive_growth(self):
        o,p=fixtures();o['groups'][0].update(original_wait_ms=59000,min_validity_ms=5000)
        constraints=self.run_advice(o,p)['pools']['bulk']['constraints']
        self.assertIn('reactive_start_too_late',constraints)
        self.assertIn('reactive_start_after_expiry',constraints)

    def test_recent_observed_p95_cannot_reduce_default(self):
        o,p=fixtures()
        o['samples']=[dict(handler_version='report:2',at=NOW.isoformat(),worker_seconds=3) for _ in range(20)]
        estimate=self.run_advice(o,p)['estimates']['report:2']
        self.assertEqual(estimate['seconds'],3);self.assertFalse(estimate['fallback'])
        for sample in o['samples']:sample['at']=(NOW-timedelta(seconds=901)).isoformat()
        self.assertEqual(self.run_advice(o,p)['estimates']['report:2']['seconds'],2)

    def test_explicit_arrival_forecast_increases_work_but_unallocated_forecast_holds(self):
        o,p=fixtures();p['handlers']['report:2']['arrival_per_second']=1
        self.assertEqual(self.run_advice(o,p)['pools']['bulk']['worker_seconds'],360)
        o['groups']=[]
        self.assertIn('unallocated_arrival_forecast:bulk',self.run_advice(o,p)['reasons'])

    def test_missing_handler_estimate_or_changed_pool_refuses(self):
        o,p=fixtures();p['handlers']={}
        self.assertIn('missing_handler_estimate:bulk',self.run_advice(o,p)['reasons'])
        o,p=fixtures();p['handlers']['report:2']['pool']='urgent'
        with self.assertRaises(CapacityError):self.run_advice(o,p)

    def test_invalid_numbers_and_site_maxima_refuse(self):
        for bad in (True,float('nan'),float('inf'),-1):
            o,p=fixtures();p['startup_seconds']=bad
            with self.assertRaises(CapacityError):self.run_advice(o,p)
        o,p=fixtures();p['pools']['bulk']['maximum']=7
        with self.assertRaises(CapacityError):self.run_advice(o,p)

    def test_inputs_remain_unchanged(self):
        o,p=fixtures();original=copy.deepcopy((o,p));self.run_advice(o,p)
        self.assertEqual((o,p),original)

    def test_warm_capacity_does_not_pay_startup_again(self):
        o,p=fixtures()
        for row in o['groups']:row['ready']=10
        p['startup_seconds']=100
        result=self.run_advice(o,p)['pools']['bulk']
        self.assertEqual(result['worker_seconds'],120)
        self.assertEqual(result['advised_lanes'],2)
        self.assertEqual(result['predicted_drain_seconds'],60)
        self.assertNotIn('startup_exceeds_drain_window',result['constraints'])

    def test_empty_queue_has_zero_predicted_work_time(self):
        o,p=fixtures()
        for row in o['groups']:row['ready']=0
        self.assertEqual(self.run_advice(o,p)['pools']['bulk']['predicted_drain_seconds'],0)

    def test_fast_burst_requires_warm_capacity_even_when_drain_window_fits(self):
        o,p=fixtures()
        p['handlers']['urgent:1']=dict(pool='urgent',default_seconds=.1,arrival_per_second=0)
        o['groups']=[dict(o['groups'][0],pool='urgent',handler='urgent',version=1,ready=150)]
        result=self.run_advice(o,p)['pools']['urgent']
        self.assertEqual(result['advised_lanes'],1)
        self.assertEqual(result['needed_warm_lanes_for_start_target'],5)
        self.assertIn('start_target_at_risk',result['constraints'])
        self.assertIn('reactive_start_too_late',result['constraints'])

    def test_exhausted_connections_cannot_recommend_scale_to_zero(self):
        o,p=fixtures();o['database']['connections']=70;o['ready_lanes']['bulk']=0
        result=self.run_advice(o,p)
        self.assertEqual(result['state'],'hold')
        self.assertIn('insufficient_warm_capacity:bulk',result['reasons'])
        self.assertIsNone(result['pools']['bulk']['advised_lanes'])
        self.assertIsNone(result['pools']['bulk']['predicted_drain_seconds'])


if __name__=='__main__':unittest.main()
