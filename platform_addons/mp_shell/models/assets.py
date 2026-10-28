"""Retain published host bundles through Odoo's native asset factory.

The native controller already serves exact public attachment URLs with correct
types/cache headers. Keep their metadata and blobs so it need not redirect an
old checksum to current code. Retention/cleanup is a separate operator decision.
"""
import hashlib

from odoo import models
from odoo.addons.base.models.assetsbundle import AssetsBundle
from odoo.addons.mp_identity.release import image_inventory_digest


HOST_BUNDLE = 'mp_shell.assets_host'


class RetainedHostBundle(AssetsBundle):
    def get_version(self, asset_type):
        # Native versions truncate a timestamp/path descriptor to seven hex
        # characters. Bind its full variant descriptor to immutable image
        # contents, keeping native URL construction and exact serving intact.
        identity=':'.join((image_inventory_digest(),self.name,asset_type,self.get_checksum(asset_type)))
        return hashlib.sha256(identity.encode()).hexdigest()

    def _clean_attachments(self, extension, keep_url):
        # Called only for HOST_BUNDLE by the factory below. No global monkey
        # patch and no change to private/workspace attachment authorization.
        return True


class IrQWeb(models.AbstractModel):
    _inherit = 'ir.qweb'

    def _get_asset_bundle(self, bundle_name, css=True, js=True, debug_assets=False,
                          rtl=False, assets_params=None, autoprefix=False):
        if bundle_name != HOST_BUNDLE or debug_assets:
            return super()._get_asset_bundle(bundle_name, css=css, js=js,
                debug_assets=debug_assets, rtl=rtl, assets_params=assets_params,
                autoprefix=autoprefix)
        if assets_params is None:
            assets_params = self.env['ir.asset']._get_asset_params()
        files, external = self._get_asset_content(bundle_name, assets_params)
        return RetainedHostBundle(bundle_name, files, external, env=self.env,
            css=css, js=js, debug_assets=debug_assets, rtl=rtl,
            assets_params=assets_params, autoprefix=autoprefix)
