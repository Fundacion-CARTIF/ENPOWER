#%% Simple Energy System
import os
import json
import numpy as np
import pandas as pd
from oemof.solph import EnergySystem, buses, components, flows, Model, Investment
from oemof.tools import economics
from classes_database import BuildingEnergyAsset, BuildingConsumption

#%% Load the JSON file
file_path_bd = os.path.join(os.getcwd(), 'data', 'community_context_updated_2_granada.json')

try:
    with open(file_path_bd, 'r') as file:
        bd = json.load(file)
except (IOError, json.JSONDecodeError) as e:
    print(f"Error loading JSON file: {e}")
    exit()

#%% Helper function for normalization
def normalize_profile(profile):
    if not profile:
        return profile  # Return empty profile if no data
    max_value = max(profile)
    return [x / max_value if max_value != 0 else 0 for x in profile]

#%% Initialize data for buildings 
building_assets = []
building_consumptions = []

# Loop through building contexts
for context in bd.get("building_asset_context", []):  # Safely handle missing or empty list
    consumption_data = context.get("building_consumption", {})
    elec_consumption = [float(value) for value in consumption_data.get("elec_consumption", [])]
    dhw_consumption = [float(value) for value in consumption_data.get("dhw_consumption", [])]
    heat_consumption = [float(value) for value in consumption_data.get("heat_consumption", [])]
    cool_consumption = [float(value) for value in consumption_data.get("cool_consumption", [])]

    building_consumption = BuildingConsumption(
        building_consumption_id_temp=consumption_data.get("id", None),
        elec_consumption=elec_consumption,
    )
    building_consumption.add_existing_consumptions(heat_consumption, dhw_consumption, cool_consumption)
    building_consumptions.append(building_consumption)
    try:
        for building_asset_data in context.get("building_energy_asset", []):
            generation_system_id = building_asset_data.get("generation_system_id", None)
            pmaxmin_scalar = building_asset_data.get("pmaxmin_scalar", None)
            pmaxmax_scalar = building_asset_data.get("pmaxmax_scalar", None)
            name = building_asset_data.get("availability_ts", {}).get("name", None)
            building_asset_context_id = context.get("building_asset_context_id", None)
            building_asset = BuildingEnergyAsset(
                generation_system_id=generation_system_id,
                pmaxmin_scalar=pmaxmin_scalar,
                pmaxmax_scalar=pmaxmax_scalar,
                building_asset_context_id=building_asset_context_id,
                name=name,
            )
            if generation_system_id in [83]:
                generation_profile = [
                    float(value) for value in building_asset_data.get("availability_ts", {}).get("value_input1", [])
                ]
                building_asset.add_PV_profile(generation_profile)

            building_assets.append(building_asset)


    except KeyError as e:
        print(f"Missing key {e} in context: {context}")
    except IndexError as e:
        print(f"Index error in 'building_energy_asset': {context}")

#%% Normalize profiles
for idx, (asset, consumption) in enumerate(zip(building_assets, building_consumptions)):
    asset.input1 = normalize_profile(asset.input1)
    consumption.elec_consumption = normalize_profile(consumption.elec_consumption)
    consumption.dhw_consumption = normalize_profile(consumption.dhw_consumption)
    consumption.heat_consumption = normalize_profile(consumption.heat_consumption)

#%% Load electricity and gas prices
price_data = pd.read_csv(os.path.join(os.getcwd(), 'Spain_Hourly_Electricity_and_Gas_Prices_2023__EUR_kWh_ ChatGPT.csv'))
electricity_price = price_data['Electricity Price [EUR/kWh]'].tolist()
gas_price = price_data['Gas Price [EUR/kWh]'].tolist()

# Validate time series lengths
assert all(len(asset.input1) == len(electricity_price) for asset in building_assets), "Length mismatch in PV profiles."
assert all(len(consumption.elec_consumption) == len(electricity_price) for consumption in building_consumptions), "Length mismatch in electricity consumption profiles."

#%% PV Sources for both buildings
epc = economics.annuity(1100, 30, 0.05)  # Calculate equivalent annual cost
# capex = 1100  # investment cost
# lifetime = 30  # life expectancy
# wacc = 0.05  # weighted average of capital cost
# epc = capex * (wacc * (1 + wacc) ** lifetime) / ((1 + wacc) ** lifetime - 1)

#%% Electricity Price and Demand Multiplier Analysis
price_multipliers = [1, 5]
demand_multipliers_1 = [1, 10]  # Multipliers for Building 1
demand_multipliers_2 = [1, 4]    # Multipliers for Building 2
results_summary = []

for price_multiplier in price_multipliers:
    for demand_multiplier_1 in demand_multipliers_1:
        for demand_multiplier_2 in demand_multipliers_2:
            # print(f"\n--- Analysis for Price Multiplier: {price_multiplier}, Demand Multiplier Building 1: {demand_multiplier_1}, Demand Multiplier Building 2: {demand_multiplier_2} ---")

            # Adjust electricity prices
            electricity_price_adjusted = [price * price_multiplier for price in electricity_price]

            # Adjust demand for Building 1 and Building 2
            demand_1_adjusted = [d * demand_multiplier_1 for d in building_consumptions[0].elec_consumption]
            demand_2_adjusted = [d * demand_multiplier_2 for d in building_consumptions[1].elec_consumption]

            # Create a new energy system
            date_time_index = pd.date_range('2019-01-01 00:00:00', periods=8760, freq='h')
            energysystem = EnergySystem(timeindex=date_time_index, infer_last_interval=True)

            # Core buses
            bus_dhw = buses.Bus(label="DHW")
            bus_heat = buses.Bus(label="Heating")
            bus_elec = buses.Bus(label="Electricity")
            bus_gas = buses.Bus(label="NG")
            energysystem.add(bus_dhw, bus_heat, bus_elec, bus_gas)

            # Redefine PV systems for this loop iteration
            pv_source_1 = components.Source(
                label="PV System Building 1",
                outputs={bus_elec: flows.Flow(fix=building_assets[0].input1, nominal_value=Investment(ep_costs=epc, maximum=7))}
            )
            pv_source_2 = components.Source(
                label="PV System Building 2",
                outputs={bus_elec: flows.Flow(fix=building_assets[1].input1, nominal_value=Investment(ep_costs=epc, maximum=6))}
            )
            energysystem.add(pv_source_1, pv_source_2)

            # Add grid and gas sources
            energysystem.add(
                components.Source(
                    label="Grid Source",
                    outputs={bus_elec: flows.Flow(variable_costs=electricity_price_adjusted)}
                )
            )
            energysystem.add(
                components.Source(
                    label="Gas Source",
                    outputs={bus_gas: flows.Flow(variable_costs=gas_price)}
                )
            )

            # Add sinks
            energysystem.add(
                components.Sink(
                    label="Electricity Consumption Building 1",
                    inputs={bus_elec: flows.Flow(
                        fix=normalize_profile(demand_1_adjusted),
                        nominal_value=max(demand_1_adjusted)
                    )}
                )
            )
            energysystem.add(
                components.Sink(
                    label="Electricity Consumption Building 2",
                    inputs={bus_elec: flows.Flow(
                        fix=normalize_profile(demand_2_adjusted),
                        nominal_value=max(demand_2_adjusted)
                    )}
                )
            )
            energysystem.add(
                components.Sink(
                    label="Excess Sink",
                    inputs={bus_elec: flows.Flow(variable_costs=0.0)}
                )
            )

            # Build and solve the model
            model = Model(energysystem)
            try:
                model.solve(solver="cbc", solve_kwargs={"tee": False})
            except Exception as e:
                print(f"Solver failed for Price Multiplier: {price_multiplier}, Demand Multipliers: {demand_multiplier_1}, {demand_multiplier_2}: {e}")
                continue

            # Extract results
            try:
                results = model.results()
                invested_capacity_1 = results[(pv_source_1, bus_elec)]["scalars"]["invest"]
                invested_capacity_2 = results[(pv_source_2, bus_elec)]["scalars"]["invest"]

                # print(f"Optimal PV capacity for Building 1: {invested_capacity_1:.2f} kW")
                # print(f"Optimal PV capacity for Building 2: {invested_capacity_2:.2f} kW")

                results_summary.append({
                    "Price Multiplier": price_multiplier,
                    "Demand Multiplier Building 1": demand_multiplier_1,
                    "Demand Multiplier Building 2": demand_multiplier_2,
                    "Invested Capacity Building 1 (kW)": invested_capacity_1,
                    "Invested Capacity Building 2 (kW)": invested_capacity_2,
                })
            except KeyError as e:
                print(f"Results extraction failed for Price Multiplier: {price_multiplier}, Demand Multipliers: {demand_multiplier_1}, {demand_multiplier_2}: {e}")

#%% Summarize results
results_df = pd.DataFrame(results_summary)

# Print the results to the console
print("Electricity Price and Demand Multipliers vs PV Capacities:")
print(results_df)
print("test")