# -*- coding: utf-8 -*-
"""
Defines Typed DataFrame schemas used throughout
"""

import pandas as pd
from typedframe import TypedDataFrame


class Asset_Data(TypedDataFrame):
    schema = {
        'UID': str,
        'Name': str,
        'Sector Code': str,
        'Country Code': str,
        'Area': float,
        }
    
class Asset_Data_Sortable(Asset_Data):
    schema = {
        'Intensities': float
        }
    #This might not always be an intensities column in future use cases?
    
class Intervention_Data(TypedDataFrame):
    schema = {
        'Target': str,
        'Year': int,
        'Type': str
        }
    
class Rollout_Data(TypedDataFrame):
    schema = {
        'Intervention Type': str,
        'Start Year': int,
        'Count per Year': int,
        'Country Scope': str,
        'Sector Scope': str
        }
    
    
