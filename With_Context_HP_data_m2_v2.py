#%% Simple Energy System
import os
import json
import numpy as np
import pandas as pd
from oemof.solph import EnergySystem, buses, components, flows, Model, Investment
from oemof.tools import economics
# from classes_database import Building_data
from helpers.helpers import (save_optimized_results_to_dataframe, generate_sankey_from_dataframe, normalize_profile,
                              initialise, create_datetime_vector, create_epw_dataframe, calculate_building_areas)
import helpers.constants as cte
# from models.solar_thermal_model import SolarThermalCollector
from models.chiller_model import CompressionHeatPumpChiller
from models.pv_model import PVSystem
from classes_database_viejas import PVGISAPI
from data_packages.draw import draw_energy_system
import matplotlib.pyplot as plt

#%% Load the JSON file
file_path_bd = os.path.join(os.getcwd(), 'data', 'community_context_updated_2_granada_PV_and_HPs.json')

try:
    with open(file_path_bd, 'r') as file:
        bd = json.load(file)
except (IOError, json.JSONDecodeError) as e:
    print(f"Error loading JSON file: {e}")
    exit()

#%% Initialize buildings
buildings = initialise(bd=bd)

#%% Load electricity and gas prices (before validation)
price_data = pd.read_csv(os.path.join(os.getcwd(), "data", 'Spain_Hourly_Electricity_and_Gas_Prices_2023__EUR_kWh_ ChatGPT.csv'))
electricity_price = price_data['Electricity Price [EUR/kWh]'].tolist()
gas_price = price_data['Gas Price [EUR/kWh]'].tolist()

# Retrieve data
config_filename =os.path.join(os.getcwd(),'model_configurations','config.yaml')
epw_filename = 'data/tmy_pvgis.epw'
tmy_pvgis_path = os.path.join(os.getcwd(), epw_filename)
epw_data = PVGISAPI.get_epw_data(tmy_pvgis_path, config_filename)

# Flat plate solar thermal collector calculation
STC_Parameters = PVGISAPI.load_config(os.path.join(os.getcwd(), 'model_configurations', 'config_STC.yaml'))
datetime_vector = create_datetime_vector(STC_Parameters['year'])
epw = create_epw_dataframe(datetime_vector, epw_data)

# Compression heat pump/chiller calculation
CHPC_Parameters = PVGISAPI.load_config(os.path.join(os.getcwd(), 'model_configurations', 'config_CHPC.yaml'))
chpc = CompressionHeatPumpChiller(CHPC_Parameters, epw)
COP_HEAT, COP_COOL = chpc.calculate_cops()

# %% Validate and normalize profiles
raw_electricity_demand = {}  # Store raw electricity demand
raw_dhw_demand = {}  # Store raw DHW demand
raw_heating_demand = {}  # Store raw heating demand
raw_cooling_demand = {}  # Store raw cooling demand

for building_id, building_data in buildings.items():
    print(f"Building {building_data.id} Validation:")

    # Normalize energy asset profiles (PV)
    for asset_name, asset_data in building_data.building_energy_assets.items():
        pv_profile_zeros = asset_data.input1.count(0) if asset_data.input1 else 0
        print(
            f"  PV Profile: {pv_profile_zeros / len(asset_data.input1) * 100:.2f}% zeros"
            if asset_data.input1 else "PV Profile is empty"
        )
        
        # Normalize PV Profile
        if asset_data.input1:
            asset_data.input1 = normalize_profile(asset_data.input1)

    # Retrieve demand profiles
    demand = building_data.building_demand

    # Store raw demand data before normalizing
    if demand['electricity_demand']:
        raw_electricity_demand[building_id] = demand['electricity_demand'][:]
    if demand['dhw_demand']:
        raw_dhw_demand[building_id] = demand['dhw_demand'][:]
    if demand['heating_demand']:
        raw_heating_demand[building_id] = demand['heating_demand'][:]
    if demand['cooling_demand']:
        raw_cooling_demand[building_id] = demand['cooling_demand'][:]

    # Compute zero values for reporting
    elec_zeros = demand['electricity_demand'].count(0) if demand['electricity_demand'] else 0
    dhw_zeros = demand['dhw_demand'].count(0) if demand['dhw_demand'] else 0
    heating_zeros = demand['heating_demand'].count(0) if demand['heating_demand'] else 0
    cooling_zeros = demand['cooling_demand'].count(0) if demand['cooling_demand'] else 0

    print(
        f"  Electricity Demand Profile: {elec_zeros / len(demand['electricity_demand']) * 100:.2f}% zeros"
        if demand['electricity_demand'] else "Electricity Demand Profile is empty"
    )
    print(
        f"  DHW Demand Profile: {dhw_zeros / len(demand['dhw_demand']) * 100:.2f}% zeros"
        if demand['dhw_demand'] else "DHW Demand Profile is empty"
    )
    print(
        f"  Heating Demand Profile: {heating_zeros / len(demand['heating_demand']) * 100:.2f}% zeros"
        if demand['heating_demand'] else "Heating Demand Profile is empty"
    )
    print(
        f"  Cooling Demand Profile: {cooling_zeros / len(demand['cooling_demand']) * 100:.2f}% zeros"
        if demand['cooling_demand'] else "Cooling Demand Profile is empty"
    )

    # # Normalize demand profiles
    if demand['electricity_demand']:
        demand['electricity_demand'] = normalize_profile(demand['electricity_demand'])
    if demand['dhw_demand']:
        demand['dhw_demand'] = normalize_profile(demand['dhw_demand'])
    if demand['heating_demand']:
        demand['heating_demand'] = normalize_profile(demand['heating_demand'])
    if demand['cooling_demand']:
        demand['cooling_demand'] = normalize_profile(demand['cooling_demand'])


#%% Initialize PV Sources and Calculate EPC
pv_sources = {}  

for building_id, building_data in buildings.items():
    for asset_name, building_energy_asset in building_data.building_energy_assets.items():
        if building_energy_asset.generation_system_id == 83:
            # Create a unique key for each instance
            asset_id = building_energy_asset.building_asset_context_id

            # Correct config path for PVSystem
            config_path = os.path.join("model_configurations", "config_PV.yaml")

            # Retrieve CAPEX, Lifetime, pmaxmin, and pmaxmax from the asset
            capex = building_energy_asset.capex  
            lifetime = building_energy_asset.lifetime  
            pmaxmin = building_energy_asset.pmaxmin_scalar  
            pmaxmax = building_energy_asset.pmaxmax_scalar  

            # Calculate Equivalent Annual Cost (EPC)
            epc = economics.annuity(capex, lifetime, 0.05)  # 5% discount rate

            # Instantiate the PVSystem class
            pv_sources[asset_id] = {
                "instance": PVSystem(
                    config_path=config_path,
                    pmaxmin=pmaxmin,  
                    pmaxmax=pmaxmax,
                    name=building_energy_asset.name,
                    capex=capex,
                ),
                "epc": epc,
                "input1": building_energy_asset.input1,
                "pmaxmin": pmaxmin,
                "pmaxmax": pmaxmax
            }

#%% Step 1: Initialize HP Sources and Calculate EPC
HP_sources = {}

for building_id, building_data in buildings.items():
    for asset_name, building_energy_asset in building_data.building_energy_assets.items():
        try:
            if building_energy_asset.generation_system_id == 63:
                # Create a unique key for each asset
                asset_id = building_energy_asset.building_asset_context_id

                # Retrieve CAPEX, Lifetime, and capacity parameters
                capex = building_energy_asset.capex
                lifetime = building_energy_asset.lifetime
                pmaxmin = building_energy_asset.pmaxmin_scalar
                pmaxmax = building_energy_asset.pmaxmax_scalar

                # Calculate Equivalent Annual Cost (EPC)
                epc = economics.annuity(capex, lifetime, 0.05)  # 5% discount rate

                # Store the data in HP_sources dictionary
                HP_sources[asset_id] = {
                    "epc": epc,
                    "capex": capex,
                    "lifetime": lifetime,
                    "pmaxmin": pmaxmin,
                    "pmaxmax": pmaxmax
                }

                # Enhanced print statement with CAPEX and Lifetime
                print(
                    f"HP Source for asset {asset_id} added: "
                    f"EPC={epc:.2f}, CAPEX={capex}, Lifetime={lifetime}, "
                    f"pmaxmin={pmaxmin}, pmaxmax={pmaxmax}"
                )

        except Exception as e:
            print(f"Error processing HP Source for Building {building_id}, Asset {asset_name}: {e}")


#%% Create an energy system
date_time_index = pd.date_range('2019-01-01 00:00:00', periods=8760, freq='h')

#%% Initialize energy system
energysystem = EnergySystem(timeindex=date_time_index, infer_last_interval=True)

# Core buses
bus_dhw = buses.Bus(label="DHW")
bus_heat = buses.Bus(label="Heating")
bus_elec = buses.Bus(label="Electricity")
bus_gas = buses.Bus(label="NG")
energysystem.add(bus_dhw, bus_heat, bus_elec, bus_gas)

# Gas Boilers
gas_boiler_heat = components.Converter(
    label="Gas Boiler for Heating",
    inputs={bus_gas: flows.Flow()},
    outputs={bus_heat: flows.Flow()},
    conversion_factors={bus_heat: 0.87}
)

gas_boiler_dhw = components.Converter(
    label="Gas Boiler for DHW",
    inputs={bus_gas: flows.Flow()},
    outputs={bus_dhw: flows.Flow()},
    conversion_factors={bus_dhw: 0.87}
)
energysystem.add(gas_boiler_heat, gas_boiler_dhw)

#%% Add PV Sources to the Energy System
for asset_id, pv_data in pv_sources.items():
    epc = pv_data.get("epc")
    pmaxmin = pv_data.get("pmaxmin")
    pmaxmax = pv_data.get("pmaxmax", 1)  # Default to 1 if missing
    input1 = pv_data.get("input1")

    # Ensure pmaxmax follows the condition
    maximum = max(1, pmaxmax) if pmaxmax < 0.25 else pmaxmax

    print(f"Adding Investment PV for Building: {asset_id}, epc: {epc:.2f}, pmaxmin: {pmaxmin}, pmaxmax: {pmaxmax}, maximum: {maximum}")

    pv_source = components.Source(
        label=f"Investment PV System {asset_id}",
        outputs={
            bus_elec: flows.Flow(
                fix=input1,
                nominal_value=Investment(
                    ep_costs=epc,
                    minimum=pmaxmin,
                    maximum=maximum
                )
            )
        },
    )

    energysystem.add(pv_source)

#%% Step 2: Initialize Heat Pumps for Each Building (Using Step 1 Parameters)
heat_pumps = {}

for building_id, building_data in buildings.items():
    try:
        # Check if this building has any HP sources initialized in Step 1
        hp_source_ids = [asset_id for asset_id in HP_sources if str(asset_id).startswith(str(building_id))]
        if not hp_source_ids:
            print(f"No HP Source found for Building {building_id}. Skipping Heat Pump initialization.")
            continue

        for asset_id in hp_source_ids:
            # Retrieve parameters from the stored HP sources
            hp_source = HP_sources[asset_id]
            epc_hp = hp_source["epc"]
            pmaxmin_hp = hp_source["pmaxmin"]
            pmaxmax_hp = hp_source["pmaxmax"]

            # Ensure max capacity follows the rule
            investment_max_hp = max(1, pmaxmax_hp) if pmaxmax_hp < 0.25 else pmaxmax_hp
            hp_label = f"Investment Heat Pump {asset_id}"

            # Ensure COP is properly formatted (avoid issues with series format)
            cop_series = np.array(COP_HEAT)  # Convert to NumPy array

            # Define the heat pump component
            heat_pump = components.Converter(
                label=hp_label,
                inputs={
                    bus_elec: flows.Flow(
                        nominal_value=Investment(
                            ep_costs=epc_hp,
                            minimum=pmaxmin_hp,
                            maximum=investment_max_hp
                        )
                    )
                },
                outputs={bus_heat: flows.Flow(nominal_value=None)},
                conversion_factors={bus_elec: 1, bus_heat: cop_series} # A partir de COP=3 empieza a invertir (Ahora: cop_series.mean()=1.27)
            )

            # Store the heat pump reference and add it to the energy system
            heat_pumps[building_id] = heat_pump
            energysystem.add(heat_pump)

            print(f"Investment Heat Pump for {asset_id} added: EPC={epc_hp:.2f}, pmaxmin={pmaxmin_hp}, pmaxmax={investment_max_hp}")

    except Exception as e:
        print(f"Error initializing Heat Pump for Building {building_id}: {e}")



# Grid and Gas Sources
grid_source = components.Source(
    label="Grid Source",
    outputs={bus_elec: flows.Flow(variable_costs=electricity_price)}
)
gas_source = components.Source(
    label="Gas Source",
    outputs={bus_gas: flows.Flow(variable_costs=gas_price)}
)
energysystem.add(grid_source, gas_source)

# %% Add Electricity Demand Sinks for Each Building
for building_id, building_data in buildings.items():
    # Retrieve normalized electricity demand for the building
    elec_demand_norm = building_data.building_demand.get('electricity_demand', [])

    # Retrieve raw electricity demand (before normalization)
    elec_demand_raw = raw_electricity_demand.get(building_id, [])

    if elec_demand_norm and elec_demand_raw:
        # Add electricity demand sink to the energy system
        energysystem.add(
            components.Sink(
                label=f"Electricity Demand Building {building_id}",
                inputs={
                    bus_elec: flows.Flow(
                        fix=elec_demand_norm,  # Use normalized demand
                        nominal_value=max(elec_demand_raw)  # Use max raw value
                    )
                }
            )
        )

# %% Add DHW Demand Sinks for Each Building
for building_id, building_data in buildings.items():
    # Retrieve normalized DHW demand for the building
    dhw_demand_norm = building_data.building_demand.get('dhw_demand', [])

    # Retrieve raw DHW demand (before normalization)
    dhw_demand_raw = raw_dhw_demand.get(building_id, [])

    if dhw_demand_norm and dhw_demand_raw:
        # Add DHW demand sink to the energy system
        energysystem.add(
            components.Sink(
                label=f"DHW Demand Building {building_id}",
                inputs={
                    bus_dhw: flows.Flow(
                        fix=dhw_demand_norm,  # Use normalized DHW demand
                        nominal_value=max(dhw_demand_raw)  # Use max raw value
                    )
                }
            )
        )

# %% Add Heating Demand Sinks for Each Building
for building_id, building_data in buildings.items():
    # Retrieve normalized heating demand for the building
    heating_demand_norm = building_data.building_demand.get('heating_demand', [])

    # Retrieve raw heating demand (before normalization)
    heating_demand_raw = raw_heating_demand.get(building_id, [])

    if heating_demand_norm and heating_demand_raw:
        # Add heating demand sink to the energy system
        energysystem.add(
            components.Sink(
                label=f"Heating Demand Building {building_id}",
                inputs={
                    bus_heat: flows.Flow(
                        fix=heating_demand_norm,  # Use normalized heating demand
                        nominal_value=max(heating_demand_raw)  # Use max raw value
                    )
                }
            )
        )


# # Define excess electricity sink
variable_costs_excess = pd.Series(electricity_price) * (-1/3)
variable_costs_excess = variable_costs_excess.to_list()

# Create the excess electricity sink component
excess_sink = components.Sink(
    label="Excess electricity",
    inputs={bus_elec: flows.Flow(variable_costs=variable_costs_excess)}
)

# Add it to the energy system
energysystem.add(excess_sink)

#%% Add Excess Heat Sink to Avoid Overproduction Issues
energysystem.add(
    components.Sink(
        label="Excess Heat",
        inputs={bus_heat: flows.Flow(variable_costs=0)}  # Allows heat dumping if needed
    )
)

#%% Build and solve the model
model = Model(energysystem)

try:
    model.solve(solver="cbc", solve_kwargs={"tee": False})
except Exception as e:
    print(f"Solver failed: {e}")

#%% Extract and Display Investment Results for PV and Heat Pumps
try:
    results = model.results()

    # Define both asset types: PV Systems and Heat Pumps
    assets = {
        "Investment PV System": pv_sources,  # ✅ PV investments
        "Investment Heat Pump": heat_pumps   # ✅ HP investments
    }

    for asset_type, asset_dict in assets.items():
        for asset_id, component in asset_dict.items():
            asset_label = f"{asset_type} {asset_id}"  # Construct the correct label

            # Find the component in the energy system
            component_ref = next((comp for comp in energysystem.nodes if comp.label == asset_label), None)

            if not component_ref:
                print(f"⚠️ Warning: {asset_label} not found in the energy system.")
                continue

            # 🔄 Set correct result_key format for PV and HP
            if "PV System" in asset_type:
                result_key = (component_ref, bus_elec)  # ✅ Correct for PV
            else:
                result_key = (bus_elec, component_ref)  # ✅ Correct for Heat Pump

            if result_key in results:
                invested_capacity = results[result_key].get("scalars", {}).get("invest", None)

                if invested_capacity is not None:
                    print(f"✅ Optimal {asset_type} capacity for {asset_label}: {invested_capacity:.2f} kW")
                else:
                    print(f"⚠️ No investment value found for {asset_label}.")
            else:
                print(f"⚠️ No result entry found for {asset_label}")

except Exception as e:
    print(f"❌ Investment results extraction failed: {e}")


# %% Access to results and save to dataframe
results_df = save_optimized_results_to_dataframe(model, results)

# Split the 'source' and 'target' columns
results_df[['source', 'target']] = pd.DataFrame(results_df['source'].tolist(), index=results_df.index)

results_year = results_df.groupby(['source', 'target'])['flow'].sum().reset_index()

generate_sankey_from_dataframe(results_year, "HP", "HP Scenario")

draw_energy_system(energy_system=energysystem, filepath="data/energy_system_graph_HP",
                   img_format="png", legend=False)


# %% Convert 'datetime' column to pandas datetime format (if not already)
results_df['datetime'] = pd.to_datetime(results_df['datetime'])

# %% Calculate building areas and store in a dictionary
areas = calculate_building_areas(buildings)

# Calculate total buildings areas
total_area = sum(areas.values())

# %% Normalize all relevant flows
# Create a copy of results_df with only data from 2019
normalized_df = results_df[results_df['datetime'].dt.year == 2019].copy()

# Normalize all relevant flows
for building_id, area in areas.items():
    if area > 0:
        # Normalize electricity and heating demands per building area
        normalized_df.loc[normalized_df['target'] == f'Heating Demand Building {building_id}', 'flow'] /= area
        normalized_df.loc[normalized_df['target'] == f'Electricity Demand Building {building_id}', 'flow'] /= area

        # Normalize investment in heat pump using source 'electricity'
        normalized_df.loc[(normalized_df['source'] == 'electricity') & 
                          (normalized_df['target'] == f'Investment Heat Pump {building_id}'), 'flow'] /= area

# Normalize 'Grid Source' by total area
if total_area > 0:
    normalized_df.loc[normalized_df['source'] == 'grid source', 'flow'] /= total_area

# Normalize 'Excess electricity' by total area
normalized_df.loc[normalized_df['target'] == 'Excess electricity', 'flow'] /= total_area


# %% Electricity Boxplots (Normalized)
# Normalize 'source' column in normalized_df (remove spaces and make it lowercase)
normalized_df['source'] = normalized_df['source'].str.strip().str.lower()

# Convert 'datetime' to a proper datetime object and extract 'month'
normalized_df['datetime'] = pd.to_datetime(normalized_df['datetime'])
normalized_df['month'] = normalized_df['datetime'].dt.to_period('M').astype(str)

# Filter data for only "Grid Source" and heat pump investments
filtered_source_df = normalized_df[normalized_df["source"].isin([
    'investment heat pump 291',
    'investment heat pump 292'
])]

# Create a 3-row subplot layout (one for each of the selected sources)
fig, axes = plt.subplots(nrows=2, ncols=1, figsize=(18, 8), sharex=True, sharey=True)

# Titles for each subplot
subplot_titles = [
    "Investment Heat Pump 291 (kW/m²)",
    "Investment Heat Pump 292 (kW/m²)"
]

# Loop through each filtered source and plot the boxplot
for i, source in enumerate(['investment heat pump 291', 'investment heat pump 292']):
    ax = axes[i]
    group = filtered_source_df[filtered_source_df['source'] == source]
    if not group.empty:
        group.boxplot(column='flow', by='month', ax=ax, grid=False, patch_artist=True, boxprops=dict(facecolor='lightblue'))
        ax.set_title(subplot_titles[i], fontsize=12)
        ax.set_xlabel("")
        ax.set_ylabel("Flow (kW/m²)")
    else:
        ax.set_title(f"{subplot_titles[i]} (No data)", fontsize=12)

# Set the overall title and adjust layout
fig.suptitle("Monthly Boxplot Heat Pump Investments", fontsize=16, y=1.02)
fig.tight_layout(rect=[0, 0.03, 1, 0.95])
plt.show()



# %% Heating Demand Boxplots (Normalized by Building Area)
# Filter for Heating Demand in normalized_df
filtered_source_df = normalized_df[normalized_df["target"].isin([
    'Heating Demand Building 291',
    'Heating Demand Building 292'
])]
filtered_source_df['month'] = filtered_source_df['datetime'].dt.to_period('M').astype(str)

# Plot Heating Demand Boxplots
fig, axes = plt.subplots(nrows=2, ncols=1, figsize=(18, 8), sharex=True, sharey=True)
subplot_titles = [
    "Heating Demand Building 291 (kW/m²)",
    "Heating Demand Building 292 (kW/m²)"
]

# Generate boxplots for each heating demand target
for i, (target, group) in enumerate(filtered_source_df.groupby('target')):
    ax = axes[i]
    group.boxplot(column='flow', by='month', ax=ax, grid=False, patch_artist=True, boxprops=dict(facecolor='lightgreen'))
    ax.set_title(subplot_titles[i], fontsize=12)
    ax.set_xlabel("")
    ax.set_ylabel("Flow (kW/m²)")

# Adjust layout and title
fig.suptitle("Monthly Boxplot Heating Demand", fontsize=16, y=1.02)
fig.tight_layout(rect=[0, 0.03, 1, 0.95])
plt.show()


# %% Electricity Demand Boxplots (Normalized by Building Area)
# Filter for Electricity Demand in normalized_df
filtered_source_df = normalized_df[normalized_df["target"].isin([
    'Electricity Demand Building 291',
    'Electricity Demand Building 292'
])]
filtered_source_df['month'] = filtered_source_df['datetime'].dt.to_period('M').astype(str)

# Plot Electricity Demand Boxplots
fig, axes = plt.subplots(nrows=2, ncols=1, figsize=(18, 8), sharex=True, sharey=True)
subplot_titles = [
    "Electricity Demand Building 291 (kW/m²)",
    "Electricity Demand Building 292 (kW/m²)"
]

# Generate boxplots for each electricity demand target
for i, (target, group) in enumerate(filtered_source_df.groupby('target')):
    ax = axes[i]
    group.boxplot(column='flow', by='month', ax=ax, grid=False, patch_artist=True, boxprops=dict(facecolor='lightcoral'))
    ax.set_title(subplot_titles[i], fontsize=12)
    ax.set_xlabel("")
    ax.set_ylabel("Flow (kW/m²)")

# Adjust layout and title
fig.suptitle("Monthly Boxplot of Electricity Demand", fontsize=16, y=1.02)
fig.tight_layout(rect=[0, 0.03, 1, 0.95])
plt.show()


# %%
