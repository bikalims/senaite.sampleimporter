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
# Copyright 2018-2021 by it's authors.
# Some rights reserved, see README and LICENSE.

from bika.lims import api

# from bika.lims.catalog import BIKA_CATALOG
from bika.lims.browser import ulocalized_time
from bika.lims.interfaces import IBatch
from bika.lims.interfaces import IContact
from bika.lims.interfaces import IContainerType
from bika.lims.interfaces import ISampleMatrix
from bika.lims.interfaces import ISamplePoint
from bika.lims.interfaces import ISampleType
from bika.lims.utils import tmpID
import csv
from DateTime.DateTime import DateTime
from datetime import datetime
from plone.autoform import directives
from plone.dexterity.content import Item
from plone.formwidget.contenttree import ObjPathSourceBinder
from plone.namedfile.field import NamedBlobFile
from plone.supermodel import model
from senaite.core.schema.fields import DataGridField
from senaite.core.schema.fields import DataGridRow
from senaite.core.z3cform.widgets.datagrid import DataGridWidgetFactory
from senaite.sampleimporter import logger
from senaite.sampleimporter import senaiteMessageFactory as _
from z3c.relationfield.schema import RelationChoice
from zope import schema

# from zope.component import getUtility
from zope.interface import implementer
from zope.interface import Interface


class ICCContactRow(Interface):
    CCNamesReport = schema.TextLine(title=u"CCNamesReport", required=False)
    CCEmailsReport = schema.TextLine(title=u"CCEmailsReport", required=False)
    CCNamesInvoice = schema.TextLine(title=u"CCNamesInvoice", required=False)
    CCEmailsInvoice = schema.TextLine(title=u"CCEmailsInvoice", required=False)


class ISampleDataRow(Interface):
    ClientSampleID = schema.TextLine(title=u"ClientSampleID", required=False)
    SamplingDate = schema.Date(title=u"SamplingDate", required=False)
    DateSampled = schema.Date(title=u"DateSampled", required=False)
    ClientReference = schema.TextLine(title=u"ClientReference", required=False)
    SamplePoint = RelationChoice(
        title=u"Sample Point",
        required=False,
        source=ObjPathSourceBinder(object_provides=ISamplePoint.__identifier__),
    )
    SampleMatrix = RelationChoice(
        title=u"Sample Matrix",
        required=False,
        source=ObjPathSourceBinder(object_provides=ISampleMatrix.__identifier__),
    )
    SampleType = RelationChoice(
        title=u"Sample Type",
        required=False,
        source=ObjPathSourceBinder(object_provides=ISampleType.__identifier__),
    )
    ContainerType = RelationChoice(
        title=u"Container Type",
        required=False,
        source=ObjPathSourceBinder(object_provides=IContainerType.__identifier__),
    )
    Analyses = schema.TextLine(title=u"Analyses", required=False)
    Profiles = schema.TextLine(title=u"Profiles", required=False)


class ISampleImport(model.Schema):
    """Schema and marker interface"""

    OriginalFile = NamedBlobFile(
        title=u"Original File",
        readonly=True,
        required=False,
    )
    Filename = schema.TextLine(
        title=u"Filename",
        required=True,
    )
    NrSamples = schema.TextLine(
        title=u"Number of Samples",
        required=True,
    )
    ClientName = schema.TextLine(
        title=u"Clientname",
        required=True,
    )
    ClientOrderNumber = schema.TextLine(
        title=u"ClientOrderNumber",
        required=True,
    )
    ClientReference = schema.TextLine(
        title=u"ClientReference",
        required=True,
    )
    Contact = RelationChoice(
        title=u"Contact",
        source=ObjPathSourceBinder(object_provides=IContact.__identifier__),
        required=False,
    )
    Batch = RelationChoice(
        title=u"Batch",
        source=ObjPathSourceBinder(object_provides=IBatch.__identifier__),
        required=True,
    )

    directives.widget("CCContacts", DataGridWidgetFactory, allow_reorder=True)
    CCContacts = DataGridField(
        title=u"CC Contacts",
        value_type=DataGridRow(title=u"CCContacts", schema=ICCContactRow),
        required=False,
    )

    directives.widget("SampleData", DataGridWidgetFactory, allow_reorder=True)
    SampleData = DataGridField(
        title=u"Sample Data",
        value_type=DataGridRow(title=u"SampleData", schema=ISampleDataRow),
        required=False,
    )

    Errors = schema.List(
        title=u"Errors",
        value_type=schema.TextLine(title=u"Error"),
        required=False,
    )


@implementer(ISampleImport)
class SampleImport(Item):
    """Holds information about an instrument location"""

    # Catalogs where this type will be catalogued
    _catalogs = ["portal_catalog"]

    def guard_validate_transition(self):
        """We may only attempt validation if file data has been uploaded."""
        data = self.OriginalFile.data
        if data and len(data):
            return True

    # TODO Workflow - SampleImport - Remove
    def workflow_before_validate(self):
        """This function transposes values from the provided file into the
        SampleImport object's fields, and checks for invalid values.

        If errors are found:
            - Validation transition is aborted.
            - Errors are stored on object and displayed to user.

        """
        # Re-set the errors on this SampleImport each time validation is attempted.
        # When errors are detected they are immediately appended to this field.
        self.setErrors([])

        self.validate_headers()
        self.validate_samples()

        if self.getErrors():
            addStatusMessage(self.REQUEST, _("Validation errors."), "error")
            transaction.commit()
            self.REQUEST.response.write(
                '<script>document.location.href="%s/edit"</script>'
                % (self.absolute_url())
            )
        self.REQUEST.response.write(
            '<script>document.location.href="%s/view"</script>' % (self.absolute_url())
        )

    def at_post_edit_script(self):
        workflow = api.get_tool("portal_workflow")
        trans_ids = [t["id"] for t in workflow.getTransitionsFor(self)]
        if "validate" in trans_ids:
            workflow.doActionFor(self, "validate")

    def workflow_script_import(self):
        """Create objects from valid SampleImport"""
        bsc = api.get_tool("bika_setup_catalog")
        client = self.aq_parent

        profiles = [x.getObject() for x in bsc(portal_type="AnalysisProfile")]

        gridrows = self.schema["SampleData"].get(self)
        row_cnt = 0
        for therow in gridrows:
            row = deepcopy(therow)
            row_cnt += 1

            # Profiles are titles, profile keys, or UIDS: convert them to UIDs.
            newprofiles = []
            for title in row["Profiles"]:
                objects = [
                    x
                    for x in profiles
                    if title in (x.getProfileKey(), x.UID(), x.Title())
                ]
                for obj in objects:
                    newprofiles.append(obj.UID())
            row["Profiles"] = newprofiles

            # Same for analyses
            newanalyses = set(
                self.get_row_services(row) + self.get_row_profile_services(row)
            )

            # get batch
            batch = self.schema["Batch"].get(self)
            if batch:
                row["Batch"] = batch.UID()

            # Add AR fields from schema into this row's data
            if not row.get("ClientReference"):
                row["ClientReference"] = self.getClientReference()
            row["ClientOrderNumber"] = self.getClientOrderNumber()
            contact_uid = self.getContact().UID() if self.getContact() else None
            row["Contact"] = contact_uid

            # Creating analysis request from gathered data
            create_analysisrequest(
                client,
                self.REQUEST,
                row,
                analyses=list(newanalyses),
            )

        self.REQUEST.response.redirect(client.absolute_url())

    def get_header_values(self):
        """Scrape the "Header" values from the original input file"""
        lines = self.OriginalFile.data.splitlines()
        reader = csv.reader(lines)
        header_fields = header_data = []
        for row in reader:
            if not any(row):
                continue
            if row[0].strip().lower() == "header":
                header_fields = [x.strip() for x in row][1:]
                continue
            if row[0].strip().lower() == "header data":
                header_data = [x.strip() for x in row][1:]
                break
        if not (header_data or header_fields):
            return None
        if not (header_data and header_fields):
            self.error("File is missing header row or header data")
            return None
        # inject us out of here
        values = dict(zip(header_fields, header_data))
        # blank cell from sheet will probably make it in here:
        if "" in values:
            del values[""]
        return values

    def save_header_data(self):
        """Save values from the file's header row into their schema fields."""
        client = self.aq_parent

        headers = self.get_header_values()
        if not headers:
            return False

        # Plain header fields that can be set into plain schema fields:
        for h, f in [
            ("File name", "Filename"),
            ("No of Samples", "NrSamples"),
            ("Client name", "ClientName"),
            ("Client ID", "ClientID"),
            ("Client Order Number", "ClientOrderNumber"),
            ("Client Reference", "ClientReference"),
        ]:
            # if f not in fields:
            #     raise RuntimeError('ImportSample: field {} in not in schema'.format(f))

            v = headers.get(h, None)
            if v:
                setattr(self, f, v)
            del headers[h]

        # Primary Contact
        v = headers.get("Contact", None)
        contacts = [x for x in client.objectValues("Contact")]
        contact = [c for c in contacts if c.Title() == v]
        if contact:
            setattr(self, "Contact", contact)
        else:
            self.error(
                "Specified contact '%s' does not exist; using '%s'"
                % (v, contacts[0].Title())
            )
            setattr(self, "Contact", contacts[0])
        del headers["Contact"]

        # CCContacts
        field_value = {
            "CCNamesReport": "",
            "CCEmailsReport": "",
            "CCNamesInvoice": "",
            "CCEmailsInvoice": "",
        }
        for h, f in [
            # csv header name      DataGrid Column ID
            ("CC Names - Report", "CCNamesReport"),
            ("CC Emails - Report", "CCEmailsReport"),
            ("CC Names - Invoice", "CCNamesInvoice"),
            ("CC Emails - Invoice", "CCEmailsInvoice"),
        ]:
            if h in headers:
                values = [x.strip() for x in headers.get(h, "").split(",")]
                field_value[f] = values if values else ""
                del headers[h]
        setattr(self, "CCContacts", [field_value])

        if headers:
            unexpected = ",".join(headers.keys())
            self.error("Unexpected header fields: %s" % unexpected)

    def get_sample_values(self):
        """Read the rows specifying Samples and return a dictionary with
        related data.

        keys are:
            headers - row with "Samples" in column 0.  These headers are
               used as dictionary keys in the rows below.
            prices - Row with "Analysis Price" in column 0.
            total_analyses - Row with "Total analyses" in colmn 0
            price_totals - Row with "Total price excl Tax" in column 0
            samples - All other sample rows.

        """
        res = {"samples": []}
        lines = self.OriginalFile.data.splitlines()
        reader = csv.reader(lines)
        next_rows_are_sample_rows = False
        for row in reader:
            if not any(row):
                continue
            if next_rows_are_sample_rows:
                vals = [x.strip() for x in row]
                if not any(vals):
                    continue
                res["samples"].append(zip(res["headers"], vals))
            elif row[0].strip().lower() == "samples":
                res["headers"] = [x.strip() for x in row]
            elif row[0].strip().lower() == "total analyses or profiles":
                res["total_analyses"] = zip(res["headers"], [x.strip() for x in row])
                next_rows_are_sample_rows = True
        return res

    def get_ar(self):
        """Create a temporary AR to fetch the fields from"""
        logger.info("*** CREATING TEMPORARY AR ***")
        return self.restrictedTraverse(
            "portal_factory/AnalysisRequest/Request new analyses"
        )

    def get_ar_schema(self):
        """Return the AR schema"""
        logger.info("*** GET AR SCHEMA ***")
        ar = self.get_ar()
        return ar.Schema()

    def save_sample_data(self):
        """Save values from the file's header row into the DataGrid columns
        after doing some very basic validation
        """
        bsc = api.get_tool("bika_setup_catalog")
        keywords = bsc.uniqueValuesFor("getKeyword")
        profiles = []
        for p in bsc(portal_type="AnalysisProfile"):
            p = p.getObject()
            profiles.append(p.Title())
            profiles.append(p.getProfileKey())

        sample_data = self.get_sample_values()
        if not sample_data:
            self.error("No sample data found")
            return False

        if len(self.NrSamples) == 0:
            self.error("'Number of samples' field is empty")
            return False

        # Incorrect number of samples
        if len(sample_data.get("samples", [])) != int(self.NrSamples):
            self.error(
                "No of Samples: {} expected but only {} found".format(
                    self.NrSamples, len(sample_data.get("samples", []))
                )
            )
            return False

        # columns that we expect, but do not find, are listed here.
        # we report on them only once, after looping through sample rows.
        missing = set()

        # This contains all sample header rows that were not handled
        # by this code
        unexpected = set()

        # Save other errors here instead of sticking them directly into
        # the field, so that they show up after MISSING and before EXPECTED
        errors = []

        # This will be the new sample-data field value, when we are done.
        grid_rows = []

        ar_schema = self.get_ar_schema()
        row_nr = 0
        for row in sample_data["samples"]:
            row = dict(row)
            row_nr += 1

            # sid is just for referring the user back to row X in their
            # in put spreadsheet
            gridrow = {"sid": row["Samples"]}
            del row["Samples"]

            # We'll use this later to verify the number against selections
            if "Total number of Analyses or Profiles" in row:
                nr_an = row["Total number of Analyses or Profiles"]
                del row["Total number of Analyses or Profiles"]
            else:
                nr_an = 0
            try:
                nr_an = int(nr_an)
            except ValueError:
                nr_an = 0

            # ContainerType - not part of sample or AR schema
            if "ContainerType" in row:
                title = row["ContainerType"]
                if title:
                    obj = self.lookup(("ContainerType",), Title=row["ContainerType"])
                    if obj:
                        gridrow["ContainerType"] = obj[0].UID
                del row["ContainerType"]

            # SampleMatrix - not part of sample or AR schema
            if "SampleMatrix" in row:
                title = row["SampleMatrix"]
                if title:
                    obj = self.lookup(("SampleMatrix",), Title=row["SampleMatrix"])
                    if obj:
                        gridrow["SampleMatrix"] = obj[0].UID
                del row["SampleMatrix"]

            # match against ar schema
            for k, v in row.items():
                if k in ["Analyses", "Profiles"]:
                    continue
                if k in ar_schema:
                    del row[k]
                    if v:
                        try:
                            value = self.munge_field_value(ar_schema, row_nr, k, v)
                            gridrow[k] = value
                        except ValueError as e:
                            errors.append(e.message)

            # Count and remove Keywords and Profiles from the list
            gridrow["Analyses"] = []
            for k, v in row.items():
                if k in keywords:
                    del row[k]
                    if str(v).strip().lower() not in ("", "0", "false"):
                        gridrow["Analyses"].append(k)
            gridrow["Profiles"] = []
            for k, v in row.items():
                if k in profiles:
                    del row[k]
                    if str(v).strip().lower() not in ("", "0", "false"):
                        gridrow["Profiles"].append(k)
            if len(gridrow["Analyses"]) + len(gridrow["Profiles"]) != nr_an:
                errors.append(
                    "Row %s: Number of analyses does not match provided value" % row_nr
                )

            grid_rows.append(gridrow)

        self.SampleData = grid_rows

        if missing:
            self.error("SAMPLES: Missing expected fields: %s" % ",".join(missing))

        for err in errors:
            self.error(err)

        if unexpected:
            self.error("Unexpected header fields: %s" % ",".join(unexpected))

    def get_batch_header_values(self):
        """Scrape the "Batch Header" values from the original input file"""
        lines = self.OriginalFile.data.splitlines()
        reader = csv.reader(lines)
        batch_headers = batch_data = []
        for row in reader:
            if not any(row):
                continue
            if row[0].strip().lower() == "batch header":
                batch_headers = [x.strip() for x in row][1:]
                continue
            if row[0].strip().lower() == "batch data":
                batch_data = [x.strip() for x in row][1:]
                # values = [i for i in batch_data if len(i) < 0]
                # if len(values) == 0:
                #     batch_data = []
                break
        if not (batch_data or batch_headers):
            return None
        if not (batch_data and batch_headers):
            self.error("Missing batch headers or data")
            return None
        # Inject us out of here
        values = dict(zip(batch_headers, batch_data))
        return values

    def create_or_reference_batch(self):
        """Save reference to batch, if existing batch specified
        Create new batch, if possible with specified values
        """
        client = self.aq_parent
        batch_headers = self.get_batch_header_values()
        if not batch_headers:
            return False
        # if the Batch's Title is specified and exists, no further
        # action is required. We will just set the Batch field to
        # use the existing object.
        batch_title = batch_headers.get("title", False)
        if batch_title:
            existing_batch = [
                x for x in client.objectValues("Batch") if x.title == batch_title
            ]
            if existing_batch:
                self.Batch = existing_batch[0]
                return existing_batch[0]
        # If the batch title is specified but does not exist,
        # we will attempt to create the bach now.
        if "title" in batch_headers:
            if "id" in batch_headers:
                del batch_headers["id"]
            if "" in batch_headers:
                del batch_headers[""]
            batch = api.create(client, "Batch", id=tmpID())
            batch.processForm()
            batch.edit(**batch_headers)
            batch.BatchDate = DateTime()
            self.Batch = batch

    def munge_field_value(self, schema, row_nr, fieldname, value):
        """Convert a spreadsheet value into a field value that fits in
        the corresponding schema field.
        - boolean: All values are true except '', 'false', or '0'.
        - reference: The title of an object in field.allowed_types;
            returns a UID or list of UIDs
        - datetime: returns a string value from ulocalized_time

        Tho this is only used during "Saving" of csv data into schema fields,
        it will flag 'validation' errors, as this is the only chance we will
        get to complain about these field values.

        """
        field = schema[fieldname]
        if field.type == "boolean":
            value = str(value).strip().lower()
            value = "" if value in ["0", "no", "false", "none"] else "1"
            return value
        if field.type in ["reference", "uidreference"]:
            value = str(value).strip()
            if len(value) < 2:
                raise ValueError(
                    "Row %s: value is too short (%s=%s)" % (row_nr, fieldname, value)
                )
            brains = self.lookup(field.allowed_types, Title=value)
            if not brains:
                brains = self.lookup(field.allowed_types, UID=value)
            if not brains:
                raise ValueError(
                    "Row %s: reference value is invalid (%s=%s)"
                    % (row_nr, fieldname, value)
                )
            if field.multiValued:
                return [b.UID for b in brains] if brains else []
            else:
                return brains[0].UID if brains else None
        if field.type == "datetime":
            try:
                value = datetime.strptime(value, "%d/%m/%Y").date()
                # value = DateTime(value)
                # value = ulocalized_time(value, long_format=True, time_only=False, context=self)
                return value
            except Exception as e:
                raise ValueError(
                    "Row %s: datetime value is invalid (%s=%s)"
                    % (row_nr, fieldname, value)
                )
        return str(value)

    def validate_headers(self):
        """Validate headers fields from schema"""

        pc = api.get_tool("portal_catalog")
        pu = api.get_tool("plone_utils")

        client = self.aq_parent

        # Verify Client Name
        if self.getClientName() != client.Title():
            self.error(
                "%s: client name value is invalid (%s)."
                % ("Client name", self.getClientName())
            )

        # Verify Client ID
        if self.getClientID() != client.getClientID():
            self.error(
                "%s: client ID value is invalid (%s)."
                % ("Client ID", self.getClientID())
            )

        existing_sampleimports = pc(
            portal_type="SampleImport", review_state=["valid", "imported"]
        )
        # Verify Client Order Number
        for sampleimport in existing_sampleimports:
            if (
                sampleimport.UID == self.UID()
                or not sampleimport.getClientOrderNumber()
            ):
                continue
            sampleimport = sampleimport.getObject()

            if sampleimport.getClientOrderNumber() == self.getClientOrderNumber():
                self.error(
                    "%s: already used by existing SampleImport." % "ClientOrderNumber"
                )
                break

        # Verify Client Reference
        for sampleimport in existing_sampleimports:
            if sampleimport.UID == self.UID() or not sampleimport.getClientReference():
                continue
            sampleimport = sampleimport.getObject()
            if sampleimport.getClientReference() == self.getClientReference():
                self.error(
                    "%s: already used by existing SampleImport." % "ClientReference"
                )
                break

        # getCCContacts has no value if object is not complete (eg during test)
        if self.getCCContacts():
            cc_contacts = self.getCCContacts()[0]
            contacts = [x for x in client.objectValues("Contact")]
            contact_names = [c.Title() for c in contacts]
            # validate Contact existence in this Client
            for k in ["CCNamesReport", "CCNamesInvoice"]:
                for val in cc_contacts[k]:
                    if val and val not in contact_names:
                        self.error("%s: CCNames value is invalid (%s)" % (k, val))
        else:
            cc_contacts = {
                "CCNamesReport": [],
                "CCEmailsReport": [],
                "CCNamesInvoice": [],
                "CCEmailsInvoice": [],
            }
            # validate Contact existence in this Client
            for k in ["CCEmailsReport", "CCEmailsInvoice"]:
                for val in cc_contacts.get(k, []):
                    if val and not pu.validateSingleNormalizedEmailAddress(val):
                        self.error("%s: CCEmails value is invalid (%s)" % (k, val))

    def validate_samples(self):
        """Scan through the SampleData values and make sure
        that each one is correct
        """

        bsc = api.get_tool("bika_setup_catalog")
        keywords = bsc.uniqueValuesFor("getKeyword")
        profiles = []
        for p in bsc(portal_type="AnalysisProfile"):
            p = p.getObject()
            profiles.append(p.Title())
            profiles.append(p.getProfileKey())

        row_nr = 0
        ar_schema = self.get_ar_schema()
        for gridrow in self.getSampleData():
            row_nr += 1

            # validate against sample and ar schemas
            for k, v in gridrow.items():
                if k in ["Analysis", "Profiles"]:
                    break
                if k in ar_schema:
                    try:
                        self.validate_against_schema(ar_schema, row_nr, k, v)
                    except ValueError as e:
                        self.error(e.message)

            an_cnt = 0
            for v in gridrow["Analyses"]:
                if v and v not in keywords:
                    self.error(
                        "Row %s: Analyses value is invalid (%s=%s)"
                        % ("Analysis keyword", row_nr, v)
                    )
                else:
                    an_cnt += 1
            for v in gridrow["Profiles"]:
                if v and v not in profiles:
                    self.error(
                        "Row %s: Profiles value is invalid (%s=%s)"
                        % ("Profile Title", row_nr, v)
                    )
                else:
                    an_cnt += 1
            if not an_cnt:
                self.error("Row %s: No valid analyses or profiles" % row_nr)

    def validate_against_schema(self, schema, row_nr, fieldname, value):
        """ """
        field = schema[fieldname]
        if field.type == "boolean":
            value = str(value).strip().lower()
            return value
        if field.type == "reference":
            value = str(value).strip()
            if field.required and not value:
                raise ValueError(
                    "Row %s: %s field requires a value" % (row_nr, fieldname)
                )
            if not value:
                return value
            brains = self.lookup(field.allowed_types, UID=value)
            if not brains:
                raise ValueError(
                    "Row %s: schema reference value is invalid (%s=%s)"
                    % (row_nr, fieldname, value)
                )
            if field.multiValued:
                return [b.UID for b in brains] if brains else []
            else:
                return brains[0].UID if brains else None
        if field.type == "datetime":
            try:
                ulocalized_time(
                    DateTime(value), long_format=True, time_only=False, context=self
                )
            except Exception as e:
                raise ValueError(
                    "Row %s: schema datetime value is invalid (%s=%s)"
                    % (row_nr, fieldname, value)
                )
        return value

    def lookup(self, allowed_types, **kwargs):
        """Lookup an object of type (allowed_types).  kwargs is sent
        directly to the catalog.
        """
        # schema = getUtility(IDexterityFTI, name='SampleImport').lookupSchema()
        # fields = schema.names()

        at = api.get_tool("archetype_tool")
        if type(allowed_types) not in (list, tuple):
            allowed_types = [allowed_types]

        if len(allowed_types) > 1:
            raise RuntimeError("lookup will only return first type!")

        for portal_type in allowed_types:
            catalog = at.catalog_map.get(portal_type, [None])[0]
            catalog = api.get_tool(catalog)
            kwargs["portal_type"] = portal_type
            brains = catalog(**kwargs)
            if brains:
                return brains

    def get_row_services(self, row):
        """Return a list of services which are referenced in Analyses.
        values may be UID, Title or Keyword.
        """
        bsc = api.get_tool("bika_setup_catalog")
        services = set()
        for val in row.get("Analyses", []):
            brains = bsc(portal_type="AnalysisService", getKeyword=val)
            if not brains:
                brains = bsc(portal_type="AnalysisService", title=val)
            if not brains:
                brains = bsc(portal_type="AnalysisService", UID=val)
            if brains:
                services.add(brains[0].UID)
            else:
                self.error("Invalid analysis specified: %s" % val)
        return list(services)

    def get_row_profile_services(self, row):
        """Return a list of services which are referenced in profiles
        values may be UID, Title or ProfileKey.
        """
        bsc = api.get_tool("bika_setup_catalog")
        services = set()
        profiles = [x.getObject() for x in bsc(portal_type="AnalysisProfile")]
        for val in row.get("Profiles", []):
            objects = [
                x for x in profiles if val in (x.getProfileKey(), x.UID(), x.Title())
            ]
            if objects:
                for service in objects[0].getService():
                    services.add(service.UID())
            else:
                self.error("Invalid profile specified: %s" % val)
        return list(services)

    def Vocabulary_SamplePoint(self):
        vocabulary = CatalogVocabulary(self)
        vocabulary.catalog = "bika_setup_catalog"
        folders = [self.bika_setup.bika_samplepoints]
        if IClient.providedBy(self.aq_parent):
            folders.append(self.aq_parent)
        return vocabulary(allow_blank=True, portal_type="SamplePoint")

    def Vocabulary_SampleMatrix(self):
        vocabulary = CatalogVocabulary(self)
        vocabulary.catalog = "bika_setup_catalog"
        return vocabulary(allow_blank=True, portal_type="SampleMatrix")

    def Vocabulary_SampleType(self):
        vocabulary = CatalogVocabulary(self)
        vocabulary.catalog = "bika_setup_catalog"
        folders = [self.bika_setup.bika_sampletypes]
        if IClient.providedBy(self.aq_parent):
            folders.append(self.aq_parent)
        return vocabulary(allow_blank=True, portal_type="SampleType")

    def Vocabulary_ContainerType(self):
        vocabulary = CatalogVocabulary(self)
        vocabulary.catalog = "bika_setup_catalog"
        return vocabulary(allow_blank=True, portal_type="ContainerType")

    def error(self, msg):
        errors = self.Errors
        if errors is None:
            errors = []
        if type(errors) != list:
            errors = [
                errors,
            ]
        errors.append(msg)
        self.Errors = errors
