from bika.lims.browser.workflow import RequestContextAware
from bika.lims.browser.workflow import WorkflowActionGenericAdapter
from bika.lims import bikaMessageFactory as _
from zope.interface import implements
from bika.lims.interfaces import IWorkflowActionUIDsAdapter
from bika.lims import api

class WorkflowActionCancelAdapter(WorkflowActionGenericAdapter):
    """Adapter in charge of Analysis Requests 'publish'-like actions
    """
    implements(IWorkflowActionUIDsAdapter)

    def __call__(self, action, uids):
        portal = api.get_portal()
        portal_url = api.get_url(portal)
        client_url = self.context.absolute_url()
        if "client" in client_url[-11:]:
            url = "{}/@@sampleimports".format(client_url)
        else:
            url = client_url

        messages = []
        objects = map(api.get_object_by_uid, uids)
        transitioned = self.do_action(action, objects)
    
        if not transitioned:
            return self.redirect(message=_("No changes made."), level="warning")

        ids =  map(api.get_id, transitioned)
        message = _("Cancelled items: {}").format(", ".join(ids))
        return self.redirect(redirect_url=url,message=message)
