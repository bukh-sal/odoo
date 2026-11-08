"""Data-only authoring input, independent of the evolving real application."""
from odoo import models,fields


class List(models.Model):
    _name='mp.aurora.task.list'
    name=fields.Char()


class Stage(models.Model):
    _name='mp.aurora.task.stage'
    name=fields.Char()


class Task(models.Model):
    _name='mp.aurora.task'
    name=fields.Char()
