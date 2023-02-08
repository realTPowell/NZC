"""
First version of Dash app, adding interactivity to the process seen in Modeller.py
"""
# Package imports
import numpy as np
import pandas as pd
import plotly.express as px
from dash import Dash, dcc, html, Input, Output
import dash_bootstrap_components as dbc

idx = pd.IndexSlice

# custom modules
import pathwayFunctions as path
from ReferenceData import Default_Splits, Configured_Data
from Interventions import Scenario, Intervention, Rollout, Model

app = Dash(__name__,
           external_stylesheets=[dbc.themes.BOOTSTRAP])

input_file = 'Reference Data/Large Test Portfolio.xlsx'

assets = pd.read_excel(input_file, sheet_name='Assets')
consumption = pd.read_excel(input_file, sheet_name='Consumption')
interventions_df = pd.read_excel(input_file, sheet_name='Interventions')
rollouts_df = pd.read_excel(input_file, sheet_name='Rollouts').fillna('-')

default_splits = Default_Splits('Reference Data/Intervention Parameters.xlsx')
splits = Configured_Data(default_splits)

test_model = Model(assets, consumption)

test_model.scenarios_from_df(interventions_df, rollouts_df)

df = (test_model.apply_interventions(test_model.scenarios)
      .pipe(path.attach_asset_data, assets, ['Country Code', 'Sector Code', 'Area'])
      .reset_index()
      )

asset_list = assets['UID'].unique()
country_list = assets['Country Code'].unique()
sector_list = assets['Sector Code'].unique()
scenario_list = df['Scenario'].unique()
path_list = ['GHG-Int', 'kWh-Int']

app.layout = dbc.Container(children=[
    html.H1(children='Dashboard'),

    dbc.Row(children=[
        dbc.Col(dcc.Graph(
            id='pathway-graph'
        ), width=8
        ),

        dbc.Col(dbc.Stack([
            dcc.Dropdown(
                asset_list,
                id='asset-dropdown',
                multi=True,
                placeholder='Select Assets to include'
            ),

            dcc.Dropdown(
                country_list,
                id='country-dropdown',
                multi=True,
                placeholder='Select Countries to include'
            ),

            dcc.Dropdown(
                sector_list,
                id='sector-dropdown',
                multi=True,
                placeholder='Select Sectors to include'
            ),

            dcc.Dropdown(
                scenario_list,
                id='scenario-dropdown',
                placeholder='Select Scenarios to include'
            ),

            dcc.Dropdown(
                path_list,
                id='path-dropdown',
                placeholder='Select Pathway Type to display'
            )
        ],
            gap=3
        ),
            align='center',
            width=4
        )

    ]),

    dbc.Row(

    )
])


@app.callback(
    Output('pathway-graph', 'figure'),
    Input('asset-dropdown', 'value'),
    Input('country-dropdown', 'value'),
    Input('sector-dropdown', 'value'),
    Input('scenario-dropdown', 'value'),
    Input('path-dropdown', 'value')
)
def plot_figure(input_assets, input_countries, input_sectors, input_scenario, input_path):
    assets = input_assets if input_assets else asset_list
    countries = input_countries if input_countries else country_list
    sectors = input_sectors if input_sectors else sector_list
    scenario = input_scenario if input_scenario else 'Scenario 1'
    path_type = input_path if input_path else 'GHG-Int'

    scenarios = ['BAU', 'Target']
    scenarios.append(scenario)

    mask = ((df['UID'].isin(assets))
            & (df['Country Code'].isin(countries))
            & (df['Sector Code'].isin(sectors))
            & (df['Pathway Code'] == path_type)
            & (df['Scenario']).isin(scenarios)
            )

    plot_sums = (df[mask]
                 .drop(columns=['Country Code', 'Sector Code', 'UID', 'Pathway Code'])
                 .groupby('Scenario')
                 .sum()  # TODO: would like to retain more aggregations (min, max, some percentiles) here in future
                 )

    plot_data = (plot_sums.div(plot_sums['Area'], axis=0)
                 .drop(columns=['Area'])
                 .T
                 .replace(0, np.nan)
                 )

    fig = px.line(plot_data, x=plot_data.index, y=scenarios)

    return fig


if __name__ == '__main__':
    app.run_server(debug=True)
