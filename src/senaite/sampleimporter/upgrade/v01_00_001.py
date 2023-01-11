# -*- coding: utf-8 -*-

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
