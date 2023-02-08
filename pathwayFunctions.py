# -*- coding: utf-8 -*-
"""
Core functions for acting on pathway dataframes
May ultimately become a custom accessor to dataframes
"""

import pandas as pd
import ReferenceData as data
from Schemas import Asset_Data


def fill_to_horizon(consumptions, horizon=2050):
    """
    Fill out BAU forecasts with last year of actual data.
    This forward inference could be smarter, eg use a rolling average to keep more than one year's data involved
    """
    year = consumptions.columns.max()  # initialise to last year within actual data
    while year < horizon:
        consumptions[year + 1] = consumptions[year].copy()
        year += 1

    return consumptions


def forecast_BAU_Consumption(asset_data, con_data, horizon=2050):
    """
    Uses an asset info df and consumption data for those assets in record form
    to return pathways for annual consumption out to the horizon, by pivoting
    the record-form consumption data appropriately
    """
    asset_con_data = con_data[con_data['UID'].isin(asset_data['UID'])]
    BAU_Consumption = (asset_con_data.pivot(index=['UID', 'Utility'], columns='Year', values='Consumption')
                                       .pipe(fill_to_horizon, horizon)
                       )
    return BAU_Consumption


def attach_asset_data(pathways: pd.DataFrame, asset_data: pd.DataFrame, columns: list):
    """
    Takes a pathway (defined as having UID on level 0 of index, and years on outside
    of columns) and attaches requested columns of info from the asset info dataframe for filtering,
    lookups etc
    """
    columns.append('UID')
    with_data = (pathways.copy()
                         .reset_index()
                         .merge(asset_data[columns], left_on='UID', right_on='UID')
                         .set_index(pathways.index.names)
                 )
    return with_data


def carbon_conversion(pathways, asset_data: Asset_Data):
    """
    Gets appropriate dataframe of emissions factors, and converts a frame of consumption pathways
    to the corresponding carbon pathways
    """
    factors = data.factors.get_data(asset_data)

    # Apply factors and sum to get BAU Emissions
    carbon = pathways * factors
    emissions = (carbon.dropna(axis=1, how='all')
                 .groupby(['UID'])  # don't like this hard-coded groupby
                 .sum()
                 )
    return emissions


def get_pathways(asset_data):
    """
    Gets the CRREM pathways of the requested type for the passed assets. For dimensional
    reasons, the *budgets* are returned so that aggregation and normalisation works
    as for the other scenarios
    """
    pathways = (asset_data[['UID', 'Country Code', 'Sector Code', 'Area']]
                .merge(data.pathways.reset_index(),
                       left_on=['Sector Code', 'Country Code'],
                       right_on=['Sector Code', 'Country Code'])
                .drop(columns=['Country Code', 'Sector Code'])
                .set_index(['UID', 'Pathway Code'])
                .sort_index()
                )
    budgets = (pathways.multiply(pathways['Area'], axis=0)
               .drop(columns=['Area'])
               )
    return budgets


def split_pathway(asset_data: Asset_Data, consumption_pathway):
    split_df = consumption_pathway.multiply(data.splits.get_data(asset_data), axis=0)
    return split_df


def normalise(pathway):
    """
    Divides the columns of a pathway by its area column and then drops the areas,
    if such a column exists
    """
    if 'Area' in pathway.columns.to_list():
        normalised = (pathway.div(pathway['Area'], axis=0)
                      .drop(columns=['Area'])
                      )
        return normalised
    else:
        print(f"{pathway} does not have an 'Area' column")


def denormalise(pathway):
    """
    Multiplies the columns of a pathway by its area column and then drops the areas,
    if such a column exists
    """
    if 'Area' in pathway.columns.to_list():
        normalised = (pathway.multiply(pathway['Area'], axis=0)
                      .drop(columns=['Area'])
                      )
        return normalised
    else:
        print(f"{pathway} does not have an 'Area' column")
