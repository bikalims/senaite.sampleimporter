# -*- coding: utf-8 -*-
#
# This file is part of SENAITE.CORE.
#
# SENAITE.CORE is free software: you can redistribute it and/or modify it under
# the terms of the GNU General Public License as published by the Free Software
# Foundation, version 2.
#
# This program is distributed in the hope that it will be useful, but WITHOUT
# ANY WARRANTY; without even the implied warranty of MERCHANTABILITY or FITNESS
# FOR A PARTICULAR PURPOSE. See the GNU General Public License for more
# details.
#
# You should have received a copy of the GNU General Public License along with
# this program; if not, write to the Free Software Foundation, Inc., 51
# Franklin Street, Fifth Floor, Boston, MA 02110-1301 USA.
#
# Copyright 2018-2019 by it's authors.
# Some rights reserved, see README and LICENSE.

import os
from bika.lims import api
from bika.lims import bikaMessageFactory as _
from bika.lims.browser import BrowserView, ulocalized_time
from bika.lims.browser.bika_listing import BikaListingView
from bika.lims.interfaces import IClient
from bika.lims.utils import tmpID
from bika.lims.workflow import getTransitionDate
from plone.app.contentlisting.interfaces import IContentListing
from plone.app.layout.globals.interfaces import IViewView
from plone.namedfile.file import NamedBlobFile
from plone.protect import CheckAuthenticator
from Products.Archetypes.utils import addStatusMessage
from Products.CMFCore.utils import getToolByName
from Products.CMFCore.WorkflowCore import WorkflowException
from Products.Five.browser.pagetemplatefile import ViewPageTemplateFile
from zope.interface import alsoProvides
from zope.interface import implements


class SampleImportsView(BikaListingView):
    implements(IViewView)

    def __init__(self, context, request):
        super(SampleImportsView, self).__init__(context, request)
        request.set("disable_plone.rightcolumn", 1)
        alsoProvides(request, IContentListing)

        self.catalog = "portal_catalog"
        self.contentFilter = {
            "portal_type": "SampleImport",
            "is_active": True,
            "sort_on": "sortable_title",
        }
        self.context_actions = {}
        if IClient.providedBy(self.context):
            self.context_actions = {
                _("Bulk Import File"): {
                    "url": "sampleimport_add",
                    "icon": "++resource++bika.lims.images/add.png",
                }
            }

        self.show_select_row = False
        self.show_select_column = False
        self.pagesize = 50
        self.form_id = "sampleimports"

        self.icon = (
            self.portal_url
            + "/++resource++senaite.sampleimporter.static/img/sampleimport_big.png"
        )
        self.title = self.context.translate(_("Sample Imports"))
        self.description = ""

        self.columns = {
            "Title": {"title": _("Title")},
            "Client": {"title": _("Client")},
            "Contact": {"title": _("Contact")},
            "Filename": {"title": _("Filename")},
            "Creator": {"title": _("Date Created")},
            "DateCreated": {"title": _("Date Created")},
            "DateValidated": {"title": _("Date Validated")},
            "DateImported": {"title": _("Date Imported")},
            "state_title": {"title": _("State")},
        }
        self.review_states = [
            {
                "id": "default",
                "title": _("Pending"),
                "contentFilter": {"review_state": ["invalid", "valid"]},
                "columns": [
                    "Title",
                    "Creator",
                    "Filename",
                    "Client",
                    "Contact",
                    "DateCreated",
                    "DateValidated",
                    "DateImported",
                    "state_title",
                ],
            },
            {
                "id": "imported",
                "title": _("Imported"),
                "contentFilter": {"review_state": "imported"},
                "columns": [
                    "Title",
                    "Creator",
                    "Filename",
                    "Client",
                    "Contact",
                    "DateCreated",
                    "DateValidated",
                    "DateImported",
                    "state_title",
                ],
            },
        ]

    def folderitems(self, **kwargs):
        items = super(SampleImportsView, self).folderitems()
        for x in range(len(items)):
            if "obj" not in items[x]:
                continue
            obj = api.get_object(items[x]["obj"])
            items[x]["Title"] = obj.title_or_id()
            items[x]["replace"]["Title"] = "<a href='%s/view'>%s</a>" % (
                obj.absolute_url(),
                items[x]["Title"],
            )
            items[x]["Creator"] = obj.Creator()
            items[x]["Filename"] = obj.getFilename()
            parent = obj.aq_parent
            items[x]["Client"] = parent if IClient.providedBy(parent) else ""
            items[x]["replace"]["Client"] = "<a href='%s'>%s</a>" % (
                parent.absolute_url(),
                parent.Title(),
            )
            items[x]["Contact"] = obj.Contact
            items[x]["DateCreated"] = ulocalized_time(
                obj.created(), long_format=True, time_only=False, context=obj
            )
            date = getTransitionDate(obj, "validate")
            items[x]["DateValidated"] = date if date else ""
            date = getTransitionDate(obj, "import")
            items[x]["DateImported"] = date if date else ""

        return items


class ClientSampleImportsView(SampleImportsView):
    def __init__(self, context, request):
        super(ClientSampleImportsView, self).__init__(context, request)
        self.contentFilter["path"] = {"query": "/".join(context.getPhysicalPath())}

        self.review_states = [
            {
                "id": "default",
                "title": _("Pending"),
                "contentFilter": {"review_state": ["invalid", "valid"]},
                "columns": [
                    "Title",
                    "Creator",
                    "Filename",
                    "DateCreated",
                    "DateValidated",
                    "DateImported",
                    "state_title",
                ],
            },
            {
                "id": "imported",
                "title": _("Imported"),
                "contentFilter": {"review_state": "imported"},
                "columns": [
                    "Title",
                    "Creator",
                    "Filename",
                    "DateCreated",
                    "DateValidated",
                    "DateImported",
                    "state_title",
                ],
            },
        ]


class ClientSampleImportAddView(BrowserView):
    implements(IViewView)
    template = ViewPageTemplateFile("templates/sampleimport_add.pt")

    def __init__(self, context, request):
        super(ClientSampleImportAddView, self).__init__(context, request)
        alsoProvides(request, IContentListing)

    def __call__(self):
        request = self.request
        form = request.form
        CheckAuthenticator(form)
        if form.get("submitted"):
            # Validate form submission
            csvfile = form.get("csvfile")
            data = csvfile.read()
            lines = data.splitlines()
            filename = csvfile.filename
            if not csvfile:
                addStatusMessage(request, _("No file selected"))
                return self.template()

            if len(lines) < 3:
                addStatusMessage(request, _("Too few lines in CSV file"))
                return self.template()

            # Create the sampleimport object
            sampleimport = api.create(self.context, "SampleImport", id=tmpID())
            sampleimport.processForm()
            sampleimport.setTitle(sampleimport.getId())
            sampleimport.Filename = filename
            sampleimport.OriginalFile = NamedBlobFile(data=data, filename=_(filename))

            # Setup headers
            sampleimport.save_header_data()
            if sampleimport.Errors:
                self.request.response.redirect(sampleimport.absolute_url())
                return self.template()

            # Save all fields from the file into the sampleimport schema
            sampleimport.save_sample_data()
            if sampleimport.Errors:
                sampleimport.SampleData = None
                self.request.response.redirect(sampleimport.absolute_url())
                return

            # immediate folderbatch creation if required
            sampleimport.create_or_reference_batch()

            # Attempt first validation
            try:
                # TODO wft = api.get_tool('portal_workflow')
                # wft.doActionFor(sampleimport, 'validate')
                self.request.response.redirect(sampleimport.absolute_url())
            except WorkflowException:
                self.request.response.redirect(
                    "{}/sampleimports".format(self.context.absolute_url())
                )
        else:
            return self.template()

    def mkTitle(self, filename):
        pc = getToolByName(self.context, "portal_catalog")
        nr = 1
        while True:
            newname = "%s-%s" % (os.path.splitext(filename)[0], nr)
            existing = pc(portal_type="SampleImport", title=newname)
            if not existing:
                return newname
            nr += 1
