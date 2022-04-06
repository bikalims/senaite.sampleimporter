*Bulk sample importing add-on for SENAITE*
=====================================================

.. image:: https://img.shields.io/github/issues-pr/mikejmets/senaite.sampleimporter.svg?style=flat-square
   :target: https://github.com/mikejmets/senaite.sampleimporter/pulls

.. image:: https://img.shields.io/github/issues/mikejmets/senaite.sampleimporter.svg?style=flat-square
   :target: https://github.com/mikejmets/senaite.sampleimporter/issues

.. image:: https://img.shields.io/badge/README-GitHub-blue.svg?style=flat-square
   :target: https://github.com/mikejmets/senaite.sampleimporter#readme


Introduction
============

WARNING: This addon is not yet production ready and has not been released on PYPI


SENAITE SAMPLEIMPORTER adds **bulk sample importing** capabilities to `SENAITE LIMS <https://www.senaite.com>`_.


Usage
=====
Once installed you will find an Imports tab on a Client. Click in Imports and add a bulk sample import file.

A sample import template can be found `in the manual pages <https://www.bikalims.org/manual/batching/bulk-ar-import-from-spreadsheet>`_.

Once the file is loaded it automatically attempts to validate it's contents. If validation fails, the SampleImport will be in an Invalid state and you will see the validation errors at the bottom of the page. Fix the issue in the file and add the file again. If validation is successful the SampleImpot will be in a Valid state. In this case you can import the records by transitioning to a Imported state.

Note that previously one could edit the SampleImport if it had validation errors. This functionality may still work but it is no longer supported. Rather fix the input file and load it from scratch. This is especially true if you are importing sample fields that are not in core but have been added via an addon.


Installation
============

Please follow the installations sampleimporter for `Plone 4`_ and `senaite.lims`_.

To install SENAITE SAMPLEIMPORTER
list inside the `[buildout]` section of your `buildout.cfg`::

   [buildout]
   parts =
       instance
   extends =
       http://dist.plone.org/release/4.3.19/versions.cfg
   find-links =
       http://dist.plone.org/release/4.3.19
       http://dist.plone.org/thirdparty
   eggs =
       Plone
       Pillow
       senaite.lims
       senaite.sampleimporter
   zcml =
   eggs-directory = ${buildout:directory}/eggs

   [instance]
   recipe = plone.recipe.zope2instance
   user = admin:admin
   http-address = 0.0.0.0:8080
   eggs =
       ${buildout:eggs}
   zcml =
       ${buildout:zcml}

   [versions]
   setuptools =
   zc.buildout =


**Note**

The above example works for the buildout created by the unified
installer. If you however have a custom buildout you might need to add
the egg to the `eggs` list in the `[instance]` section rather than
adding it in the `[buildout]` section.

Also see this section of the Plone documentation for further details:
https://docs.plone.org/4/en/manage/installing/installing_addons.html

**Important**

For the changes to take effect you need to re-run buildout from your
console::

   bin/buildout


Installation Requirements
-------------------------

The following versions are required for SENAITE SAMPLEIMPORTER

-  Plone 4.3.19
-  senaite.lims >= 1.3.0


Activate the Add-on
-------------------

Please browse to the *Add-ons* Controlpanel and activate the **SENAITE SAMPLEIMPORTER** Add-on:

.. image:: static/activate_addon.png
    :alt: Activate SENAITE SAMPLEIMPORTER Add-on

Contribute
==========

We want contributing to SENAITE.SAMPLEIMPORTER to be fun, enjoyable, and educational
for anyone, and everyone. This project adheres to the `Contributor Covenant
<https://github.com/mikejmets/senaite.sampleimporter/blob/master/CODE_OF_CONDUCT.md>`_.

By participating, you are expected to uphold this code. Please report
unacceptable behavior.

Contributions go far beyond pull requests and commits. Although we love giving
you the opportunity to put your stamp on SENAITE.SAMPLEIMPORTER, we also are thrilled
to receive a variety of other contributions.

Please, read `Contributing to senaite.sampleimporter document
<https://github.com/mikejmets/senaite.sampleimporter/blob/master/CONTRIBUTING.md>`_.


User manual
===========
 `Community site Batch Sample Import <https://www.bikalims.org/manual/batching/bulk-ar-import-from-spreadsheet>`_

Feedback and support
====================

* `Community site <https://community.senaite.org/>`_
* `Gitter channel <https://gitter.im/senaite/Lobby>`_
* `Users list <https://sourceforge.net/projects/senaite/lists/senaite-users>`_


License
=======

**SENAITE.SAMPLEIMPORTER** Copyright (C) 2019 Senaite Foundation

This program is free software; you can redistribute it and/or modify it under
the terms of the `GNU General Public License version 2
<https://github.com/mikejmets/senaite.sampleimporter/blob/master/LICENSE>`_ as published
by the Free Software Foundation.

This program is distributed in the hope that it will be useful,
but WITHOUT ANY WARRANTY; without even the implied warranty of
MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE. See the
GNU General Public License for more details.
