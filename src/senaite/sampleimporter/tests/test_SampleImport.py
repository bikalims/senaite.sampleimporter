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

import re

import transaction
from bika.lims.catalog import (CATALOG_ANALYSIS_LISTING,
                               CATALOG_ANALYSIS_REQUEST_LISTING)
from bika.lims.utils import tmpID
from bika.lims.workflow import doActionFor, getCurrentState
from plone.app.testing import (TEST_USER_ID, TEST_USER_NAME,
                               TEST_USER_PASSWORD, login, setRoles)
from Products.CMFCore.utils import getToolByName
from Products.CMFPlone.utils import _createObjectByType
from senaite.sampleimporter.tests.base import SimpleTestCase

try:
    import unittest2 as unittest
except ImportError:  # Python 2.7
    import unittest


class TestSampleImports(SimpleTestCase):
    def addthing(self, folder, portal_type, **kwargs):
        thing = _createObjectByType(portal_type, folder, tmpID())
        thing.unmarkCreationFlag()
        thing.edit(**kwargs)
        thing._renameAfterCreation()
        return thing

    def setUp(self):
        super(TestSampleImports, self).setUp()
        setRoles(self.portal, TEST_USER_ID, ['Member', 'LabManager'])
        login(self.portal, TEST_USER_NAME)
        client = self.addthing(
            self.portal.clients, 'Client', title='Happy Hills', ClientID='HH')
        self.addthing(
            client, 'Contact', Firstname='Rita Mohale', Lastname='Mohale')
        self.addthing(
            self.portal.bika_setup.bika_sampletypes, 'SampleType',
            title='Water', Prefix='H2O')
        self.addthing(
            self.portal.bika_setup.bika_samplematrices, 'SampleMatrix',
            title='Liquids')
        self.addthing(
            self.portal.bika_setup.bika_samplepoints, 'SamplePoint',
            title='Toilet')
        self.addthing(
            self.portal.bika_setup.bika_samplepoints, 'SamplePoint',
            title='Bracketville (Centre)')
        self.addthing(
            self.portal.bika_setup.bika_samplepoints, 'SamplePoint',
            title='(Land) of (Brackets) station')
        self.addthing(
            self.portal.bika_setup.bika_containertypes, 'ContainerType',
            title='Cup')
        a = self.addthing(
            self.portal.bika_setup.bika_analysisservices, 'AnalysisService',
            title='Ecoli', Keyword="ECO")
        b = self.addthing(
            self.portal.bika_setup.bika_analysisservices, 'AnalysisService',
            title='Salmonella', Keyword="SAL")
        c = self.addthing(
            self.portal.bika_setup.bika_analysisservices, 'AnalysisService',
            title='Color', Keyword="COL")
        d = self.addthing(
            self.portal.bika_setup.bika_analysisservices, 'AnalysisService',
            title='Taste', Keyword="TAS")
        self.addthing(
            self.portal.bika_setup.bika_analysisprofiles, 'AnalysisProfile',
            title='MicroBio', Service=[a.UID(), b.UID()])
        self.addthing(
            self.portal.bika_setup.bika_analysisprofiles, 'AnalysisProfile',
            title='Properties', Service=[c.UID(), d.UID()])

    def tearDown(self):
        super(TestSampleImports, self).setUp()
        login(self.portal, TEST_USER_NAME)

    def test_complete_valid_batch_import(self):
        pc = getToolByName(self.portal, 'portal_catalog')
        workflow = getToolByName(self.portal, 'portal_workflow')
        client = self.portal.clients.objectValues()[0]
        sampleimport = self.addthing(client, 'SampleImport')
        sampleimport.unmarkCreationFlag()
        sampleimport.setFilename("test1.csv")
        # Fix double comma at TimeSampled should work without it.
        sampleimport.setOriginalFile("""
Header    ,Client name    ,Client ID       ,Contact
Header Data    ,Happy Hills    ,HH         ,Rita Mohale
Batch Header    ,title    ,description    ,ClientBatchID
Batch Data    ,New Batch  ,Optional descr   ,CC 201506
Samples    ,ClientSampleID ,DateSampled    ,TimeSampled ,Sampler  ,SamplePoint    ,SampleType ,SampleContainer ,ECO  ,SAL  ,COL  ,TAS   ,MicroBio ,Properties
"Sample 1"    ,HHS14001    ,3/9/2014       ,,            ,        ,  Toilet ,  Water    ,Cup             ,0    ,0    ,0    ,0     ,0        ,1
"Sample 2"    ,HHS14002    ,3/9/2014       ,,           ,         ,  Toilet ,  Water    ,Cup             ,0    ,0    ,0    ,0     ,1        ,1
"Sample 3"    ,HHS14002    ,3/9/2014       ,,            ,        ,  Toilet ,  Water    ,Cup             ,1    ,1    ,1    ,1     ,0        ,0
"Sample 4"    ,HHS14003    ,3/9/2014       ,,           ,         ,  Toilet ,  Water    ,Cup             ,1    ,0    ,0    ,0     ,1        ,0
        """)

        # check that values are saved without errors
        sampleimport.setErrors([])
        sampleimport.save_header_data()
        sampleimport.save_sample_data()
        sampleimport.create_or_reference_batch()
        errors = sampleimport.getErrors()
        if errors:
            self.fail("Unexpected errors while saving data: " + str(errors))
        # check that batch was created and linked to sampleimport without errors
        if not pc(portal_type='Batch'):
            self.fail("Batch was not created!")
        if not sampleimport.schema['Batch'].get(sampleimport):
            self.fail("Batch was created, but not linked to SampleImport.")

        # the workflow scripts use response.write(); silence them
        sampleimport.REQUEST.response.write = lambda x: x

        # check that validation succeeds without any errors
        workflow.doActionFor(sampleimport, 'validate')
        state = workflow.getInfoFor(sampleimport, 'review_state')
        if state != 'valid':
            errors = sampleimport.getErrors()
            self.fail(
                'Validation failed!  %s.Errors: %s' % (sampleimport.id, errors))

        # Import objects and verify that they exist
        workflow.doActionFor(sampleimport, 'import')
        state = workflow.getInfoFor(sampleimport, 'review_state')
        if state != 'imported':
            errors = sampleimport.getErrors()
            self.fail(
                'Importation failed!  %s.Errors: %s' % (sampleimport.id, errors))

        barc = getToolByName(self.portal, CATALOG_ANALYSIS_REQUEST_LISTING)
        samples = barc(portal_type='AnalysisRequest')
        if not samples[0].getObject().getContact():
            self.fail('No Contact imported into sample.Contact field.')
        sample_len = len(samples)
        if sample_len != 4:
            self.fail('4 AnalysisRequests were not created!  We found %s' % sample_len)
        bac = getToolByName(self.portal, CATALOG_ANALYSIS_LISTING)
        analyses = bac(portal_type='Analysis')
        sample_len = len(analyses)
        if sample_len != 12:
            self.fail('12 Analysis not found! We found %s' % l)
        states = [workflow.getInfoFor(a.getObject(), 'review_state')
                  for a in analyses]
        sample_states = [sample.review_state for sample in samples]
        if sample_states != ['sample_due'] * 4:
            self.fail('Samples states should all be sample_due, '
                      'but are not!')
        if states != ['registered'] * 12:
            self.fail('Analysis states should all be registered, but are not!')

    def test_LIMS_2080_correctly_interpret_false_and_blank_values(self):
        client = self.portal.clients.objectValues()[0]
        sampleimport = self.addthing(client, 'SampleImport')
        sampleimport.unmarkCreationFlag()
        sampleimport.setFilename("test1.csv")
        sampleimport.setOriginalFile("""
Header,      File name,  Client name,  Client ID, Contact,     CC Names - Report, CC Emails - Report, CC Names - Invoice, CC Emails - Invoice, No of Samples, Client Order Number, Client Reference,,
Header Data, test1.csv,  Happy Hills,  HH,        Rita Mohale,                  ,                   ,                    ,                    , 4,            HHPO-001,                            ,,
Samples,    ClientSampleID,    SamplingDate,DateSampled,SamplePoint,SampleMatrix,SampleType,ContainerType,ReportDryMatter,Priority,Total number of Analyses or Profiles,Price excl Tax,ECO,SAL,COL,TAS,MicroBio,Properties
"Total Analyses or Profiles",,,,,,,,,,,,,9,,,
"Sample 1", HHS14001,          3/9/2014,    3/9/2014,   ,     ,     Water,     Cup,          0,              Normal,  1,                                   0,             0,0,0,0,0,1
"Sample 2", HHS14002,          3/9/2014,    3/9/2014,   ,     ,     Water,     Cup,          0,              Normal,  2,                                   0,             0,0,0,0,1,1
"Sample 3", HHS14002,          3/9/2014,    3/9/2014,   Toilet,     Liquids,     Water,     Cup,          1,              Normal,  4,                                   0,             1,1,1,1,0,0
"Sample 4", HHS14002,          3/9/2014,    3/9/2014,   Toilet,     Liquids,     Water,     Cup,          1,              Normal,  2,                                   0,             1,0,0,0,1,0
        """)

        # check that values are saved without errors
        sampleimport.setErrors([])
        sampleimport.save_header_data()
        sampleimport.save_sample_data()
        errors = sampleimport.getErrors()
        if errors:
            self.fail("Unexpected errors while saving data: " + str(errors))
        transaction.commit()
        browser = self.getBrowser(
            username=TEST_USER_NAME,
            password=TEST_USER_PASSWORD,
            loggedIn=True)
        browser.addHeader("Accept-Language", "en-US")

        doActionFor(sampleimport, 'validate')
        c_state = getCurrentState(sampleimport)
        self.assertTrue(
            c_state == 'valid',
            "ARrimport in 'invalid' state after it has been transitioned to "
            "'valid'.")
        browser.open(sampleimport.absolute_url() + "/edit")
        content = browser.contents
        re.match(
            '<option selected=\"selected\" value=\"\d+\">Toilet</option>',
            content)
        if len(re.findall('<.*selected.*Toilet', content)) != 2:
            self.fail("Should be two empty SamplePoints, and two with values")

    def test_LIMS_2081_post_edit_fails_validation_gracefully(self):
        client = self.portal.clients.objectValues()[0]
        sampleimport = self.addthing(client, 'SampleImport')
        sampleimport.unmarkCreationFlag()
        sampleimport.setFilename("test1.csv")
        sampleimport.setOriginalFile("""
Header,      File name,  Client name,  Client ID, Contact,     CC Names - Report, CC Emails - Report, CC Names - Invoice, CC Emails - Invoice, No of Samples, Client Order Number, Client Reference,,
Header Data, test1.csv,  Happy Hills,  HH,        Rita Mohale,                  ,                   ,                    ,                    , 1,            HHPO-001,                            ,,
Samples,    ClientSampleID,    SamplingDate,DateSampled,SamplePoint,SampleMatrix,SampleType,ContainerType,ReportDryMatter,Priority,Total number of Analyses or Profiles,Price excl Tax,ECO,SAL,COL,TAS,MicroBio,Properties
"Total Analyses or Profiles",,,,,,,,,,,,,9,,,
"Sample 1", HHS14001,          3/9/2014,    3/9/2014,   ,     ,     Water,     Cup,          0,              Normal,  1,                                   0,             0,0,0,0,0,1
        """)

        # check that values are saved without errors
        sampleimport.setErrors([])
        sampleimport.save_header_data()
        sampleimport.save_sample_data()
        sampleimport.create_or_reference_batch()
        errors = sampleimport.getErrors()
        if errors:
            self.fail("Unexpected errors while saving data: " + str(errors))
        transaction.commit()
        browser = self.getBrowser(loggedIn=True)
        browser.addHeader("Accept-Language", "en-US")
        browser.open(sampleimport.absolute_url() + "/edit")
        browser.getControl(name="ClientReference").value = 'test_reference'
        browser.getControl(name="form.button.save").click()
        if 'test_reference' not in browser.contents:
            self.fail('Failed to modify SampleImport object (Client Reference)')

    def test_LIMS_206_brackets_throwoff_lookup(self):
        pc = getToolByName(self.portal, 'portal_catalog')
        workflow = getToolByName(self.portal, 'portal_workflow')
        client = self.portal.clients.objectValues()[0]
        sampleimport = self.addthing(client, 'SampleImport')
        sampleimport.unmarkCreationFlag()
        sampleimport.setFilename("test1.csv")
        sampleimport.setOriginalFile("""
Header    ,Client name    ,Client ID       ,Contact
Header Data    ,Happy Hills    ,HH         ,Rita Mohale
Batch Header    ,title    ,description    ,ClientBatchID
Batch Data    ,New Batch  ,Optional descr   ,CC 201506
Samples    ,ClientSampleID ,DateSampled    ,TimeSampled ,Sampler  ,SamplePoint    ,SampleType ,SampleContainer ,ECO  ,SAL  ,COL  ,TAS   ,MicroBio ,Properties
"Sample 1"    ,HHS14001    ,3/9/2014       ,,            ,        ,   (Land) of (Brackets) station                    ,  Water    ,Cup             ,0    ,0    ,0    ,0     ,0        ,1
"Sample 2"    ,HHS14002    ,3/9/2014       ,,           ,         ,   Bracketville (Centre)     ,  Water    ,Cup             ,0    ,0    ,0    ,0     ,1        ,1
"Sample 3"    ,HHS14002    ,3/9/2014       ,,            ,        ,   (Land) of (Brackets) station                    ,  Water    ,Cup             ,1    ,1    ,1    ,1     ,0        ,0
"Sample 4"    ,HHS14003    ,3/9/2014       ,,           ,         ,   Bracketville (Centre)     ,  Water    ,Cup             ,1    ,0    ,0    ,0     ,1        ,0
        """)

        # check that values are saved without errors
        sampleimport.setErrors([])
        sampleimport.save_header_data()
        sampleimport.save_sample_data()
        sampleimport.create_or_reference_batch()
        errors = sampleimport.getErrors()
        if errors:
            self.fail("Unexpected errors while saving data: " + str(errors))
        # the workflow scripts use response.write(); silence them
        sampleimport.REQUEST.response.write = lambda x: x
        barc = getToolByName(self.portal, CATALOG_ANALYSIS_REQUEST_LISTING)
        samples = barc(portal_type='AnalysisRequest')

        for samp in samples:
            if samp.getObject().getSamplePoint().title not in ["(Land) of (Brackets) station",'Bracketville (Centre)']:
                self.fail('Sample Point with Brackets not imported into Sample Point field')


def test_suite():
    suite = unittest.TestSuite()
    suite.addTest(unittest.makeSuite(TestSampleImports))
    return suite
