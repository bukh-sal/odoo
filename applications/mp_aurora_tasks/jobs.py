"""Registered native reminder; no remote effect or detached ORM access."""
from odoo.exceptions import MissingError
from odoo.addons.mp_core import job_dispatch

from .access import PLUGIN,ADDON
from .models import HANDLER

EMPTY=dict(type='object',properties={},additionalProperties=False)
INPUT=dict(type='object',properties={name:dict(type='integer',minimum=1,maximum=2147483647)
                                  for name in ('task','revision')},required=['task','revision'],additionalProperties=False)
OUTPUT=dict(type='object',properties=dict(outcome=dict(enum=['obsolete','notified'])),required=['outcome'],additionalProperties=False)


def resource(env,values,bound):
    task=env['mp.aurora.task'].browse(values['task']).exists()
    if not task:raise MissingError('Task unavailable')
    return task._mp_reminder_resource()


def apply(env,values,prepared,computed,bound):
    return resource(env,values,bound)._deliver_reminder(values['revision'])


job_dispatch.register(job_dispatch.JobDefinition(HANDLER,1,PLUGIN,'','','',INPUT,EMPTY,EMPTY,OUTPUT,
    resource,lambda env,values,bound:{},lambda values,context:{},apply,
    max_attempts=5,timeout_seconds=30,pool='urgent',authority='native',addon=ADDON))
