# Owned foundation regression. See LICENSE and COPYRIGHT.
from odoo.exceptions import AccessError
from odoo.tests import TransactionCase, new_test_user


class TestFoundationFlow(TransactionCase):
    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.actor = new_test_user(cls.env, 'foundation_actor', groups='base.group_user,base.group_partner_manager')
        cls.reader = new_test_user(cls.env, 'foundation_reader', groups='base.group_user')

    def test_identity_and_record_lifecycle(self):
        with self.assertRaises(AccessError):
            self.env['res.partner'].with_user(self.reader).create({'name': 'Unapproved record'})
        partner = self.env['res.partner'].with_user(self.actor).create({
            'name': 'Owned foundation record', 'email': 'record@example.invalid'})
        partner.write({'name': 'Updated foundation record'})
        self.assertEqual(partner.read(['name'])[0]['name'], 'Updated foundation record')
        self.actor.sudo().write({'active': False})
        self.assertFalse(self.actor.active)
        self.assertTrue(partner.exists())

    def test_native_views_and_configuration_authority(self):
        views = self.env['res.partner'].with_user(self.actor).get_views([(False, 'list'), (False, 'form')])
        self.assertTrue({'list', 'form'} <= views['views'].keys())
        with self.assertRaises(AccessError):
            self.env['ir.config_parameter'].with_user(self.actor).set_param('foundation.unapproved', 'denied')

    def test_retirement_archive_privacy_immutability_and_raw_precision(self):
        raw='[{"amount": 9007199254740993.000000000000000001}]'
        self.env.cr.execute("INSERT INTO mp_retirement_archive (operation_id,recipe,source_image,source_inventory,table_name,row_count,sha256,payload) VALUES ('fixture','fixture','fixture','fixture','fixture',1,'fixture',%s) RETURNING id",[raw])
        ident=self.env.cr.fetchone()[0]
        archive=self.env['mp.retirement.archive'].browse(ident)
        self.assertEqual(archive.payload,raw)
        for user in (self.actor,self.reader):
            with self.assertRaises(AccessError):archive.with_user(user).read(['payload'])
        with self.assertRaises(AccessError):archive.sudo().write({'payload':'changed'})
        with self.assertRaises(AccessError):archive.sudo().unlink()
        with self.assertRaises(AccessError):archive.sudo().create({'payload':'unapproved'})
