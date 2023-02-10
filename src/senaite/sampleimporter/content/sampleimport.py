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

import csv
import sys
import transaction

from AccessControl import ClassSecurityInfo
from copy import deepcopy
from DateTime.DateTime import DateTime
from bika.lims.browser import ulocalized_time
from bika.lims.browser.widgets import ReferenceWidget as bReferenceWidget
from bika.lims.content.bikaschema import BikaSchema
from bika.lims.idserver import renameAfterCreation
from bika.lims.interfaces import IClient
from bika.lims.utils import getUsers, tmpID
from bika.lims.utils.analysisrequest import create_analysisrequest
from bika.lims.vocabularies import CatalogVocabulary
from plone.app.blob.field import FileField as BlobFileField
from Products.Archetypes.atapi import BaseContent
from Products.Archetypes.atapi import registerType
from Products.Archetypes.atapi import Schema
from Products.Archetypes.public import ComputedWidget
from Products.Archetypes.public import LinesField
from Products.Archetypes.public import LinesWidget
from Products.Archetypes.public import ReferenceField
from Products.Archetypes.public import ReferenceWidget
from Products.Archetypes.public import StringField
from Products.Archetypes.public import StringWidget
from Products.Archetypes.references import HoldingReference
from Products.Archetypes.utils import addStatusMessage
from Products.CMFCore.utils import getToolByName
from Products.CMFPlone.browser.search import quote_chars
from Products.CMFPlone.utils import _createObjectByType
from Products.DataGridField import Column
from Products.DataGridField import DataGridField
from Products.DataGridField import DataGridWidget
from Products.DataGridField import DatetimeLocalColumn
from Products.DataGridField import LinesColumn
from Products.DataGridField import SelectColumn
from senaite.sampleimporter.interfaces import ISampleImport
from senaite.sampleimporter import logger
from senaite.sampleimporter import PRODUCT_NAME
from senaite.sampleimporter import senaiteMessageFactory as _
from zope.interface import implements
from bika.lims import api


OriginalFile = BlobFileField(
    'OriginalFile',
    widget=ComputedWidget(
        visible=False
    ),
)

Filename = StringField(
    'Filename',
    widget=StringWidget(
        label=_('Original Filename'),
        visible={'view': 'visible', 'edit': 'invisible'}
    ),
)

NrSamples = StringField(
    'NrSamples',
    widget=StringWidget(
        label=_('Number of samples'),
        visible={'view': 'visible', 'edit': 'invisible'},
    ),
)

ClientName = StringField(
    'ClientName',
    searchable=True,
    widget=StringWidget(
        label=_("Client Name"),
        visible=False
    ),
)

ClientID = StringField(
    'ClientID',
    searchable=True,
    widget=StringWidget(
        label=_('Client ID'),
        visible=False
    ),
)

Contact = ReferenceField(
    'Contact',
    allowed_types=('Contact',),
    relationship='SampleImportContact',
    default_method='getContactUIDForUser',
    referenceClass=HoldingReference,
    vocabulary_display_path_bound=sys.maxint,
    widget=ReferenceWidget(
        label=_('Primary Contact'),
        size=20,
        visible=True,
        base_query={'is_active': True},
        showOn=True,
        popup_width='300px',
        colModel=[{'columnName': 'UID', 'hidden': True},
                  {'columnName': 'Fullname', 'width': '100',
                   'label': _('Name')}],
    ),
)

Batch = ReferenceField(
    'Batch',
    allowed_types=('Batch',),
    relationship='SampleImportBatch',
    widget=bReferenceWidget(
        label=_('Batch Title'),
        visible=True,
        catalog_name='senaite_catalog',
        base_query={'review_state': 'open'},
        showOn=True,
    ),
)

ClientBatchID = StringField(
    'ClientBatchID',
    searchable=True,
    widget=StringWidget(
        label=_('Client Batch ID'),
        visible=True
    ),
)

SampleData = DataGridField(
    'SampleData',
    allow_insert=True,
    allow_delete=True,
    allow_reorder=False,
    allow_empty_rows=False,
    allow_oddeven=True,
    columns=('ClientSampleID',
             'DateSampled',
             'Sampler',
             'SamplePoint',
             'SampleType',  # not a schema field!
             'AnalysisSpecification',
             'PublicationSpecification',
             'SampleCondition',
             'SampleContainer',  # not a schema field!
             'Analyses',  # not a schema field!
             'Profiles'  # not a schema field!
             ),
    widget=DataGridWidget(
        label=_('Samples'),
        columns={
            'ClientSampleID': Column('Client Sample ID'),
            'DateSampled': DatetimeLocalColumn('Date Sampled'),
            'Sampler': SelectColumn(
                'Sampler', vocabulary='Vocabulary_Sampler'),
            'SamplePoint': SelectColumn(
                'Sample Point', vocabulary='Vocabulary_SamplePoint'),
            'SampleType': SelectColumn(
                'Sample Type', vocabulary='Vocabulary_SampleType'),
            'AnalysisSpecification': SelectColumn(
                'Analysis Specification', vocabulary='Vocabulary_AnalysisSpecification'),
            'PublicationSpecification': SelectColumn(
                'Publication Specification', vocabulary='Vocabulary_AnalysisSpecification'),
            'SampleCondition': SelectColumn(
                'Sample Condition', vocabulary='Vocabulary_SampleCondition'),
            'SampleContainer': SelectColumn(
                'Sample Container', vocabulary='Vocabulary_SampleContainer'),
            'Analyses': LinesColumn('Analyses'),
            'Profiles': LinesColumn('Profiles'),
        }
    )
)

Errors = LinesField(
    'Errors',
    widget=LinesWidget(
        label=_('Errors'),
        rows=10,
    )
)

schema = BikaSchema.copy() + Schema((
    OriginalFile,
    Filename,
    NrSamples,
    ClientName,
    ClientID,
    Contact,
    Batch,
    ClientBatchID,
    SampleData,
    Errors,
))

schema['title'].validators = ()
schema['title'].widget.label = "ID"
# Update the validation layer after change the validator in runtime
schema['title']._validationLayer()


class SampleImport(BaseContent):
    security = ClassSecurityInfo()
    implements(ISampleImport)
    schema = schema

    _at_rename_after_creation = True

    def _renameAfterCreation(self, check_auto_id=False):
        renameAfterCreation(self)

    def guard_validate_transition(self):
        """We may only attempt validation if file data has been uploaded.
        """
        data = self.getOriginalFile()
        if data and data.getSize():
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
            addStatusMessage(self.REQUEST, _('Validation errors.'), 'error')
            transaction.commit()
            self.REQUEST.response.write(
                '<script>document.location.href="%s/edit"</script>' % (
                    self.absolute_url()))
        self.REQUEST.response.write(
            '<script>document.location.href="%s/view"</script>' % (
                self.absolute_url()))

    @security.public
    def getFilename(self):
        """Returns the filename
        """
        return self.getField('Filename').get(self)

    def at_post_edit_script(self):
        workflow = api.get_tool("portal_workflow")
        trans_ids = [t["id"] for t in workflow.getTransitionsFor(self)]
        if "validate" in trans_ids:
            self.setErrors([])
            workflow.doActionFor(self, "validate")

    def workflow_script_import(self):
        """Create objects from valid SampleImport"""
        bsc = api.get_tool("senaite_catalog_setup")
        client = self.aq_parent

        profiles = [x.getObject() for x in bsc(portal_type='AnalysisProfile')]

        gridrows = self.schema['SampleData'].get(self)
        row_cnt = 0
        for therow in gridrows:
            row = deepcopy(therow)
            row_cnt += 1

            # Profiles are titles, profile keys, or UIDS: convert them to UIDs.
            newprofiles = []
            for title in row['Profiles']:
                objects = [x for x in profiles
                           if title in (x.getProfileKey(), x.UID(), x.Title())]
                for obj in objects:
                    newprofiles.append(obj.UID())
            row['Profiles'] = newprofiles

            # Same for analyses
            newanalyses = set(self.get_row_services(row) +
                              self.get_row_profile_services(row))

            # get batch
            batch = self.schema['Batch'].get(self)
            if batch:
                row['Batch'] = batch.UID()

            # Add AR fields from schema into this row's data
            contact_object = self.getContact()
            contact_uid =\
                contact_object.UID() if contact_object else None
            row['Contact'] = contact_uid
            if contact_object.getCCContact():
                cc_contacts =\
                    [cc.UID() for cc in contact_object.getCCContact()]
                row['CCContact'] = cc_contacts
            # Creating analysis request from gathered data
            row['Container'] = row.pop('SampleContainer') #SampleContainers are titled containers in analysis requests.
            row['Specification'] = row.pop('AnalysisSpecification') #Naming convention for Analysis specifications in the schema
            row['Specification_uid'] = row.get('Specification')
            create_analysisrequest(
                client,
                self.REQUEST,
                row,
                analyses=list(newanalyses),)

        self.REQUEST.response.redirect(client.absolute_url())

    def get_header_values(self):
        """Scrape the "Header" values from the original input file
        """
        lines = self.getOriginalFile().data.splitlines()
        reader = csv.reader(lines)
        header_fields = header_data = []
        for row in reader:
            if not any(row):
                continue
            if row[0].strip().lower() == 'header':
                header_fields = [x.strip() for x in row][1:]
                continue
            if row[0].strip().lower() == 'header data':
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
        if '' in values:
            del (values[''])
        return values

    def save_header_data(self):
        """Save values from the file's header row into their schema fields.
        """
        client = self.aq_parent

        headers = self.get_header_values()
        if not headers:
            return False

        # Plain header fields that can be set into plain schema fields:
        for h, f in [
            ('Client name', 'ClientName'),
            ('Client ID', 'ClientID'),
        ]:
            v = headers.get(h, None)
            if v:
                field = self.schema[f]
                field.set(self, v)
            del (headers[h])

        # Primary Contact
        v = headers.get('Contact', None)
        contacts = [x for x in client.objectValues('Contact')]
        contact = [c for c in contacts if c.Title() == v]
        if contact:
            self.schema['Contact'].set(self, contact)
        else:
            self.error("Specified contact '%s' does not exist; using '%s'" %
                       (v, contacts[0].Title()))
            self.schema['Contact'].set(self, contacts[0])
        del (headers['Contact'])

        if headers:
            unexpected = ','.join(headers.keys())
            self.error("Unexpected header fields: %s" % unexpected)

    def get_sample_values(self):
        """Read the rows specifying Samples and return a dictionary with
        related data.

        keys are:
            headers - row with "Samples" in column 0.  These headers are
               used as dictionary keys in the rows below.
            prices - Row with "Analysis Price" in column 0.
            total_analyses - Row with "Total analyses" in colmn 0 (removed)
            price_totals - Row with "Total price excl Tax" in column 0
            samples - All other sample rows.

        """
        res = {'samples': []}
        lines = self.getOriginalFile().data.splitlines()
        reader = csv.reader(lines)
        next_rows_are_sample_rows = False
        for row in reader:
            if not any(row):
                continue
            if next_rows_are_sample_rows:
                vals = []
                for indx,x in enumerate(row):
                    if indx!=3:
                        if indx == 2:
                            vals.append(x.strip()+" "+row[3].strip()) #Here we combine DateSampled and TimeSampled
                        else:
                            vals.append(x.strip())    
                if not any(vals):
                    continue
                res['samples'].append(zip(res['headers'], vals))
            elif row[0].strip().lower() == 'samples':
                headers = []
                for x in row:
                    if x!= "TimeSampled":
                        headers.append(x.strip())
                res['headers'] = headers
                next_rows_are_sample_rows = True 
        return res

    def get_ar(self):
        """Create a temporary AR to fetch the fields from
        """
        logger.info("*** CREATING TEMPORARY AR ***")
        return self.restrictedTraverse(
            "portal_factory/AnalysisRequest/Request new analyses")

    def get_ar_schema(self):
        """Return the AR schema
        """
        logger.info("*** GET AR SCHEMA ***")
        ar = self.get_ar()
        return ar.Schema()

    def save_sample_data(self):
        """Save values from the file's header row into the DataGrid columns
        after doing some very basic validation
        """
        bsc = api.get_tool("senaite_catalog_setup")
        keywords = bsc.uniqueValuesFor("getKeyword")
        profiles = []
        for p in bsc(portal_type='AnalysisProfile'):
            p = p.getObject()
            profiles.append(p.Title())
            profiles.append(p.getProfileKey())

        sample_data = self.get_sample_values()
        if not sample_data:
            self.error("No sample data found")
            return False

        self.schema['NrSamples'].set(self,len(sample_data.get('samples', [])))
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
        for row in sample_data['samples']:
            row = dict(row)
            row_nr += 1

            # sid is just for referring the user back to row X in their
            # in put spreadsheet
            gridrow = {'sid': row['Samples']}
            del (row['Samples'])

            # ContainerType - not part of sample or AR schema
            
            if 'SampleContainer' in row:
                title = row['SampleContainer']
                if title:
                    obj = self.lookup(('SampleContainer',),
                                      Title=row['SampleContainer'])
                    if obj:
                        gridrow['SampleContainer'] = obj[0].UID
                del (row['SampleContainer'])

            if 'Sampler' in row:
                title = row['Sampler']
                if title:
                    Users = getUsers(self, ['Sampler', ])
                    for name in Users.items():
                        if title in name[1]:
                            gridrow['Sampler'] = name[0]
                            del (row['Sampler'])

            if 'AnalysisSpecification' in row:
                title = row['AnalysisSpecification']
                if title:
                    obj = self.lookup(('AnalysisSpec',),
                                      Title=row['AnalysisSpecification'])
                    if obj:
                        gridrow['AnalysisSpecification'] = obj[0].UID
                del (row['AnalysisSpecification'])

            # match against ar schema
            for k, v in row.items():
                if k in ['Analyses', 'Profiles']:
                    continue
                if k in ar_schema:
                    del (row[k])
                    if v:
                        try:
                            value = self.munge_field_value(
                                ar_schema, row_nr, k, v)
                            gridrow[k] = value
                        except ValueError as e:
                            errors.append(e.message)

            # Count and remove Keywords and Profiles from the list
            gridrow['Analyses'] = []
            for k, v in row.items():
                if k in keywords:
                    del (row[k])
                    if str(v).strip().lower() not in ('', '0', 'false'):
                        gridrow['Analyses'].append(k)
            gridrow['Profiles'] = []
            for k, v in row.items():
                if k in profiles:
                    del (row[k])
                    if str(v).strip().lower() not in ('', '0', 'false'):
                        gridrow['Profiles'].append(k)

            grid_rows.append(gridrow)

        self.setSampleData(grid_rows)

        if missing:
            self.error("SAMPLES: Missing expected fields: %s" %
                       ','.join(missing))

        for err in errors:
            self.error(err)

        if unexpected:
            self.error("Unexpected header fields: %s" %
                       ','.join(unexpected))

    def get_batch_header_values(self):
        """Scrape the "Batch Header" values from the original input file
        """
        lines = self.getOriginalFile().data.splitlines()
        reader = csv.reader(lines)
        batch_headers = batch_data = []
        for row in reader:
            if not any(row):
                continue
            if row[0].strip().lower() == 'batch header':
                batch_headers = [x.strip() for x in row][1:]
                continue
            if row[0].strip().lower() == 'batch data':
                batch_data = [x.strip() for x in row][1:]
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
        batch_title = batch_headers.get('title', False)
        client_batch_id = batch_headers.get('ClientBatchID')
        self.setClientBatchID(client_batch_id)
        if batch_title:
            existing_batch = [x for x in client.objectValues('Batch')
                              if x.title == batch_title]
            if existing_batch:
                self.setBatch(existing_batch[0])
                return existing_batch[0]
        # If the batch title is specified but does not exist,
        # we will attempt to create the bach now.
        if 'title' in batch_headers:
            if 'id' in batch_headers:
                del (batch_headers['id'])
            if '' in batch_headers:
                del (batch_headers[''])
            batch = api.create(client, "Batch", id=tmpID())
            batch.processForm()
            batch.edit(**batch_headers)
            batch.BatchDate = DateTime()
            self.Batch = batch
            self.setBatch(batch) # Here we set the new batch

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
        if field.type == 'boolean':
            value = str(value).strip().lower()
            value = '' if value in ['0', 'no', 'false', 'none'] else '1'
            return value
        if field.type in ['reference', 'uidreference']:
            value = str(value).strip()
            if len(value) < 2:
                raise ValueError('Row %s: value is too short (%s=%s)' % (
                    row_nr, fieldname, value))
            brains = self.lookup(field.allowed_types, Title=value)
            if not brains:
                brains = self.lookup(field.allowed_types, UID=value)
            if not brains:
                raise ValueError('Row %s: value is invalid (%s=%s)' % (
                    row_nr, fieldname, value))
            if field.multiValued:
                return [b.UID for b in brains] if brains else []
            else:
                return brains[0].UID if brains else None
        if field.type == 'datetime' or field.type == 'datetime_ng':
            try:
                value = DateTime(value)
                return ulocalized_time(
                    value, long_format=True, time_only=False, context=self)
            except Exception as e:
                raise ValueError('Row %s: value is invalid (%s=%s)' % (
                    row_nr, fieldname, value))
        return str(value)

    def validate_headers(self):
        """Validate headers fields from schema
        """

        client = self.aq_parent

        # Verify Client Name
        if self.getClientName() != client.Title():
            self.error("%s: value is invalid (%s)." % (
                'Client name', self.getClientName()))

        # Verify Client ID
        if self.getClientID() != client.getClientID():
            self.error("%s: value is invalid (%s)." % (
                'Client ID', self.getClientID()))

    def validate_samples(self):
        """Scan through the SampleData values and make sure
        that each one is correct
        """

        bsc = api.get_tool("senaite_catalog_setup")
        keywords = bsc.uniqueValuesFor("getKeyword")
        profiles = []
        for p in bsc(portal_type='AnalysisProfile'):
            p = p.getObject()
            profiles.append(p.Title())
            profiles.append(p.getProfileKey())

        row_nr = 0
        ar_schema = self.get_ar_schema()
        for gridrow in self.getSampleData():
            row_nr += 1

            # validate against sample and ar schemas
            for k, v in gridrow.items():
                if k in ['Analysis', 'Profiles']:
                    break
                if k in ar_schema:
                    try:
                        self.validate_against_schema(
                            ar_schema, row_nr, k, v)
                    except ValueError as e:
                        self.error(e.message)

            an_cnt = 0
            for v in gridrow['Analyses']:
                if v and v not in keywords:
                    self.error("Row %s: value is invalid (%s=%s)" %
                               ('Analysis keyword', row_nr, v))
                else:
                    an_cnt += 1
            for v in gridrow['Profiles']:
                if v and v not in profiles:
                    self.error("Row %s: value is invalid (%s=%s)" %
                               ('Profile Title', row_nr, v))
                else:
                    an_cnt += 1
            if not an_cnt:
                self.error("Row %s: No valid analyses or profiles" % row_nr)

    def validate_against_schema(self, schema, row_nr, fieldname, value):
        """
        """
        field = schema[fieldname]
        if field.type == 'boolean':
            value = str(value).strip().lower()
            return value
        if field.type == 'reference':
            value = str(value).strip()
            if field.required and not value:
                raise ValueError("Row %s: %s field requires a value" % (
                    row_nr, fieldname))
            if not value:
                return value
            brains = self.lookup(field.allowed_types, UID=value)
            if not brains:
                raise ValueError("Row %s: value is invalid (%s=%s)" % (
                    row_nr, fieldname, value))
            if field.multiValued:
                return [b.UID for b in brains] if brains else []
            else:
                return brains[0].UID if brains else None
        if field.type == 'datetime':
            try:
                ulocalized_time(DateTime(value), long_format=True,
                                time_only=False, context=self)
            except Exception as e:
                raise ValueError('Row %s: value is invalid (%s=%s)' % (
                    row_nr, fieldname, value))
        return value

    def lookup(self, allowed_types, **kwargs):
        """Lookup an object of type (allowed_types).  kwargs is sent
        directly to the catalog.
        """
        at = getToolByName(self, 'archetype_tool')
        if type(allowed_types) not in (list, tuple):
            allowed_types = [allowed_types]
        for portal_type in allowed_types:
            if portal_type == 'SampleContainer':
                catalog = at.catalog_map.get('Container', [None])[0]
            elif portal_type == 'AnalysisSpec':
                catalog = at.catalog_map.get('AnalysisSpec', [None])[0]
            else:
                catalog = at.catalog_map.get(portal_type, [None])[0]
            catalog = getToolByName(self, catalog)
            kwargs['portal_type'] = portal_type
            if kwargs.get('Title'):
                kwargs['Title'] =  quote_chars(kwargs['Title'])
            if kwargs.get('UID'):
                kwargs['UID'] =  quote_chars(kwargs['UID'])
            brains = catalog(**kwargs)
            if brains:
                return brains

    def get_row_services(self, row):
        """Return a list of services which are referenced in Analyses.
        values may be UID, Title or Keyword.
        """
        bsc = api.get_tool("senaite_catalog_setup")
        services = set()
        for val in row.get('Analyses', []):
            brains = bsc(portal_type='AnalysisService', getKeyword=val)
            if not brains:
                brains = bsc(portal_type='AnalysisService', title=val)
            if not brains:
                brains = bsc(portal_type='AnalysisService', UID=val)
            if brains:
                services.add(brains[0].UID)
            else:
                self.error("Invalid analysis specified: %s" % val)
        return list(services)

    def get_row_profile_services(self, row):
        """Return a list of services which are referenced in profiles
        values may be UID, Title or ProfileKey.
        """
        bsc = api.get_tool("senaite_catalog_setup")
        services = set()
        profiles = [x.getObject() for x in bsc(portal_type='AnalysisProfile')]
        for val in row.get('Profiles', []):
            objects = [x for x in profiles
                       if val in (x.getProfileKey(), x.UID(), x.Title())]
            if objects:
                for service in objects[0].getService():
                    services.add(service.UID())
            else:
                self.error("Invalid profile specified: %s" % val)
        return list(services)

    def Vocabulary_SamplePoint(self):
        vocabulary = CatalogVocabulary(self)
        vocabulary.catalog = "senaite_catalog_setup"
        folders = [self.bika_setup.bika_samplepoints]
        if IClient.providedBy(self.aq_parent):
            folders.append(self.aq_parent)
        return vocabulary(allow_blank=True, portal_type='SamplePoint')

    def Vocabulary_SampleType(self):
        vocabulary = CatalogVocabulary(self)
        vocabulary.catalog = "senaite_catalog_setup"
        folders = [self.bika_setup.bika_sampletypes]
        if IClient.providedBy(self.aq_parent):
            folders.append(self.aq_parent)
        return vocabulary(allow_blank=True, portal_type='SampleType')

    def Vocabulary_AnalysisSpecification(self):
        vocabulary = CatalogVocabulary(self)
        vocabulary.catalog = "senaite_catalog_setup"
        folders = [self.bika_setup.bika_analysisspecs]#change
        if IClient.providedBy(self.aq_parent):
            folders.append(self.aq_parent)
        return vocabulary(allow_blank=True, portal_type='AnalysisSpec')

    def Vocabulary_SampleCondition(self):
        vocabulary = CatalogVocabulary(self)
        vocabulary.catalog = "senaite_catalog_setup"
        folders = [self.bika_setup.bika_sampleconditions]#change
        if IClient.providedBy(self.aq_parent):
            folders.append(self.aq_parent)
        return vocabulary(allow_blank=True, portal_type='SampleCondition')

    def Vocabulary_SampleContainer(self):
        vocabulary = CatalogVocabulary(self)
        vocabulary.catalog = "senaite_catalog_setup"
        folders = [self.bika_setup.sample_containers]
        if IClient.providedBy(self.aq_parent):
            folders.append(self.aq_parent)
        return vocabulary(allow_blank=True, portal_type="SampleContainer")

    def Vocabulary_Sampler(self):
        return getUsers(self, ['Sampler', ])

    def error(self, msg):
        errors = list(self.getErrors())
        errors.append(msg)
        self.setErrors(errors)


registerType(SampleImport, PRODUCT_NAME)
