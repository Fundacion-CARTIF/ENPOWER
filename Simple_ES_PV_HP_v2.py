#%% Simple Energy System
import os
import json
import numpy as np
import pandas as pd
from oemof.solph import EnergySystem, buses, components, flows, Model, Investment
from oemof.tools import economics
# from classes_database import Building_data
from helpers.helpers import save_optimized_results_to_dataframe, generate_sankey_from_dataframe, normalize_profile, initialise, create_datetime_vector, create_epw_dataframe
# import helpers.constants as cte
# from models.solar_thermal_model import SolarThermalCollector
from models.chiller_model import CompressionHeatPumpChiller
from models.pv_model import PVSystem
from classes_database_viejas import PVGISAPI

#%% Load the JSON file
file_path_bd = os.path.join(os.getcwd(), 'data', 'community_context_updated_2_granada.json')

try:
    with open(file_path_bd, 'r') as file:
        bd = json.load(file)
except (IOError, json.JSONDecodeError) as e:
    print(f"Error loading JSON file: {e}")
    exit()

# Initialize buildings
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

#%% Validate and normalize profiles
raw_electricity_consumption = {}  # Store raw electricity consumption
raw_dhw_consumption = {}  # Store raw DHW consumption
raw_heat_consumption = {}  # Store raw heating consumption

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

    # Retrieve consumption profiles
    consumption = building_data.building_consumption

    # Store raw consumption data before normalizing
    if consumption.elec_consumption:
        raw_electricity_consumption[building_id] = consumption.elec_consumption[:]
    if consumption.dhw_consumption:
        raw_dhw_consumption[building_id] = consumption.dhw_consumption[:]
    if consumption.heat_consumption:
        raw_heat_consumption[building_id] = consumption.heat_consumption[:]

    # Compute zero values for reporting
    elec_zeros = consumption.elec_consumption.count(0) if consumption.elec_consumption else 0
    dhw_zeros = consumption.dhw_consumption.count(0) if consumption.dhw_consumption else 0
    heat_zeros = consumption.heat_consumption.count(0) if consumption.heat_consumption else 0

    print(
        f"  Electricity Demand Profile: {elec_zeros / len(consumption.elec_consumption) * 100:.2f}% zeros"
        if consumption.elec_consumption else "Electricity Profile is empty"
    )
    print(
        f"  DHW Demand Profile: {dhw_zeros / len(consumption.dhw_consumption) * 100:.2f}% zeros"
        if consumption.dhw_consumption else "DHW Profile is empty"
    )
    print(
        f"  Heat Demand Profile: {heat_zeros / len(consumption.heat_consumption) * 100:.2f}% zeros"
        if consumption.heat_consumption else "Heat Profile is empty"
    )

    # Normalize consumption profiles
    if consumption.elec_consumption:
        consumption.elec_consumption = normalize_profile(consumption.elec_consumption)
    if consumption.dhw_consumption:
        consumption.dhw_consumption = normalize_profile(consumption.dhw_consumption)
    if consumption.heat_consumption:
        consumption.heat_consumption = normalize_profile(consumption.heat_consumption)

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


#%% Assertions (after electricity price is loaded)
assert all(len(asset.input1) == len(electricity_price) for building_data in buildings.values()
           for asset in building_data.building_energy_assets.values()), "Length mismatch in PV profiles."

assert all(len(building_data.building_consumption.elec_consumption) == len(electricity_price)
           for building_data in buildings.values()), "Length mismatch in electricity consumption profiles."

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

#%% Initialize Heat Pumps for Each Building (Investment-Based)
heat_pumps = {}

for building_id, building_data in buildings.items():
    # Retrieve heat pump investment parameters
    capex_hp = 1100  # Example CAPEX per kW (adjust based on actual values)
    lifetime_hp = 30  # Example lifetime in years

    # Calculate Equivalent Annual Cost (EPC)
    epc_hp = economics.annuity(capex_hp, lifetime_hp, 0.05)  # 5% discount rate

    pmaxmin_hp = 1  # Minimum capacity (kW)
    pmaxmax_hp = 15  # Maximum capacity (kW)

    # Retrieve building-specific consumption data
    elec_consumption_norm = building_data.building_consumption.elec_consumption
    elec_consumption_raw = raw_electricity_consumption.get(building_id, [])
    heat_consumption_norm = building_data.building_consumption.heat_consumption
    heat_consumption_raw = raw_heat_consumption.get(building_id, [])

    # Ensure valid data exists before proceeding
    if not elec_consumption_norm or not elec_consumption_raw or not heat_consumption_norm or not heat_consumption_raw:
        print(f"Skipping Heat Pump for Building {building_id} due to missing data.")
        continue

    # Ensure max capacity follows the rule
    investment_max_hp = max(1, pmaxmax_hp) if pmaxmax_hp < 0.25 else pmaxmax_hp

    print(f"Adding Investment Heat Pump for Building {building_id}: epc_hp={epc_hp:.2f}, pmaxmin={pmaxmin_hp}, pmaxmax={investment_max_hp}")

    # Create a unique label for each heat pump
    hp_label = f"Investment Heat Pump Building {building_id}"

    # Ensure COP is properly formatted (avoid series issues)
    cop_series = np.array(COP_HEAT)  # Convert to NumPy array

    # Define investment heat pump component
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
        outputs={
            bus_heat: flows.Flow(nominal_value=None)
        },
        conversion_factors={bus_elec: 1, bus_heat: cop_series}  # Time-dependent COP
    )

    # Store **actual reference** in dictionary
    heat_pumps[building_id] = heat_pump

    # Add to the energy system
    energysystem.add(heat_pump)


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

#%% Add Electricity Consumption Sinks for Each Building
for building_id, building_data in buildings.items():
    # Retrieve normalized electricity consumption for the building
    elec_consumption_norm = building_data.building_consumption.elec_consumption

    # Retrieve raw electricity consumption (before normalization)
    elec_consumption_raw = raw_electricity_consumption.get(building_id, [])

    if elec_consumption_norm and elec_consumption_raw:
        # Add electricity consumption sink to the energy system
        energysystem.add(
            components.Sink(
                label=f"Electricity Consumption Building {building_id}",
                inputs={
                    bus_elec: flows.Flow(
                        fix=elec_consumption_norm,  # Use normalized consumption
                        nominal_value=max(elec_consumption_raw)  # Use max raw value
                    )
                }
            )
        )



#%% Add DHW Consumption Sinks for Each Building
for building_id, building_data in buildings.items():
    # Retrieve normalized DHW consumption for the building
    dhw_consumption_norm = building_data.building_consumption.dhw_consumption

    # Retrieve raw DHW consumption (before normalization)
    dhw_consumption_raw = raw_dhw_consumption.get(building_id, [])

    if dhw_consumption_norm and dhw_consumption_raw:
        # Add DHW consumption sink to the energy system
        energysystem.add(
            components.Sink(
                label=f"DHW Consumption Building {building_id}",
                inputs={
                    bus_dhw: flows.Flow(
                        fix=dhw_consumption_norm,  # Use normalized DHW consumption
                        nominal_value=max(dhw_consumption_raw)  # Use max raw value
                    )
                }
            )
        )

#%% Add Heating Consumption Sinks for Each Building
for building_id, building_data in buildings.items():
    # Retrieve normalized heating consumption for the building
    heat_consumption_norm = building_data.building_consumption.heat_consumption

    # Retrieve raw heating consumption (before normalization)
    heat_consumption_raw = raw_heat_consumption.get(building_id, [])

    if heat_consumption_norm and heat_consumption_raw:
        # Add heating consumption sink to the energy system
        energysystem.add(
            components.Sink(
                label=f"Heating Consumption Building {building_id}",
                inputs={
                    bus_heat: flows.Flow(
                        fix=heat_consumption_norm,  # Use normalized heating consumption
                        nominal_value=max(heat_consumption_raw)  # Use max raw value
                    )
                }
            )
        )

#%% Create a dataframe with timestamps and electricity prices
electricity_price_df = pd.DataFrame({'datetime': date_time_index, 'price': electricity_price})

# Extract the month for each hourly price
electricity_price_df['month'] = electricity_price_df['datetime'].dt.month

# Compute total electricity cost per month (assuming 1 kWh usage per hour initially)
monthly_grid_costs = electricity_price_df.groupby('month')['price'].sum()

# Compute the maximum kWh that can be exported per month
monthly_export_limit_kWh = monthly_grid_costs / (electricity_price_df.groupby("month")["price"].mean() * (1/3))

# Convert monthly kWh limit to an hourly list for oemof
monthly_export_limit_per_hour = electricity_price_df['month'].map(monthly_export_limit_kWh).tolist()


# # Define excess electricity sink
# variable_costs_excess = pd.Series(electricity_price) * (-1/3)
# variable_costs_excess = variable_costs_excess.to_list()

# Convert monthly grid costs to a list indexed by hour
monthly_cost_limit_per_hour = electricity_price_df['month'].map(monthly_grid_costs).tolist()

# Define excess electricity sink with a limited export cap
excess_sink = components.Sink(
    label="Excess electricity",
    inputs={bus_elec: flows.Flow(
        variable_costs=[-1/3 * p for p in electricity_price],  # Provider pays 1/3 of the price
        nominal_value=monthly_export_limit_per_hour  # Maximum kWh export per hour
    )}
)

# Add the excess electricity sink to the energy system
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

    assets = {
        "Investment PV System": pv_sources,
        "Investment Heat Pump Building": heat_pumps
    }

    for asset_type, asset_dict in assets.items():
        for asset_id, component in asset_dict.items():
            asset_label = f"{asset_type} {asset_id}"  # Match the correct label

            # Find component in the energy system
            component_ref = next((comp for comp in energysystem.nodes if comp.label == asset_label), None)

            if not component_ref:
                print(f"⚠️ Warning: {asset_label} not found in the energy system.")
                continue

            # 🔄 Correcting the result_key format for PV and HP
            if "PV System" in asset_type:
                result_key = (component_ref, bus_elec)  # ✅ Correct format for PV
            else:
                result_key = (bus_elec, component_ref)  # ✅ Correct format for Heat Pump

            if result_key in results:
                invested_capacity = results[result_key].get("scalars", {}).get("invest", None)

                if invested_capacity is not None:
                    print(f"✅ Optimal {asset_type} capacity for {asset_label}: {invested_capacity:.2f} kW")
                else:
                    print(f"⚠️ No investment value found for {asset_label}")
            else:
                print(f"⚠️ No result entry found for {asset_label}")

except Exception as e:
    print(f"❌ Investment results extraction failed: {e}")


# %% Acess to results and save to dataframe:
results_df = save_optimized_results_to_dataframe(model, results)
results_df[['source', 'target']] = pd.DataFrame(results_df['source'].tolist(), index=results_df.index)
results_year = results_df.groupby(['source', 'target'])['flow'].sum().reset_index()

# %%
generate_sankey_from_dataframe(results_year)
# %%
