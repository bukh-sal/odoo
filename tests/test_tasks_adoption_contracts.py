"""Closed Tasks transition declarations do not authorize arbitrary core adoption."""
import copy
import json
from pathlib import Path
import sys
import unittest

ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT/'packages/platform_sdk'))
from modular_platform.contracts import validate,ContractError


class TasksAdoptionContract(unittest.TestCase):
    def setUp(self):
        self.example=json.loads((ROOT/'packages/contracts/examples/v1/foundation-transition/tasks-adoption.json').read_bytes())

    def test_explicit_closed_recipe_and_retained_old_golden(self):
        validate('foundation-transition',self.example)
        validate('foundation-transition',json.loads((ROOT/'packages/contracts/examples/v1/foundation-transition.json').read_bytes()))

    def test_other_source_target_or_app_cannot_select_this_recipe(self):
        for path,value in [
            (('recipe',),'generic-adoption'),(('source','image_id'),'sha256:'+'0'*64),
            (('source','inventory_digest'),'sha256:'+'0'*64),
            (('source','core_version'),'0.1.46'),(('target','core_version'),'0.1.50'),
            (('target','application_version'),'0.2.3'),(('target','application_digest'),'sha256:'+'0'*64)]:
            with self.subTest(path=path):
                value_copy=copy.deepcopy(self.example);part=value_copy
                for key in path[:-1]:part=part[key]
                part[path[-1]]=value
                with self.assertRaises(ContractError):validate('foundation-transition',value_copy)

    def test_no_commands_sql_workspaces_or_permission_snapshots(self):
        for part,key,value in [('root','command','run me'),('site','sql','DELETE FROM res_users'),
                               ('site','workspace_id',None),('target','grant',True)]:
            with self.subTest(key=key):
                obj=copy.deepcopy(self.example)
                section=obj if part=='root' else obj['site_effects'][0] if part=='site' else obj['target']
                section[key]=value
                with self.assertRaises(ContractError):validate('foundation-transition',obj)

    def test_unknown_table_native_state_and_boolean_shapes_are_denied(self):
        for case in ['table','state','bool','gap']:
            with self.subTest(case=case):
                obj=copy.deepcopy(self.example);effect=obj['site_effects'][0]
                if case=='table':effect['retained_tables'][0]['table']='unreviewed_table'
                if case=='state':effect['native_modules'][0]['state']='to install'
                if case=='bool':effect['tasks_installed']=1
                if case=='gap':effect['stage_additions']=[dict(list_id=True,done=False)]
                with self.assertRaises(ContractError):validate('foundation-transition',obj)


if __name__=='__main__':unittest.main()
