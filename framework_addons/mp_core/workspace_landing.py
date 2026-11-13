"""Neutral stock entry page; workspace choice grants no application authority."""
from odoo import http
from odoo.exceptions import AccessError
from odoo.http import request
from odoo.addons.web.controllers.home import Home
from odoo.addons.mp_identity.release import stock_webclient_default
from odoo.addons.mp_identity.scopes import resolve_scope


class WorkspaceLanding(Home):
    @http.route()
    def web_client(self, s_action=None, **kwargs):
        # Keep the original authentication/session/internal-user/redirect checks.
        # The returned bootstrap has not run in a browser, so no app action has
        # been selected. Existing scoped pages retain exactly that response.
        response = super().web_client(s_action=s_action, **kwargs)
        if (response.status_code != 200 or not stock_webclient_default()
                or request.httprequest.args.get('workspace')):
            return response
        workspaces = []
        unavailable = False
        try:
            rows = request.env['mp.workspace'].search([('state', '=', 'active')], order='name,id')
        except AccessError:
            rows = []
            unavailable = True
        for row in rows:
            try:
                # Fresh identity/membership policy, not a browser/session hint.
                resolve_scope(request.env, row.public_id)
            except AccessError:
                continue
            workspaces.append({'id': row.public_id, 'name': row.name})
        response = request.render('mp_core.workspace_landing', {
            'workspaces': workspaces, 'workspaces_unavailable': unavailable})
        response.headers['Cache-Control'] = 'no-store'
        response.headers['X-Frame-Options'] = 'DENY'
        return response
