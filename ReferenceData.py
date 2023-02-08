# -*- coding: utf-8 -*-
"""
Establishes classes to handle lookups against default parameters which may be
customised, then uses these to create instances contained configured data for
the reference parameters used throughout the model
"""
import pandas as pd
from abc import ABC, abstractmethod
from Schemas import Asset_Data

sparse = pd.SparseDtype(float,fill_value=0)

class Default_Data(ABC):
    @abstractmethod
    def get_defaults(self, assets: Asset_Data) -> pd.DataFrame:
        '''
        Should take a dataframe of asset data and return the appropriate frame of parameters
        '''
        pass

class Configured_Data:
    def __init__(self, default: Default_Data, custom_data: pd.DataFrame = None):
        '''
        Stores a Default_Data store, and a dataframe of custom values to override with
        '''
        self.default = default
        self.custom = custom_data
        
        
    def get_data(self, assets: Asset_Data) -> pd.DataFrame:
        '''
        Gets the default data, then overwrites it with custom data wherever specified
        '''
        df = self.default.get_defaults(assets)
        if self.custom == None:
            return df
        df.loc[df.index.intersection(self.custom.index)]=self.custom
        return df
        
class Default_Pathways(Default_Data):
    def __init__(self,filepath):
        self.default = pd.concat([pd.read_excel(filepath,
                                            sheet_name=sheetname,
                                            index_col=[2, 1,0]) 
                                  for sheetname in ["GHG Pathways", "CO2 Pathways", "Energy Pathways"]])
    
    def get_defaults(self, assets: Asset_Data,) -> pd.DataFrame:   
        CRREM_Pathways = self.default
        
        pathways = (assets[['UID','Country Code','Sector Code','Area']]
                               .merge(CRREM_Pathways.reset_index(),
                                      left_on=['Sector Code','Country Code'],
                                      right_on=['Sector Code','Country Code'])
                               .drop(columns=['Country Code','Sector Code'])
                               .set_index(['UID','Pathway Code'])
                               .sort_index()
                               )
        
        budgets = (pathways.multiply(pathways['Area'],axis=0)
                            .drop(columns=['Area'])
                    )
        
        return budgets

class Default_Splits(Default_Data):
    def __init__(self,filepath):
        self.default = (pd.read_excel(filepath,
                                      sheet_name='Energy Splits',
                                      index_col=[0,1])
                             .sort_index())
    
    def get_defaults(self, assets: Asset_Data) -> pd.DataFrame:
        splits = pd.concat([self.default[assets.loc[assets['UID']==asset,'Sector Code']].squeeze() for asset in assets['UID']],
                              keys = assets['UID'],
                              names=['UID'])
        return splits

class Default_Factors(Default_Data):
    def __init__(self,filepath):
        utilities = ["Elec Emissions Factors", "DH&C Emissions Factors", "Gas Emissions Factors"]
        self.default = pd.concat([pd.read_excel(filepath,
                                           sheet_name=sheetname,
                                           index_col=[1,0])
                             for sheetname in utilities])
    
    def get_defaults(self, assets: Asset_Data) -> pd.DataFrame:
        factors = (assets[['UID','Country Code']]
                           .merge(self.default.reset_index(), left_on='Country Code', right_on='Country Code')
                           .drop(columns=['Country Code'])
                           .set_index(['UID','Utility'])
                   )
        return factors

#%% Data set-up 

default_factors = Default_Factors('Reference Data/Emissions Factors.xlsx')
factors = Configured_Data(default_factors)

default_pathways = Default_Pathways('Reference Data/Pathways.xlsx')
pathways = Configured_Data(default_pathways)

default_splits = Default_Splits('Reference Data/Intervention Parameters.xlsx')
splits = Configured_Data(default_splits)

efficiency_parameters = (pd.read_excel('Reference Data/Intervention Parameters.xlsx',
                              sheet_name='Efficiency Interventions',
                              index_col=[0,1])
                           .sort_index())

utility_use = efficiency_parameters.index

reassignment_parameters = (pd.read_excel('Reference Data/Intervention Parameters.xlsx',
                              sheet_name='Reassignment Interventions')
                           )


#%% Legacy code to be converted

# #--- Define conversion tables for readable versions of codes ---
# sector_codes = pd.DataFrame([['RSF','Residential - Single Family'],
#                              ['RMF','Residential - Multi Family'],
#                              ['OFF','Offices'],
#                              ['RHS','Retail - High Street'],
#                              ['RSC','Retail - Shopping Centre'],
#                              ['RWB','Retail - Warehouse Building'],
#                              ['HOT','Hotel'],
#                              ['DWC','Industrial Warehouse - Cold'],
#                              ['DWW','Industrial Warehouse - Warm'],
#                              ['HEC','Healthcare'],
#                              ['LEI','Leisure, Lodges etc.'],
#                              ['Resi','Residential']],
#                             columns=['Code','Name']).set_index('Code')

# #--- Import default intervention parameters, and process to effect matrices ---






