# -*- coding: utf-8 -*-
"""Focused CSV and reference regressions, without a running Plone site."""
import unittest

from Products.PluginIndexes.FieldIndex.FieldIndex import FieldIndex
from Products.PluginIndexes.PathIndex.PathIndex import PathIndex
from Products.ZCatalog.ZCatalog import ZCatalog
from zope.interface import alsoProvides

from senaite.sampleimporter.content import sampleimport as module


def method(name):
    value = getattr(module.SampleImport, name)
    return getattr(value, "im_func", value)


class Importer(object):
    get_sample_values = method("get_sample_values")
    munge_field_value = method("munge_field_value")
    validate_against_schema = method("validate_against_schema")
    lookup = method("lookup")
    save_sample_data = method("save_sample_data")

    def get_samplepoint_paths(self):
        return ["/site/clients/environmental", "/site/setup/samplepoints"]

    def getOriginalFile(self):
        return self


class Field(object):
    type = "uidreference"
    allowed_types = ("SamplePoint",)
    multiValued = False
    required = False


class Brain(object):
    UID = "sample-point-uid"


class TestSamplePointValues(unittest.TestCase):
    def setUp(self):
        self.importer = Importer()
        self.schema = {"SamplePoint": Field()}

    def parse(self, data):
        self.importer.data = data
        return dict(self.importer.get_sample_values()["samples"][0])

    def test_samplepoint_in_fourth_column_without_time(self):
        row = self.parse("Samples,ClientSampleID,DateSampled,SamplePoint,SampleType\n"
                         "Sample 1,ID1,2026-09-07,Bracketville (Centre),Water")
        self.assertEqual(row["SamplePoint"], "Bracketville (Centre)")
        self.assertEqual(row["SampleType"], "Water")

    def test_time_column_is_trimmed_and_matched_by_name(self):
        row = self.parse("Samples,SamplePoint, TimeSampled ,DateSampled,SampleType\n"
                         "Sample 1,Toilet,10:30,2026-09-07,Water")
        self.assertEqual(row["SamplePoint"], "Toilet")
        self.assertEqual(row["DateSampled"], "2026-09-07 10:30")
        self.assertNotIn("TimeSampled", row)

    def test_short_rows_do_not_require_a_fourth_column(self):
        row = self.parse("Samples,SamplePoint\nSample 1,A")
        self.assertEqual(row["SamplePoint"], "A")

    def test_existing_one_character_title_resolves_to_uid(self):
        self.importer.lookup = lambda *args, **kw: [Brain()] if kw == {"title": "A"} else []
        uid = self.importer.munge_field_value(self.schema, 1, "SamplePoint", "A")
        self.assertEqual(uid, Brain.UID)

    def test_missing_point_reports_row_field_and_value(self):
        self.importer.lookup = lambda *args, **kw: []
        with self.assertRaises(ValueError) as error:
            self.importer.munge_field_value(self.schema, 2, "SamplePoint", "Missing")
        self.assertIn("Row 2", str(error.exception))
        self.assertIn("SamplePoint=Missing", str(error.exception))

    def test_uid_is_accepted_when_title_does_not_match(self):
        self.importer.lookup = lambda *args, **kw: [Brain()] if kw == {"UID": Brain.UID} else []
        self.assertEqual(self.importer.munge_field_value(
            self.schema, 1, "SamplePoint", Brain.UID), Brain.UID)

    def test_unresolved_uid_fails_validation(self):
        self.importer.lookup = lambda *args, **kw: []
        with self.assertRaises(ValueError):
            self.importer.validate_against_schema(self.schema, 1, "SamplePoint", "missing-uid")

    def test_blank_optional_samplepoint_is_valid(self):
        self.assertEqual(self.importer.validate_against_schema(
            self.schema, 1, "SamplePoint", ""), "")

    def test_missing_csv_samplepoint_is_reported_when_saving(self):
        importer = self.importer
        importer.data = ("Samples,ClientSampleID,DateSampled,SamplePoint,SampleType\n"
                         "Sample 1,ID1,2026-09-07,Missing,Water")
        importer.get_ar_schema = lambda: self.schema
        importer.lookup = lambda *args, **kw: []
        errors = []
        rows = []
        importer.error = errors.append
        importer.setSampleData = rows.extend
        class CountField(object):
            def set(self, context, value):
                pass
        importer.schema = {"NrSamples": CountField()}
        class Catalog(object):
            def uniqueValuesFor(self, name):
                return []
            def __call__(self, **query):
                return []
        original = module.api.get_tool
        module.api.get_tool = lambda name: Catalog()
        try:
            importer.save_sample_data()
        finally:
            module.api.get_tool = original
        self.assertEqual(errors, [
            "Row 1: value is invalid (SamplePoint=Missing)"])
        self.assertNotIn("SamplePoint", rows[0])

    def test_lookup_uses_registered_catalogs_and_literal_title(self):
        queries = []
        types = []
        def catalog(**query):
            queries.append(query)
            return [Brain()]
        def get_catalogs(portal_type):
            types.append(portal_type)
            return [catalog]
        original = module.api.get_catalogs_for
        module.api.get_catalogs_for = get_catalogs
        try:
            title = '(Land) of (Brackets) station'
            result = self.importer.lookup(("SamplePoint",), title=title)
            self.assertEqual(result[0].UID, Brain.UID)
            self.assertEqual(types, ["SamplePoint"])
            self.assertEqual(queries, [{
                "portal_type": "SamplePoint", "title": title,
                "is_active": True,
                "path": {"query": "/site/clients/environmental"}}])
        finally:
            module.api.get_catalogs_for = original

    def test_lookup_checks_additional_registered_catalogs(self):
        original = module.api.get_catalogs_for
        module.api.get_catalogs_for = lambda portal_type: [
            lambda **query: [], lambda **query: [Brain()]]
        try:
            result = self.importer.lookup(("SamplePoint",), title="KML01")
            self.assertEqual(result[0].UID, Brain.UID)
        finally:
            module.api.get_catalogs_for = original

    def test_current_client_takes_precedence_over_shared_samplepoint(self):
        calls = []
        client_point = Brain()
        client_point.UID = 'environmental-kml01'
        shared_point = Brain()
        shared_point.UID = 'shared-kml01'
        def catalog(**query):
            calls.append(query)
            if query.get('path') == {'query': '/site/clients/environmental'}:
                return [client_point]
            return [shared_point, client_point]
        original = module.api.get_catalogs_for
        module.api.get_catalogs_for = lambda portal_type: [catalog]
        try:
            uid = self.importer.munge_field_value(
                self.schema, 1, 'SamplePoint', 'KML01')
            self.assertEqual(uid, client_point.UID)
            self.assertEqual(len(calls), 1)
        finally:
            module.api.get_catalogs_for = original

    def test_shared_samplepoint_is_fallback(self):
        def catalog(**query):
            if query.get('path') == {'query': '/site/setup/samplepoints'}:
                return [Brain()]
            return []
        original = module.api.get_catalogs_for
        module.api.get_catalogs_for = lambda portal_type: [catalog]
        try:
            result = self.importer.lookup(('SamplePoint',), title='KML01')
            self.assertEqual(result[0].UID, Brain.UID)
        finally:
            module.api.get_catalogs_for = original

    def test_another_clients_point_is_not_accepted_by_title_or_uid(self):
        def catalog(**query):
            if query.get('path') == {'query': '/site/clients/other'}:
                return [Brain()]
            return []
        original = module.api.get_catalogs_for
        module.api.get_catalogs_for = lambda portal_type: [catalog]
        try:
            with self.assertRaises(ValueError):
                self.importer.munge_field_value(
                    self.schema, 1, 'SamplePoint', 'KML01')
            with self.assertRaises(ValueError):
                self.importer.validate_against_schema(
                    self.schema, 1, 'SamplePoint', Brain.UID)
        finally:
            module.api.get_catalogs_for = original


class CatalogPoint(object):
    portal_type = 'SamplePoint'

    def __init__(self, title, uid, path, active=True):
        self.title = title
        self.UID = uid
        self.path = path
        self.is_active = active

    def getPhysicalPath(self):
        return tuple(self.path.split('/'))


class TestSamplePointCatalogLookup(unittest.TestCase):
    """Exercise real catalog filters with client and global Sample Points."""

    def setUp(self):
        self.catalog = ZCatalog('samplepoints')
        for name in ('portal_type', 'title', 'UID', 'is_active'):
            self.catalog._catalog.addIndex(name, FieldIndex(name))
        self.catalog._catalog.addIndex('path', PathIndex('path'))
        self.catalog.addColumn('UID')
        self.importer = Importer()
        self.schema = {'SamplePoint': Field()}
        client = CatalogPoint('', '', '/site/clients/environmental')
        alsoProvides(client, module.IClient)
        self.importer.aq_parent = client
        setup = CatalogPoint('', '', '/site/setup')
        setup.samplepoints = CatalogPoint('', '', '/site/setup/samplepoints')
        self.original_catalogs = module.api.get_catalogs_for
        self.original_setup = module.api.get_senaite_setup
        module.api.get_catalogs_for = lambda portal_type: [self.catalog]
        module.api.get_senaite_setup = lambda: setup
        self.addCleanup(self.restore_api)
        # Use the production path builder, including client interface detection.
        self.importer.get_samplepoint_paths = lambda: method(
            'get_samplepoint_paths')(self.importer)

    def restore_api(self):
        module.api.get_catalogs_for = self.original_catalogs
        module.api.get_senaite_setup = self.original_setup

    def add_point(self, title, uid, folder, active=True):
        path = folder + '/' + uid
        point = CatalogPoint(title, uid, path, active)
        self.catalog.catalog_object(point, path)
        return point

    def resolve(self, value):
        return self.importer.munge_field_value(
            self.schema, 28, 'SamplePoint', value)

    def test_global_samplepoint_resolves_by_title_and_uid(self):
        point = self.add_point('Global Well', 'global-well',
                               '/site/setup/samplepoints')
        self.assertEqual(self.resolve(point.title), point.UID)
        self.assertEqual(self.resolve(point.UID), point.UID)

    def test_client_samplepoint_resolves_by_title_and_uid(self):
        point = self.add_point('Client Well', 'client-well',
                               '/site/clients/environmental')
        self.assertEqual(self.resolve(point.title), point.UID)
        self.assertEqual(self.resolve(point.UID), point.UID)

    def test_client_samplepoint_under_a_location_resolves(self):
        point = self.add_point('Nested Well', 'nested-well',
                               '/site/clients/environmental/location-1')
        self.assertEqual(self.resolve(point.title), point.UID)

    def test_client_duplicate_wins_even_if_global_was_indexed_first(self):
        self.add_point('KML01', 'global-kml01', '/site/setup/samplepoints')
        client = self.add_point('KML01', 'client-kml01',
                                '/site/clients/environmental')
        self.add_point('KML01', 'other-kml01', '/site/clients/other')
        self.assertEqual(self.resolve('KML01'), client.UID)

    def test_other_clients_point_is_rejected_by_title_and_uid(self):
        point = self.add_point('Other Well', 'other-well', '/site/clients/other')
        for value in (point.title, point.UID):
            with self.assertRaises(ValueError):
                self.resolve(value)

    def test_inactive_global_and_client_points_are_rejected(self):
        for folder in ('/site/setup/samplepoints',
                       '/site/clients/environmental'):
            point = self.add_point('VBH2', 'inactive-' + folder.split('/')[-1],
                                   folder, active=False)
            with self.assertRaises(ValueError) as error:
                self.resolve('VBH2')
            self.assertEqual(str(error.exception),
                             'Row 28: value is invalid (SamplePoint=VBH2)')
            with self.assertRaises(ValueError):
                self.resolve(point.UID)

    def test_saved_global_and_client_uids_pass_validation(self):
        for folder in ('/site/setup/samplepoints',
                       '/site/clients/environmental'):
            point = self.add_point('Well', 'well-' + folder.split('/')[-1],
                                   folder)
            self.assertEqual(self.importer.validate_against_schema(
                self.schema, 1, 'SamplePoint', point.UID), point.UID)


if __name__ == "__main__":
    unittest.main()
