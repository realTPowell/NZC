# -*- coding: utf-8 -*-
"""
Module handling interventions and intervention plans
"""

import pandas as pd
import ReferenceData as data
from typing import List, Callable, Tuple
from itertools import chain
from Schemas import Asset_Data, Asset_Data_Sortable, Intervention_Data, Rollout_Data
import pathwayFunctions as path

idx = pd.IndexSlice

intervention_constructors = {'Monitoring & Targeting': 'Efficiency',
                             'Smart Thermostats': 'Efficiency',
                             'BMS Set Point Optimisation': 'Efficiency',
                             'Localised Heating / Cooling Controls': 'Efficiency',
                             'LED Lighting': 'Efficiency',
                             'Lighting Occupancy Sensor': 'Efficiency',
                             'Daylighting Control': 'Efficiency',
                             'External Wall Insulation': 'Efficiency',
                             'Cavity Wall Insulation': 'Efficiency',
                             'Floor Insulation': 'Efficiency',
                             'Roof Insulation': 'Efficiency',
                             'Double Glazing': 'Efficiency',
                             'Heat Pump': 'Relative Reassignment',
                             'Heat Pump - Renewable Power': 'Relative Reassignment'}


class Model:
    @staticmethod
    def compute_CRREM_pathways(consumption_pathway, asset_data):
        energy = consumption_pathway.groupby('UID').sum()

        emissions = path.carbon_conversion(consumption_pathway, asset_data)

        CRREM_pathways = (pd.concat([energy, emissions],
                                    keys=['kWh-Int', 'GHG-Int'],
                                    names=['Pathway Code'])
                          .reorder_levels([1, 0])
                          .sort_index()
                          )
        return CRREM_pathways

    def __init__(self, asset_data, con_data, base_year=2020):
        """
        Using the input data, the basic calculations are done, and the BAU Consumption
        is stored to the instance, as well as a dataframe of pathways in the BAU and CRREM target
        scenarios.
        """
        self.scenarios = None
        self.base_year = base_year

        self.asset_data = asset_data
        self.BAU_Consumption = path.forecast_BAU_Consumption(asset_data, con_data)
        self.BAU_Pathways = Model.compute_CRREM_pathways(self.BAU_Consumption, asset_data)
        self.CRREM_Targets = data.pathways.get_data(asset_data)

    def scenarios_from_df(self, interventions_df: Intervention_Data, rollouts_df: Rollout_Data):
        scenario_names = (pd.concat([interventions_df['Scenario'], rollouts_df['Scenario']])
                          .unique()
                          .tolist()
                          )
        scenarios = []

        for name in scenario_names:
            scenarios.append(Scenario.from_df(name,
                                              interventions_df[interventions_df['Scenario'] == name],
                                              rollouts_df[rollouts_df['Scenario'] == name],
                                              self)
                             )

        self.scenarios = scenarios

    def apply_interventions(self, scenarios):
        all_names = ["BAU", "Target"]
        scenario_names = []
        scenario_pathways = [self.BAU_Pathways, self.CRREM_Targets]
        scenario_consumptions = []
        scenario_impacts = []

        split_consumption = path.split_pathway(self.asset_data, self.BAU_Consumption)

        for scenario in scenarios:
            scenario_names.append(scenario.name)
            consumption_copy = split_consumption.copy()
            scenario_data = (scenario(consumption_copy).groupby(['UID', 'Utility'])
                             .sum()
                             )

            new_pathway = Model.compute_CRREM_pathways(scenario_data, self.asset_data)

            scenario_consumptions.append(scenario_data)
            scenario_pathways.append(new_pathway)
            scenario_impacts.append(scenario.impact_log)

        all_names.extend(scenario_names)
        self.scenario_consumption_data = pd.concat(scenario_consumptions, keys=scenario_names, names=['Scenario'])
        self.scenario_impact_data = pd.concat(scenario_impacts, keys=scenario_names, names=['Scenario'])
        return pd.concat(scenario_pathways, keys=all_names, names=['Scenario'])


class Intervention:
    # TODO Implement costs
    def __init__(self, target: str, year: int, intervention_type: str, model: Model):
        self.impact_log = None
        self.target = target
        self.year = year
        self.intervention_type = intervention_type
        self.asset_info = model.asset_data[model.asset_data['UID'] == target]
        self.BAU_data = model.BAU_Consumption.loc[target, year]

    def effect(self):
        if intervention_constructors[self.intervention_type] == 'Efficiency':
            return EfficiencyEffect(self)
        elif intervention_constructors[self.intervention_type] == 'Relative Reassignment':
            return RelativeReassignment(self)

    def act(self, df: pd.DataFrame):
        result = df.copy().fillna(0)
        result.loc[self.target, result.columns >= self.year] = (result.loc[self.target, df.columns >= self.year]
                                                                .apply(self.effect())
                                                                .values
                                                                )

        info = pd.Series([self.target, self.year, self.intervention_type, 0], index=['Target', 'Year', 'Type', 'Cost'])
        impact = ((result.loc[self.target, self.year] - df.loc[self.target, self.year])
                  .groupby('Utility')
                  .sum()
                  )

        self.impact_log = pd.concat([info, impact], axis=0)
        return result

    __call__ = act


def EfficiencyEffect(intervention: Intervention):
    # TODO Add exception handling when the intervention type cannot be handle by this constructor

    # TODO use a configured data object for this
    effect_coeffs = 1 - data.efficiency_parameters[intervention.intervention_type]

    return lambda x: effect_coeffs.multiply(x)


def RelativeReassignment(intervention: Intervention):
    # TODO Add exception handling when the intervention type cannot be handle by this constructor

    # TODO use a configured data object for this
    effect_coeffs = data.reassignment_parameters.reset_index()[
        data.reassignment_parameters['Type'] == intervention.intervention_type]

    def reassignment_effect(df):
        for _, row in effect_coeffs.iterrows():
            df.loc[(row.ToUtility, row.ToUse)] = df.loc[(row.FromUtility, row.FromUse)] / row.CoP
            df.loc[(row.FromUtility, row.FromUse)] = 0
        return df

    return reassignment_effect


class Rollout:
    def __init__(self, intervention_type, start_year, count_per_year, model: Model,
                 country_scope: str = '-', sector_scope: str = '-'):

        # NB for now, to facilitate easier read-in from df data, countries can only be specified one at a time;
        # may wish in future to allow list input for easier config, but will require semi-structured data input
        # also this is a dodgy fix to allow read-in from excel

        asset_data = model.asset_data

        country_filter = asset_data['Country Code'].unique().tolist() if country_scope == '-' else [country_scope]
        sector_filter = asset_data['Sector Code'].unique().tolist() if sector_scope == '-' else [sector_scope]

        mask = ((asset_data['Country Code'].isin(country_filter))
                & (asset_data['Sector Code'].isin(sector_filter)))

        intensities = (model.BAU_Pathways.loc[idx[:, 'kWh-Int'], model.base_year]
                       .reset_index()
                       .drop(columns=['Pathway Code'])
                       .set_index('UID')
                       .rename(columns={2020: 'Intensities'}))

        sortable_assets = asset_data.merge(intensities, left_on='UID', right_index=True)

        self.targets = sortable_assets[mask].sort_values('Intensities')['UID'].tolist()
        self.type = intervention_type
        self.start_year = start_year
        self.rate = count_per_year
        self.model = model

    def unpack(self) -> List[Intervention]:
        # TODO: dreadful code, nesting is way too deep, fix this
        # Fix may involve a generator?

        intervention_list = []
        year = self.start_year
        checklist = self.targets
        while len(checklist) > 0:
            for i in range(self.rate):
                try:
                    target = checklist.pop()
                except IndexError:
                    return intervention_list
                intervention_list.append(Intervention(target, year, self.type, self.model))
            year += 1
        return intervention_list


class Scenario:
    def __init__(self, name: str, interventions: List[Intervention], rollouts: List[Rollout] = []):
        self.impact_log = None
        self.name = name
        self.intervention_list = interventions
        if len(rollouts) > 0:
            rollout_contents = chain(*[rollout.unpack() for rollout in rollouts])
            self.intervention_list.extend(rollout_contents)
        self.intervention_list.sort(key=lambda x: x.year)

    @classmethod
    def from_df(cls, name: str, interventions_df: Intervention_Data, rollouts_df: Rollout_Data, model: Model):

        interventions = []
        rollouts = []
        for _, row in interventions_df.iterrows():
            interventions.append(Intervention(row['Target'], row['Year'], row['Type'], model))

        for _, row in rollouts_df.iterrows():
            rollouts.append(Rollout(row['Type'], row['Start'], row['Installations per year'],
                                    model, country_scope=row['Country Scope'], sector_scope=row['Sector Scope']))

        return Scenario(name, interventions, rollouts)

    def act(self, df: pd.DataFrame):
        result = df.copy()
        log_list = []
        for intervention in self.intervention_list:
            result = intervention(result)
            log_list.append(intervention.impact_log)
        self.impact_log = pd.DataFrame(log_list)
        return result

    __call__ = act
