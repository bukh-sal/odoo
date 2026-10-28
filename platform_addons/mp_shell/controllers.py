from odoo import http
from odoo.http import request
from odoo.addons.mp_identity.scopes import current_scope
from odoo.addons.mp_core.controllers import result
from odoo.addons.web.controllers.home import Home


class ShellHome(Home):
    def _login_redirect(self,uid,redirect=None):
        # Preserve native MFA/session redirect processing; change only the
        # successful default destination, not explicit/deep-link redirects.
        return super()._login_redirect(uid,redirect or '/')

    @http.route('/',type='http',auth='user',methods=['GET'])
    def index(self,**kwargs):
        # Narrow authenticated navigation metadata. Never choose a workspace on
        # the actor's behalf or expose arbitrary model/business dispatch here.
        request.env.cr.execute("""SELECT i.plugin_id,i.manifest FROM mp_plugin_installation i
            JOIN mp_workspace_plugin f ON f.installation_id=i.id
            JOIN mp_membership m ON m.workspace_id=f.workspace_id AND m.state='active'
            JOIN mp_principal p ON p.id=m.principal_id AND p.state='active'
            WHERE p.user_id=%s AND f.availability='enabled' AND i.state='installed'
            ORDER BY i.plugin_id""",[request.env.uid])
        for plugin,manifest in request.env.cr.fetchall():
            pages=manifest['ui']['pages']
            if pages:return request.redirect('/app/'+plugin+pages[0]['path'])
        return request.redirect('/app/settings')


class Shell(http.Controller):
    @http.route(['/app/<string:plugin>','/app/<string:plugin>/','/app/<string:plugin>/<path:page>','/app/settings'],type='http',auth='user',methods=['GET'])
    def app(self,plugin=None,page=None,**kwargs):
        # Bootstrap has no business data. Explicit URL workspace is validated
        # by /api/v1/context before rendering a page or native view.
        response=request.render('mp_shell.bootstrap',request.env['ir.http'].webclient_rendering_context())
        response.headers['Cache-Control']='no-store';response.headers['X-Frame-Options']='DENY'
        return response

    @http.route('/api/v1/navigation',type='http',auth='public',methods=['GET'])
    def navigation(self):
        def run():
            scope=current_scope(request.env)
            # Constrained current workspace feature metadata after live authority.
            request.env.cr.execute("""SELECT i.plugin_id,i.manifest FROM mp_plugin_installation i
                JOIN mp_workspace_plugin f ON f.installation_id=i.id
                WHERE f.workspace_id=%s AND f.availability='enabled' AND i.state='installed'
                ORDER BY i.plugin_id""",[scope.workspace_id])
            return [{'plugin_id':ident,'name':manifest['plugin']['name'],'pages':manifest['ui']['pages'],'navigation':manifest['ui']['navigation']} for ident,manifest in request.env.cr.fetchall() if manifest['ui']['pages']]
        return result(run)
