# -*- coding: utf-8 -*-
#
# This file is part of SENAITE.SAMPLEIMPORTER
#
# Copyright 2019 by it's authors

from setuptools import setup, find_packages

version = "1.0.1"

setup(
    name="senaite.sampleimporter",
    version=version,
    description="AR importing add-on for SENAITE",
    long_description=open("README.rst").read(),
    # long_description_content_type="text/markdown",
    # Get more strings from
    # http://pypi.python.org/pypi?:action=list_classifiers
    classifiers=[
        "Framework :: Plone",
        "Framework :: Zope2",
        "Programming Language :: Python",
        "License :: OSI Approved :: GNU General Public License v2 (GPLv2)",
    ],
    keywords=['senaite', 'lims', 'opensource'],
    author="SENAITE Foundation",
    author_email="support@senaite.com",
    url="https://github.com/senaite/senaite.sampleimporter",
    license="GPLv2",
    packages=find_packages("src", exclude=["ez_setup"]),
    package_dir={"": "src"},
    namespace_packages=["senaite"],
    include_package_data=True,
    zip_safe=False,
    install_requires=[
        "setuptools",
        "senaite.lims>=2.0.0",
        "senaite.app.supermodel>=2.0.0",
        "plone.formwidget.contenttree",
        "plone.app.relationfield",
        "collective.z3cform.datagridfield",
    ],
    extras_require={
        "test": [
            "Products.PloneTestCase",
            "Products.SecureMailHost",
            "plone.app.testing",
            "unittest2",
        ]
    },
    entry_points="""
      # -*- Entry points: -*-
      [z3c.autoinclude.plugin]
      target = plone
      """,
)
