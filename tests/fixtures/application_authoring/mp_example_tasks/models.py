"""Data-only synthetic authoring input; not product source or application code."""
from odoo import models,fields


class ExampleList(models.Model):
    _name='mp.example.task.list'
    name=fields.Char()


class ExampleStage(models.Model):
    _name='mp.example.task.stage'
    name=fields.Char()


class ExampleTask(models.Model):
    _name='mp.example.task'
    name=fields.Char()
