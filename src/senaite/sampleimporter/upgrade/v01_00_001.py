# -*- coding: utf-8 -*-
#
# This file is part of SENAITE.SAMPLEIMPORTER.
#
# SENAITE.CORE.LISTING is free software: you can redistribute it and/or modify
# it under the terms of the GNU General Public License as published by the Free
# Software Foundation, version 2.
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
# Copyright 2019 by it's authors.
# Some rights reserved, see README and LICENSE.

from senaite.core.upgrade import upgradestep
from senaite.sampleimporter import PRODUCT_NAME
from senaite.sampleimporter import logger
from senaite.sampleimporter import PROJECTNAME as product

version = "1.0.1"
profile = "profile-{0}:default".format(product)

@upgradestep(PRODUCT_NAME, version)
def upgrade(tool):
    portal = tool.aq_inner.aq_parent
    setup = portal.portal_setup
    setup.runImportStepFromProfile(profile, "workflow")
    logger.info("{0} upgraded to version {1}".format(PRODUCT_NAME, version))
    return True
