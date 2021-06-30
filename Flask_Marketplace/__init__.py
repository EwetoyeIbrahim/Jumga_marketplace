"""
Flask-Market is an modular ecommerce flask app.
It can either be used as standalone or as extension to provide marketplace
features to existing flask applications.

Author: Ewetoye Ibrahim
"""

__author__ = 'Ewetoye Ibrahim'
__version__ = '1.1.1-alpha'

import os, sys
sys.path.append(os.path.dirname(__file__))
from Flask_Marketplace.views import MarketViews
from .factory import marketplace

