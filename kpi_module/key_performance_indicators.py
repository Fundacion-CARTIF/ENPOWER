import os
import json
from classes_database import FinalEnergy, BuildingKPIs, CommunityEnergyAsset
import pandas as pd
from KPI_module import (kpi_ctz_factors,tv_h, streaming_h, pizza_h, battery_charges, el_car_charges,trees_number,
                        streaming_emission_hours,icv_km,wine_bottles)
import geopandas as gpd
from shapely import wkt
from shapely.geometry import shape
import helpers.constants as cte


def handle_demand_profile(building_asset_context,generation_system_profile,consumption_profile):
    consumption_profile_length=len(consumption_profile[cte.ELECTRICITY_CONSUMPTION])
    # Handle demand_profile: If it doesn"t exist, calculate using generation system profiles
    building_id=building_asset_context.get(cte.ID)
    demand_profile = building_asset_context.get(cte.BUILDING, {}).get(cte.DEMANDPROFILE)
    if demand_profile is None and generation_system_profile is not None:
        # Retrieve fuel yield values from the generation system profiles
        if generation_system_profile.get(cte.HEATING_SYSTEM, {}) is not None:
            fuel_yield1_heating = generation_system_profile.get(cte.HEATING_SYSTEM, {}).get(cte.FUEL_YIELD_1, 1)
        else:
            fuel_yield1_heating = 0
            consumption_profile[cte.HEAT_CONSUMPTION]=[0]*consumption_profile_length
        if generation_system_profile.get(cte.COOLING_SYSTEM, {}) is not None:
            fuel_yield1_cooling = generation_system_profile.get(cte.COOLING_SYSTEM, {}).get(cte.FUEL_YIELD_1, 1)
        else:
            fuel_yield1_cooling = 0
            consumption_profile[cte.COOL_CONSUMPTION]=[0]*consumption_profile_length
        if generation_system_profile.get(cte.DHW_SYSTEM, {}) is not None:
            fuel_yield1_dhw = generation_system_profile.get(cte.DHW_SYSTEM, {}).get(cte.FUEL_YIELD_1, 1)
        else:
            fuel_yield1_dhw = 0
            consumption_profile[cte.DHW_CONSUMPTION]=[0]*consumption_profile_length

        # Calculate demand profile using the consumption profile and fuel yields
        demand_profile = {
            cte.ELECTRICITY_DEMAND: consumption_profile[cte.ELECTRICITY_CONSUMPTION],
            cte.HEATING_DEMAND: [x * fuel_yield1_heating for x in
                               consumption_profile.get(cte.HEAT_CONSUMPTION, [])],
            cte.COOLING_DEMAND: [x * fuel_yield1_cooling for x in
                               consumption_profile.get(cte.COOL_CONSUMPTION, [])],
            cte.DHW_DEMAND: [x * fuel_yield1_dhw for x in consumption_profile.get(cte.DHW_CONSUMPTION, [])]
        }
        return demand_profile

    elif demand_profile is None:
        return ValueError(
            f"Demand profile could not be calculated because generation system profile is missing for building ID: {building_id}")

def calculate_self_consumption(total_electricity_use, total_PV):
    return [
        min(total_electricity_use[i], total_PV[i])
        for i in range(len(total_electricity_use))
    ]

def calculate_rate_of_self_consumption(self_consumption, total_PV):
    return [
        (self_consumption[i] / total_PV[i]) * 100 if total_PV[i] > 0 else 0
        for i in range(len(self_consumption))
    ]

def calculate_grid_consumption(total_electricity_use, self_consumption):
    return [
        total_electricity_use[i] - self_consumption[i]
        for i in range(len(total_electricity_use))
    ]

def calculate_self_sufficiency(self_consumption, total_electricity_use):
    return [
        (self_consumption[i] / total_electricity_use[i]) * 100 if total_electricity_use[i] > 0 else 0
        for i in range(len(self_consumption))
    ]

def add_electricity_consumption(total_electricity_use, consumption):
    for i in range(len(total_electricity_use)):
        if consumption[i] is None:
            consumption[i] = 0  # Handle None values in consumption
        total_electricity_use[i] += consumption[i]
    return total_electricity_use

def check_system_type_to_get_consumption(system_name,consumption_profile):
    # print(type(consumption_profile))
    # print(consumption_profile.keys())
    system_type=None
    if system_name == cte.DHW_SYSTEM_ID:
        consumption = consumption_profile[cte.DHW_CONSUMPTION].copy()
        system_type=cte.DHW_SYSTEM
    elif system_name == cte.HEATING_SYSTEM_ID:
        consumption = consumption_profile[cte.HEAT_CONSUMPTION].copy()
        system_type=cte.HEATING_SYSTEM
    elif system_name == cte.COOLING_SYSTEM_ID:
        consumption = consumption_profile[cte.COOL_CONSUMPTION].copy()
        system_type=cte.COOLING_SYSTEM
    else:
        consumption=[0]*8760
        system_type=cte.ELECTRICITY_SYSTEM
    return consumption, system_type

def instantiate_final_energy_with_json():
    parent_directory = os.path.dirname(os.path.abspath(__file__))
    json_file_path = os.path.join(parent_directory,
                                  "catalogues", "energy_carrier.json")
    with open(json_file_path, "r") as file:
        json_data = json.load(file)

    total_final_energy = {} #diccionario de instancias de la clase Final Energy para cada energy carrier
    for entry in json_data:
        if entry.get("final"):
            id = entry[cte.ID]
            total_final_energy[id] = FinalEnergy(id)
            total_final_energy[id].name = entry["name"]
            total_final_energy[id].final = entry["final"]

    return total_final_energy

def load_energy_system_catalogue():
    parent_directory = os.path.dirname(os.path.abspath(__file__))
    input_files_path = os.path.join(parent_directory,"catalogues",
                                    "generation_systems_catalogue.json")
    with open(input_files_path, "r") as file:
        energy_systems_catalogue = json.load(file)
    return energy_systems_catalogue

def filter_energy_systems_catalogue(energy_systems_catalogue, new_generation_system_id):
    # Loop through each system in the "systems" list
    for system in energy_systems_catalogue:
        # Check if the ID in the system matches the new_generation_system_id
        if system[cte.ID] == new_generation_system_id:
            return system  # Return the matching system dictionary

    return None  # Return None if no matching system is found

def calculate_building_indicators(consumption_profile,
                                  generation_system_profile,
                                  building_energy_asset,
                                  timestep_count,
                                  building_use_id):
    """

    Parameters
    ----------
    consumption_profile is the dictionary of consumption, typically:
        BUILDING_CONSUMPTION:{
            ID: int,
            HEAT_CONSUMPTION:[],
            DHW_CONSUMPTION:[],
            ELECTRICITY_CONSUMPTION:[],
            COOL_CONSUMPTION:[]
            }
    generation_system_profile is the dictionary of the energy systems
    building_energy_asset is a list of several assets

    Returns
    -------

    """
    #initilize:
    rate_of_self_consumption = []
    grid_consumption = []
    self_sufficiency = []
    total_electricity_use = []
    list_of_hps = [1, 2, 3, 4, 5, 6, 7, 8, 27, 28, 29, 30, 31, 32, 33, 34, 35, 36, 41, 61, 62, 63, 64, 65, 66,
                   67, 68, 73]
    #dhn 145, 147, 153, 155 is out of the list as el. is consumed somewhere else
    cooling_hps_list = [1, 2, 3, 4, 5, 6, 7, 8]
    heating_hps_list = [61, 62, 63, 64, 65, 66, 67, 68, 73]
    dhw_hps_list = [27, 28, 29, 30, 31, 32, 33, 34, 35, 36, 41]
    chp_list = [88, 89, 90, 91]
    electric_asset_list = [80, 81, 82, 83, 84, 85, 86, 87]
    solar_thermal = [37, 38, 39, 40, 69, 70, 71, 72]
    #any other id is a boiler?????
    total_fuels_use={}
    cooling_asset = False
    heating_asset = False
    dhw_asset = False
    electricity_asset = False
    total_final_energy=instantiate_final_energy_with_json()
    energy_systems_catalogue=load_energy_system_catalogue()
    consumption=[]
    costs={}
    if building_energy_asset is not None:
        # Initialize total_electricity_use with the base consumption profile
        total_electricity_use = consumption_profile.get(cte.ELECTRICITY_CONSUMPTION, [])
        for asset in building_energy_asset:
            if asset[cte.GENERATION_SYSTEM_ID] in list_of_hps:
                # Perform element-wise summation for time_series_input1
                time_series_input1_values =asset[cte.AVAILABILITY_TS][cte.VALUE_INPUT1].copy()
                total_electricity_use = [
                            total_electricity_use[i] + time_series_input1_values[i]
                            for i in range(len(total_electricity_use))
                        ]
                if asset[cte.GENERATION_SYSTEM_ID] in cooling_hps_list:
                    cooling_asset = True
                if asset[cte.GENERATION_SYSTEM_ID] in dhw_hps_list:
                    dhw_asset = True
                if asset[cte.GENERATION_SYSTEM_ID] in heating_hps_list:
                    heating_asset = True
            #faltan los sistemas que se están optimizando (gas boilers, biomass boilers) y que no son heat pumps

        for system_name, system_id in generation_system_profile.items():
            # Check if the value is an integer (system ID)
            if not isinstance(system_id, int):
                continue  # Skip if the value is not an integer
            #System_id is an integer, you can safely check it
            #Get consumption
            consumption, system_type=check_system_type_to_get_consumption(system_name, consumption_profile)
            if system_name == cte.DHW_SYSTEM_ID and system_id in dhw_hps_list and dhw_asset == False:
                total_electricity_use = add_electricity_consumption(total_electricity_use, consumption)
            elif system_name ==cte.HEATING_SYSTEM_ID and system_id in heating_hps_list and heating_asset == False:
                total_electricity_use = add_electricity_consumption(total_electricity_use, consumption)
            elif system_name ==cte.COOLING_SYSTEM_ID and system_id in cooling_hps_list and cooling_asset == False:
                #If cooling_system_id is in list_of_new_hps and is not already found in asset["generation_system_id],
                # the program will proceed to sum the corresponding cool_consumption values with total_electricity_use for each hour.
                total_electricity_use = add_electricity_consumption(total_electricity_use, consumption)
            elif system_name == cte.DHW_SYSTEM_ID and dhw_asset == False and generation_system_profile[system_type] is not None:
                fuels_id=generation_system_profile[system_type][cte.ENERGY_CARRIER_INPUT1_ID ]
                total_final_energy[fuels_id].add_new_consumption(consumption)
            elif system_name == cte.HEATING_SYSTEM_ID and heating_asset == False and generation_system_profile[system_type] is not None:
                fuels_id=generation_system_profile[system_type][cte.ENERGY_CARRIER_INPUT1_ID ]
                total_final_energy[fuels_id].add_new_consumption(consumption)
            elif system_name == cte.COOLING_SYSTEM_ID and cooling_asset == False and generation_system_profile[system_type] is not None:
                fuels_id=generation_system_profile[system_type][cte.ENERGY_CARRIER_INPUT1_ID ]
                total_final_energy[fuels_id].add_new_consumption(consumption)

        for asset in building_energy_asset:
            if asset[cte.GENERATION_SYSTEM_ID] in electric_asset_list:
                # PV system, scale output by pmax_scalar
                # Perform element-wise summation for time_series_input1
                time_series_input1_values =asset[cte.AVAILABILITY_TS][cte.VALUE_INPUT1].copy()
                # Handle None by replacing it with 0
                pmax_scalar = asset[cte.PMAX_SCALAR] if asset[cte.PMAX_SCALAR] is not None else 0

                total_PV = [x * pmax_scalar for x in time_series_input1_values]
                electricity_asset = True
                # Calculate self-consumption
                self_consumption = calculate_self_consumption(total_electricity_use, total_PV)

                # Calculate rate of self-consumption
                rate_of_self_consumption = calculate_rate_of_self_consumption(self_consumption, total_PV)

                # Calculate grid consumption
                grid_consumption = calculate_grid_consumption(total_electricity_use, self_consumption)

                #Calculate self-sufficiency
                self_sufficiency = calculate_self_sufficiency(self_consumption, total_electricity_use)


            if asset[cte.GENERATION_SYSTEM_ID] not in list_of_hps and asset[
                cte.GENERATION_SYSTEM_ID] not in electric_asset_list:
                    time_series_input1_values = asset[cte.AVAILABILITY_TS][cte.VALUE_INPUT1].copy()
                    total_input1 = [x * asset[cte.PMAX_SCALAR] for x in time_series_input1_values]
                    system = filter_energy_systems_catalogue(energy_systems_catalogue, asset[cte.GENERATION_SYSTEM_ID])
                    fuels_id=int(system[cte.ENERGY_CARRIER_INPUT1_ID ])
                    total_final_energy[fuels_id].add_new_consumption(total_input1)

        if electricity_asset == False:
            # If no electricity asset, set grid_consumption equal to total_electricity_use
            grid_consumption = total_electricity_use
            # Set rate_of_self_consumption and self_sufficiency to lists of 8760 zeros
            self_consumption = [0] * timestep_count
            rate_of_self_consumption = [0] * timestep_count
            self_sufficiency = [0] * timestep_count
            total_PV =[0] * timestep_count
    else:
        #there is no asset in this building
        # Initialize total_electricity_use with the base consumption profile
        total_electricity_use = consumption_profile[cte.ELECTRICITY_CONSUMPTION].copy()
        for system_name, system_id in generation_system_profile.items():
            # Check if the value is an integer (system ID)
            if not isinstance(system_id, int):
                continue  # Skip if the value is not an integer
            # Get consumption
            consumption, system_type = check_system_type_to_get_consumption(system_name, consumption_profile)
                # Now, system_id is an integer, and you can safely check it
            if system_name == cte.DHW_SYSTEM_ID and system_id in dhw_hps_list:
                total_electricity_use = add_electricity_consumption(total_electricity_use, consumption)
            elif system_name == cte.HEATING_SYSTEM_ID and system_id in heating_hps_list:
                total_electricity_use = add_electricity_consumption(total_electricity_use, consumption)
            elif system_name == cte.COOLING_SYSTEM_ID and system_id in cooling_hps_list:
                total_electricity_use = add_electricity_consumption(total_electricity_use, consumption)
            elif system_name == cte.ELECTRICITY_SYSTEM_ID and system_id == 79:
                # This is the grid
                # grid_consumption equal to total_electricity_use
                grid_consumption = total_electricity_use
                # Set rate_of_self_consumption and self_sufficiency to lists of 8760 zeros
                self_consumption = [0] * timestep_count
                rate_of_self_consumption = [0] * timestep_count
                self_sufficiency = [0] * timestep_count
                total_PV =[0] * timestep_count
            #consumption_profile
            else:
                #this means is not a heat pump nor electricity grid but other type of system, therefore:
                if generation_system_profile[system_type] is not None:
                    fuels_id=generation_system_profile[system_type][cte.ENERGY_CARRIER_INPUT1_ID ]
                    total_final_energy[fuels_id].add_new_consumption(consumption)

    total_final_energy[12].add_new_consumption(grid_consumption)
    KPIs = {}  # Dictionary to store the BuildingKPIs objects

    # Loop through the generation_system_profile
    for system_name, system in generation_system_profile.items():
        if system_name.endswith(
                "_system") and system is not None:  # Check if system ends with "_system" and is not None
            if cte.ENERGY_CARRIER_INPUT1 in system and system[cte.ENERGY_CARRIER_INPUT1].get("final") == True:
                # Get the ID and KPI data
                energy_carrier_id = system[cte.ENERGY_CARRIER_INPUT1][cte.ID]
                data = system[cte.ENERGY_CARRIER_INPUT1][cte.NATIONAL_ENERGY_CARRIER_DATA]
                target_country_id = 27  # Replace with the desired country_id, e.g., 31
                # Handle both list and single dictionary cases
                if isinstance(data, list):
                    # Look for a match in the list
                    kpi_data = next((item for item in data if item['country_id'] == target_country_id), None)
                    if kpi_data is None:  # If no match is found, use `country_id=31`
                        kpi_data = next((item for item in data if item['country_id'] == 31), None)
                else:
                    # Single dictionary case: Check if `country_id` matches
                    if data['country_id'] == target_country_id:
                        kpi_data = data
                    else:  # Use `country_id=31` if no match
                        kpi_data = data if data['country_id'] == 31 else None
                    #kpi_data = {'pef_nren': float,
                    # 'f_co2_eq_g_kwh': float,
                    # 'non_h_costs_eur_kwh': float,
                    # 'country_id': int,
                    #  'energy_carrier_id': int,
                    #  'id': int,
                    #  'pef_tot': float,
                    #  'pef_ren': float,
                    #  'house_costs_eur_kwh': float,
                    #  'reference': 'string of reference'}
                # Check if `kpi_data` is still None (no fallback found)
                if kpi_data is None:
                    raise ValueError("No matching or fallback country_id found in the data.")

                if kpi_data is not None:
                    KPIs[energy_carrier_id] = BuildingKPIs(total_final_energy[energy_carrier_id], kpi_data)
                    if energy_carrier_id==12:
                        cost_of_electricity_household = kpi_data.get("house_costs_eur_kwh", 0) if kpi_data.get(
                            "house_costs_eur_kwh") is not None else 0
                        cost_of_electricity_non_household = kpi_data.get("non_h_costs_eur_kwh", 0) if kpi_data.get(
                            "non_h_costs_eur_kwh") is not None else 0

    for asset in building_energy_asset:
        if asset.get(cte.GENERATION_SYSTEM_ID,0)==83:
            if building_use_id in [1, 2, 3]:
                # print('to be modified in the future')
                total_energy_costs_now=KPIs[12].household_costs_yearly
                total_energy_costs_baseline=(sum(self_consumption)+sum(grid_consumption))*cost_of_electricity_household
                costs = calculate_costs(capacity=asset[cte.PMAX_SCALAR],
                                                              generation_system_id=83,
                                                              generation_time_series=total_PV,
                                                              total_energy_costs_now=total_energy_costs_now,
                                                              total_energy_costs_baseline=total_energy_costs_baseline
                                                              )
            else:
                total_energy_costs_now = KPIs[12].non_h_costs_yearly
                total_energy_costs_baseline = (sum(self_consumption) + sum(
                    grid_consumption)) * cost_of_electricity_non_household
                costs = calculate_costs(capacity=asset[cte.PMAX_SCALAR],
                                                              generation_system_id=83,
                                                              generation_time_series=total_PV,
                                                              total_energy_costs_now=total_energy_costs_now,
                                                              total_energy_costs_baseline=total_energy_costs_baseline
                                                              )
            #     total_energy_cost = sum(total_non_h_costs)
            # area_building = building_asset_context.get(BUILDING, {}).get(AREA)
            #

    return (total_PV,rate_of_self_consumption, self_sufficiency, total_electricity_use, self_consumption,
            total_final_energy, KPIs, costs)

def aggregate_demand_profiles(demand_profile):
    # Initialize a dictionary to store the aggregated demand
    total_demand = {}
    # Check if demand_profile is a list or a dictionary
    if isinstance(demand_profile, list):
        # Loop over each building"s demand profile in the list
        for building in demand_profile:
            # Get the specific demand profile dictionary for each building
            profile = building.get(cte.DEMAND_PROFILE, {})

            # Loop through each demand type in the building"s demand profile
            for demand_type, demand_values in profile.items():
                # If the demand type is already in total_demand, sum it element-wise
                if demand_type in total_demand:
                    total_demand[demand_type] = [
                        total_demand[demand_type][i] + demand_values[i]
                        for i in range(len(demand_values))
                    ]
                else:
                    # If it"s the first occurrence, initialize it in total_demand
                    total_demand[demand_type] = demand_values

    elif isinstance(demand_profile, dict):
        # If demand_profile is a single dictionary, process it directly
        for demand_type, demand_values in demand_profile.get(cte.DEMAND_PROFILE, {}).items():
            if demand_type in total_demand:
                total_demand[demand_type] = [
                    total_demand[demand_type][i] + demand_values[i]
                    for i in range(len(demand_values))
                ]
            else:
                total_demand[demand_type] = demand_values

    else:
        raise TypeError("demand_profile must be either a list or a dictionary.")

    return total_demand

def community_KPIs(citizen_KPIs,total_demand,areas_buildings):
    # Initialize an empty dictionary to hold the sum of each KPI
    aggregate_KPIs = {}
    # Define the KPIs requiring area-weighted aggregation
    area_weighted_kpis = [
        "total_primary_energy_intensity",
        "national_average_total_primary_energy_intensity",
        "total_CO2_intensity",
        "national_average_total_CO2_intensity",
        "total_energy_cost_intensity",
        "national_average_total_energy_cost_intensity"
    ]
    # Initialize storage for area-weighted KPI sums
    area_weighted_sums = {kpi: 0 for kpi in area_weighted_kpis}
    total_area = 0
    # Loop through each building"s KPI data in citizen_KPIs
    for building_id, kpis in citizen_KPIs.items():
        building_area = areas_buildings[building_id][cte.AREA]
        total_area += building_area
        for kpi in kpis:
            kpi_name = kpi["name"]
            kpi_value = kpi["value"]
            # Area-weighted aggregation
            if kpi_name in area_weighted_kpis:
                area_weighted_sums[kpi_name] += kpi_value * building_area
                # Standard aggregation for numeric values
            elif isinstance(kpi_value, (int, float)):
                if kpi_name in aggregate_KPIs:
                    aggregate_KPIs[kpi_name]["value"] += kpi_value
                else:
                    aggregate_KPIs[kpi_name] = {"value": kpi_value, "unit": kpi["unit"]}

            # Time-series aggregation
            elif isinstance(kpi_value, list):
                timestep_count = len(kpi_value)
                if kpi_name in aggregate_KPIs:
                    aggregate_KPIs[kpi_name]["value"] = [
                        aggregate_KPIs[kpi_name]["value"][i] + kpi_value[i]
                        for i in range(timestep_count)
                    ]
                else:
                    aggregate_KPIs[kpi_name] = {"value": kpi_value, "unit": kpi["unit"]}
    # Finalize area-weighted KPIs
    for kpi_name in area_weighted_kpis:
        # Find the first occurrence of the KPI in citizen_KPIs to extract its unit
        unit = next(
            (kpi["unit"] for building_kpis in citizen_KPIs.values()
             for kpi in building_kpis if kpi["name"] == kpi_name),
            None
        )
        aggregate_KPIs[kpi_name] = {
            "value": area_weighted_sums[kpi_name] / total_area,
            "unit": unit if unit else "N/A"
        }

    aggregate_KPIs["KPI_peak_heat_demand_[kWh]"]={"value": max(total_demand[cte.HEATING_DEMAND]),"unit": "kWh"}
    aggregate_KPIs["KPI_peak_dhw_demand_[kWh]"]={"value":max(total_demand[cte.DHW_DEMAND]),"unit": "kWh"}
    aggregate_KPIs["KPI_peak_cooling_demand_[kWh]"]={"value": max(total_demand[cte.COOLING_DEMAND]),"unit": "kWh"}
    aggregate_KPIs["KPI_peak_elec_demand_[kWh]"]={"value": max(total_demand[cte.ELECTRICITY_DEMAND]),"unit": "kWh"}
    aggregate_KPIs["KPI_peak_electricity_consumption_[kWh]"]={"value": max(aggregate_KPIs[cte.FINAL_ENERGY_ELECTRICITY_GRID]["value"]),"unit": "kWh"}
    # `aggregate_KPIs` now contains the summed values for each KPI across all buildings
    return aggregate_KPIs

def get_totals_per_building (KPIs,timestep_count,final_energy):
    """

    Parameters
    ----------
    KPIs
    timestep_count
    final_energy

    Returns
    -------

    """
    # Initialize totals for the current building
    total_primary_energy= [0] * timestep_count
    total_primary_energy_renewable = [0] * timestep_count
    total_primary_energy_non_renewable = [0] * timestep_count
    total_non_h_costs = [0] * timestep_count
    total_h_costs = [0] * timestep_count
    total_co2= [0] * timestep_count
    for id_carrier, energy_instance in KPIs.items():
        if energy_instance is not None:
            # Use dot notation to access the energy instance attributes
            total_primary_energy = [
                total_primary_energy[i] + energy_instance.PEF_total[i]
                for i in range(timestep_count)
            ]

            total_primary_energy_renewable = [
                total_primary_energy_renewable[i] + energy_instance.PEF_ren[i]
                for i in range(timestep_count)
            ]

            total_primary_energy_non_renewable = [
                total_primary_energy_non_renewable[i] + energy_instance.PEF_nren[i]
                for i in range(timestep_count)
            ]

            total_non_h_costs = [
                total_non_h_costs[i] + energy_instance.non_h_costs[i]
                for i in range(timestep_count)
            ]

            total_h_costs= [
                total_h_costs[i] + energy_instance.household_costs[i]
                for i in range(timestep_count)
            ]

            total_co2 = [
                total_co2[i] + energy_instance.co2[i]
                for i in range(timestep_count)
            ]
    total_primary_energy_kWh = total_primary_energy  # it is already in kWh unless we decide otherwise
    total_co2_kg = [x / 1000 for x in total_co2]
    # Extract dictionary of citizen_kpis_factors
    citizen_kpis_factors = kpi_ctz_factors()
    # KPI Equivalent TV hours
    TV_h = tv_h(citizen_kpis_factors=citizen_kpis_factors,
                total_primary_energy=total_primary_energy_kWh)
    # KPI Equivalent streaming hours
    streaming_hours = streaming_h(citizen_kpis_factors=citizen_kpis_factors,
                                  total_primary_energy=total_primary_energy_kWh)
    # KPI equivalent pizza items
    Pizza_h = pizza_h(citizen_kpis_factors=citizen_kpis_factors,
                      total_primary_energy=total_primary_energy_kWh)
    # Equivalent battery usage estimation
    Battery_charges = battery_charges(citizen_kpis_factors=citizen_kpis_factors,
                                      total_primary_energy=total_primary_energy_kWh)
    # Equivalent electric car charging times
    ElCar_charges = el_car_charges(citizen_kpis_factors=citizen_kpis_factors,
                                   total_primary_energy=total_primary_energy_kWh)
    # Equivalent trees - - CO2
    Trees_number = trees_number(citizen_kpis_factors=citizen_kpis_factors, total_co2=total_co2_kg)

    # Equivalent Streaming impact in emissions - - CO2
    streaming_emissionhours = streaming_emission_hours(citizen_kpis_factors=citizen_kpis_factors,
                                                       total_co2=total_co2_kg)
    # - - CO2
    ICV_km = icv_km(citizen_kpis_factors=citizen_kpis_factors, total_co2=total_co2_kg)
    # Equivalent wine bottles produced - - CO2
    Wine_bottles = wine_bottles(citizen_kpis_factors=citizen_kpis_factors,
                                total_primary_energy=total_primary_energy_kWh)
    FinalEnergy_dic = {}

    for key, energy_instance in final_energy.items():
        # Check if there"s any non-zero value in hourly_data
        if any(value > 0 for value in energy_instance.hourly_data):
            # Add to the dictionary with the appropriate name as key
            FinalEnergy_dic[f"final_energy_{energy_instance.name}"] = energy_instance.hourly_data

    return (total_primary_energy_kWh, total_co2,total_primary_energy_non_renewable, total_primary_energy_renewable,
            total_h_costs, total_non_h_costs, TV_h, streaming_hours, Pizza_h, Battery_charges, ElCar_charges, Trees_number,
            streaming_emissionhours, ICV_km, Wine_bottles,FinalEnergy_dic)

def filter_function(df, variable, building_use_id, construction_year, country_id):
    try:
        # Step 1: Full match
        df_filtered = df[
            (df[cte.BUILDING_USE_ID] == int(building_use_id)) &
            (df[cte.CONSTRUCTION_YEAR] == int(construction_year)) &
            (df[cte.COUNTRY_ID] == float(country_id))
        ][variable].values
        # Step 2: Match without construction_year
        if len(df_filtered) == 0:
            df_filtered = df[
                (df["building_use_id"] == building_use_id) &
                (df["country_id"] == country_id)
                ][variable].values

        # Step 3: Match with country_id set to 31
        if len(df_filtered) == 0:
            df_filtered = df[
                (df["building_use_id"] == building_use_id) &
                (df["country_id"] == 31)
                ][variable].values

        # Step 4: Return default if still empty
        if len(df_filtered) == 0:
            if variable == "total_primary_energy_intensity":
                return 234.87
            elif variable == "total_energy_cost_intensity":
                return 22
            elif variable == "total_CO2_intensity":
                return 43149.28568

        return df_filtered[0]
    except Exception as e:
        # print(f"Error during filtering in {variable}: {e}")
        if variable == "total_primary_energy_intensity":
            return 234.87
        elif variable == "total_energy_cost_intensity":
            return 22
        elif variable == "total_CO2_intensity":
            return 43149.28568

def filter_values(filename, building_use_id, construction_year, country_id):
    """

    Parameters
    ----------
    filename: total_primary_energy_GHG_costs_intensity.csv
    building_use_id
    construction_year
    country_id

    Returns
    -------
    National averages: total_primary_energy_intensity_filtered, total_energy_cost_filtered, total_CO2_filtered

    """
    # Cast input values to int if not None
    building_use_id = int(building_use_id) if building_use_id is not None else None
    construction_year = int(construction_year) if construction_year is not None else None
    country_id = int(country_id) if country_id is not None else None

    parent_directory = os.path.dirname(os.path.abspath(__file__))
    csv_path = os.path.join(parent_directory, "data", filename)

    try:
        # Read the CSV file
        df = pd.read_csv(csv_path)
    except FileNotFoundError:
        # print(f"Error: The file {filename} does not exist in the specified directory. , average values provided: 	234.87, 22, 43149.28568")
        return 234.87, 22, 43149.28568
    except Exception as e:
        # print(f"Error loading file {filename}: {e}")
        return 234.87, 22, 43149.28568



    # Ensure required columns are present
    required_columns = {"country_id","building_use_id", "construction_year", "total_primary_energy_intensity", "total_energy_cost_intensity", "total_CO2_intensity"}
    if not required_columns.issubset(df.columns):
        # print(f"Error: The file {filename} must contain the following columns: {required_columns}, average values provided: 	234.87, 22, 43149.28568")
        return 234.87, 22, 43149.28568
    # Cast relevant DataFrame columns to int
    df[cte.BUILDING_USE_ID] = df[cte.BUILDING_USE_ID].astype("Int64")
    df[cte.CONSTRUCTION_YEAR] = df[cte.CONSTRUCTION_YEAR].astype("Int64")
    df[cte.COUNTRY_ID] = df[cte.COUNTRY_ID].astype("Int64")

    try:
        # Perform filtering for each variable
        total_primary_energy_intensity_filtered = filter_function(
            df=df,
            variable="total_primary_energy_intensity",
            building_use_id=building_use_id,
            construction_year=construction_year,
            country_id=country_id,
        )
        total_energy_cost_filtered = filter_function(
            df=df,
            variable="total_energy_cost_intensity",
            building_use_id=building_use_id,
            construction_year=construction_year,
            country_id=country_id,
        )
        total_CO2_filtered = filter_function(
            df=df,
            variable="total_CO2_intensity",
            building_use_id=building_use_id,
            construction_year=construction_year,
            country_id=country_id,
        )
        if total_primary_energy_intensity_filtered is None:
            total_primary_energy_intensity_filtered= 234.87
        if total_energy_cost_filtered is None:
            total_energy_cost_filtered =22
        if total_CO2_filtered is None:
            total_CO2_filtered= 43149.28568

        return total_primary_energy_intensity_filtered, total_energy_cost_filtered, total_CO2_filtered
    except Exception as e:
        # print(f"Error during filtering: {e}, average values provided: 	234.87, 22, 43149.28568")
        return 234.87, 22, 43149.28568

def get_indicators_from_baseline(front_data, data, building_consumption_dict, demand_profile):
    """

    Parameters
    ----------
    front_data = {
    data
    building_consumption_dict

    Returns
    -------

    """
    rate_of_self_consumption = {}
    self_sufficiency = {}
    total_electricity_use = {}
    self_consumption = {}
    total_final_energy = {}
    total_PV = {}
    # groups
    KPIs = {}
    citizen_KPIs = {}
    costs={}
    # Define the number of hours for each month (non-leap year)
    hours_per_month = {
        "January": 744, "February": 672, "March": 744, "April": 720,
        "May": 744, "June": 720, "July": 744, "August": 744,
        "September": 720, "October": 744, "November": 720, "December": 744
    }

    # Total hours in a day
    hours_per_day = 24
    areas_buildings={}

    for i, item in enumerate(front_data):
        # Case 1: building_statistics_profile_id is in front_data and there is a loop for each item in front_data (per building)
        if "building_statistics_profile_id" in item:
            building_statistics_profile_id = item["building_statistics_profile_id"]
            building_profile = next(
                (profile for profile in data if profile.get(cte.ID) == building_statistics_profile_id), None)

            if building_profile is None:
                raise ValueError(
                    f"No se encontró el perfil de estadísticas del edificio con id {building_statistics_profile_id}")

            generation_system_profile = building_profile.get(cte.GENERATION_SYSTEM_PROFILE, {})
            building_use_id = item.get(cte.BUILDING_USE_ID)
            construction_year= item.get(cte.CONSTRUCTION_YEAR)
            # Check the type of item["geom"] and process accordingly
            if isinstance(item["geom"], str):
                # If it's a string, assume it's WKT and convert it to a Shapely geometry object
                wkt_geom = item["geom"]
                geom = wkt.loads(wkt_geom)
            else:
                # Otherwise, assume it's a GeoJSON-like dictionary and use shape()
                geom = shape(item["geom"])
            area_building = geom.area
            # Check if area_building is 0 and assign 100 if true
            if area_building < 10:
                area_building = 100
        else:
            # Else case: No "building_statistics_profile_id" found, we use the "building_statistics_profile"
            building_statistics_profiles = data.get("building_statistics_profile", [])
            generation_system_profile = building_statistics_profiles.get(cte.GENERATION_SYSTEM_PROFILE, {})
            building_use_id = front_data.get(cte.BUILDING_USE_ID)
            construction_year = front_data.get(cte.CONSTRUCTION_YEAR)
            if isinstance(front_data["location"], str):
                # If it's a string, assume it's WKT and convert it to a Shapely geometry object
                wkt_geom = front_data["location"]
                geom = wkt.loads(wkt_geom)
            else:
                # Otherwise, assume it's a GeoJSON-like dictionary and use shape()
                geom = shape(front_data["location"])
            area_building = geom.area
            # Check if area_building is 0 and assign 100 if true
            if area_building < 10:
                area_building = 100 * front_data["num_building"]

            if isinstance(building_statistics_profiles, dict):
                building_statistics_profiles = [building_statistics_profiles]

        building_id=i+1
        areas_buildings[building_id] = {}
        areas_buildings[building_id][cte.AREA] = area_building
        # Get the consumption data for each type of generation system (8760 hourly values)
        # Fetch the building consumption
        building_consumption = building_consumption_dict.get(f"building_id_{i + 1}", {})
        # Check if the retrieved value is empty; if so, get the value for "building_id_1"
        if not building_consumption:
            building_consumption = building_consumption_dict.get("building_id_1", {})

        heating_consumption = building_consumption.get(cte.HEAT_CONSUMPTION, [0] * 8760)
        electricity_consumption = building_consumption.get(cte.ELECTRICITY_CONSUMPTION, [0] * 8760)
        cooling_consumption = building_consumption.get(cte.COOL_CONSUMPTION, [0] * 8760)
        dhw_consumption = building_consumption.get(cte.DHW_CONSUMPTION, [0] * 8760)

        # Check if demand_profile contains multiple buildings or a single building
        if isinstance(demand_profile, list):
            # Multiple buildings: loop through each building
            demand_profile_building = demand_profile[i]
            demand_profile_building = demand_profile_building[cte.DEMAND_PROFILE]
        else:
            # Single building case
            demand_profile_building = demand_profile[cte.DEMAND_PROFILE]
            # Process the single building profile here

        # Define the systems to process (linking them to the profiles)
        systems = {
            cte.HEATING_SYSTEM: heating_consumption,
            "electricity_system": electricity_consumption,
            cte.COOLING_SYSTEM: cooling_consumption,
            cte.DHW_SYSTEM: dhw_consumption
        }

        building_energy_asset=[]
        (
            total_PV[building_id],
            rate_of_self_consumption[building_id],
            self_sufficiency[building_id],
            total_electricity_use[building_id],
            self_consumption[building_id],
            total_final_energy[building_id],
            KPIs[building_id],
            costs[building_id]
        ) = calculate_building_indicators(consumption_profile=building_consumption,
                                          generation_system_profile=generation_system_profile,
                                          building_energy_asset=building_energy_asset,
                                          timestep_count=len(dhw_consumption),
                                          building_use_id=building_use_id)

        (total_primary_energy_kWh, total_co2, total_primary_energy_non_renewable, total_primary_energy_renewable,
         total_h_costs, total_non_h_costs, TV_h, streaming_hours, Pizza_h, Battery_charges, ElCar_charges, Trees_number,
         streaming_emissionhours, ICV_km, Wine_bottles, FinalEnergy_dic) = get_totals_per_building(KPIs[building_id],
                                                                                                   timestep_count=len(
                                                                                                       dhw_consumption),
                                                                                                   final_energy=
                                                                                                   total_final_energy[
                                                                                                           building_id])
        KPI_peak_heat_demand = max(demand_profile_building[cte.HEATING_DEMAND])
        # calculate peak cooling demand
        KPI_peak_elec_demand = max(total_electricity_use[building_id])

        # Extract country_id from generation_system_profile
        try:
            country_id = generation_system_profile[cte.ELECTRICITY_SYSTEM][cte.ENERGY_CARRIER_INPUT1][
                cte.NATIONAL_ENERGY_CARRIER_DATA][0][cte.COUNTRY_ID]
        except (KeyError, IndexError, TypeError):
            print(f"Error: Unable to extract {cte.COUNTRY_ID} from {cte.GENERATION_SYSTEM_PROFILE}.")
            country_id = None

        national_average_total_primary_energy_intensity, national_average_total_CO2, national_average_total_energy_cost = filter_values(
            filename="total_primary_energy_GHG_costs_intensity.csv",
            building_use_id=building_use_id,
            construction_year=construction_year,
            country_id=country_id)


        # building_use_mapping = {
        #     1: "residential",  # residential
        #     2: "residential",  # residential
        #     3: "residential",  # residential
        #     4: "office",  # office
        #     5: "commerce",  # commerce
        #     6: "education",  # education
        # }
        if building_use_id in [1, 2, 3]:
            total_energy_cost = sum(total_h_costs)
        else:
            total_energy_cost = sum(total_non_h_costs)

        if area_building > 0:
            total_primary_energy_intensity_kWh = sum(total_primary_energy_kWh) / area_building
            total_co2_intensity = sum(total_co2) / area_building
            total_energy_cost_intensity = total_energy_cost / area_building
        else:
            area_building = 1
            total_primary_energy_intensity_kWh = sum(total_primary_energy_kWh) / area_building
            total_co2_intensity = sum(total_co2) / area_building
            total_energy_cost_intensity = total_energy_cost / area_building


        # Store citizen KPIs for the building
        citizen_KPIs[building_id] = [
            {cte.ID: 1, "name": "KPI_peak_heat_demand_[kWh]", "value": KPI_peak_heat_demand, "unit": "kWh"},
            {cte.ID: 2, "name": "KPI_peak_elec_demand_[kWh]", "value": KPI_peak_elec_demand, "unit": "kWh"},
            {cte.ID: 3, "name": "total_primary_energy_[kWh]", "value": total_primary_energy_kWh,
             "unit": "kWh"},
            {cte.ID: 4, "name": "num_members", "value": 0, "unit": "a.u."},
            {cte.ID: 5, "name": "EquivalentTVHours_[h]", "value": TV_h, "unit": "h"},
            {cte.ID: 6, "name": "EquivalentstreamingHours_[h]", "value": streaming_hours, "unit": "h"},
            {cte.ID: 7, "name": "PizzaConsumptionComparison_[pizza]", "value": Pizza_h, "unit": "pizza"},
            {cte.ID: 8, "name": "BatteryUsageEstimation_[charges]", "value": Battery_charges,
             "unit": "charges"},
            {cte.ID: 9, "name": "ElectricCarChargingEstimation_[charges]", "value": ElCar_charges,
             "unit": "charges"},
            {cte.ID: 10, "name": "WineBottlesProduction_[bottles]", "value": Wine_bottles, "unit": "bottles"},
            {cte.ID: 11, "name": "TreesRequiredForCarbonOffset_[trees]", "value": Trees_number,
             "unit": "trees"},
            {cte.ID: 12, "name": "streamingEmissionsImpact_[hours]", "value": streaming_emissionhours,
             "unit": "hours"},
            {cte.ID: 13, "name": "CarbonEmissionsPerKilometer_[km]", "value": ICV_km, "unit": "km"},
            {cte.ID: 14, "name": "Total_PV_[kWh]", "value": total_PV[building_id], "unit": "kWh"},
            {cte.ID: 15, "name": "Total_self_consumption", "value": self_consumption[building_id], "unit": "a.u."},
            {cte.ID: 16, "name": "Total_self_sufficiency", "value": self_sufficiency[building_id], "unit": "a.u."},
            {cte.ID: 17, "name": "rate_of_self_consumption", "value": rate_of_self_consumption[building_id],
             "unit": "%"},
            {cte.ID: 18, "name": "renewable_primary_energy_[kWh]",
             "value": total_primary_energy_renewable[building_id], "unit": "kWh"},
            {cte.ID: 19, "name": "non_renewable_primary_energy_[kWh]",
             "value": total_primary_energy_non_renewable[building_id], "unit": "kWh"},
            {cte.ID: 20, "name": "non_households_costs_[€]", "value": total_non_h_costs[building_id], "unit": "€"},
            {cte.ID: 21, "name": "households_costs_[€]", "value": total_h_costs[building_id], "unit": "€"},
            {cte.ID: 22, "name": "Total_co2", "value": total_co2, "unit": "g CO2eq"},
            {cte.ID: 23, "name": "total_primary_energy_intensity", "value": total_primary_energy_intensity_kWh,
             "unit": "kWh/m2"},
            {cte.ID: 24, "name": "national_average_total_primary_energy_intensity",
             "value": national_average_total_primary_energy_intensity, "unit": "kWh/m2"},
            {cte.ID: 25, "name": "total_CO2_intensity", "value": total_co2_intensity, "unit": "g/m2"},
            {cte.ID: 26, "name": "national_average_total_CO2_intensity", "value": national_average_total_CO2,
             "unit": "g/m2"},
            {cte.ID: 27, "name": "total_energy_cost_intensity", "value": total_energy_cost_intensity, "unit": "€/m2"},
            {cte.ID: 28, "name": "national_average_total_energy_cost_intensity",
             "value": national_average_total_energy_cost, "unit": "€/m2"}
        ]
        id_for_citizen_kpi = 29
        for key, energy_instance in FinalEnergy_dic.items():
            citizen_KPIs[building_id].append(
                {cte.ID: id_for_citizen_kpi, "name": key, "value": energy_instance, "unit": "kWh"})
            id_for_citizen_kpi += 1


    return citizen_KPIs, areas_buildings


# Function to calculate Net Present Value (NPV) of cash flows
def calculate_npv(cash_flows, discount_rate):
    """
    Calculate the Net Present Value (NPV) of a series of cash flows.

    Parameters:
    - cash_flows: List of cash flows (e.g., annual OPEX or generation).
    - discount_rate: The discount rate for NPV calculation.

    Returns:
    - NPV of the cash flows.
    """
    return sum(cf / ((1 + discount_rate) ** year) for year, cf in enumerate(cash_flows, start=1))

# Function to calculate total CAPEX
def calculate_total_capex(capacity, capex_per_kw):
    """
    Calculate total capital expenditure (CAPEX).

    Parameters:
    - capacity: Installed power capacity in kW.
    - capex_per_kw: Capital cost per kW in EUR.

    Returns:
    - Total CAPEX in EUR.
    """
    return capacity * capex_per_kw


# Function to calculate annual OPEX
def calculate_annual_opex(annual_generation, opex_per_kwh):
    """
    Calculate annual operating expenses (OPEX).

    Parameters:
    - annual_generation: Total electricity generation per year in kWh.
    - opex_per_kwh: Operating cost per kWh in EUR.

    Returns:
    - Annual OPEX in EUR.
    """
    return annual_generation * opex_per_kwh


# Function to calculate total lifetime costs
def calculate_total_lifetime_costs(capex, npv_opex):
    """
    Calculate total lifetime costs by summing CAPEX and discounted OPEX.

    Parameters:
    - capex: Total initial capital expenditure in EUR.
    - npv_opex: Net Present Value of total OPEX in EUR.

    Returns:
    - Total lifetime costs in EUR.
    """
    return capex + npv_opex


# Function to calculate Levelized Cost of Electricity (LCOE)
def calculate_lcoe(total_lifetime_costs, npv_generation):
    """
    Calculate the Levelized Cost of Electricity (LCOE).

    Parameters:
    - total_lifetime_costs: Sum of CAPEX and discounted OPEX in EUR.
    - npv_generation: NPV of electricity generation in kWh.

    Returns:
    - LCOE in EUR per kWh.
    """
    if npv_generation == 0:
        raise ValueError("NPV of generation cannot be zero.")
    return total_lifetime_costs / npv_generation


# Function to calculate Payback Period
def calculate_payback_period(total_capex, annual_savings, lifetime):
    """
    Calculate the payback period in years.

    Parameters:
    - total_capex: Total capital expenditure in EUR.
    - annual_savings: Annual savings in EUR (baseline minus current).
    - lifetime: System lifetime in years.

    Returns:
    - Payback period in years, or None if not achievable within the lifetime.
    """
    if annual_savings <= 0:
        return None  # No payback achievable
    years = total_capex / annual_savings
    return years if years <= lifetime else None


# Main calculation function
def calculate_costs(capacity, generation_system_id, generation_time_series,
        total_energy_costs_baseline=None, total_energy_costs_now=None):
    """
    Calculate system costs, savings, and LCOE for a specific generation system.

    Parameters:
    - capacity: Installed power capacity in kW.
    - generation_system_id: ID of the selected energy generation system.
    - generation_time_series: List of annual energy production values in kWh/year.
    - total_energy_costs_baseline: Time-series baseline energy costs before system installation in EUR.
    - total_energy_costs_now: Time-series current energy costs after system installation in EUR.

    Returns:
    - A dictionary containing:
        - total_capex: Total CAPEX in EUR.
        - npv_opex_before: NPV of costs before system installation.
        - npv_opex_after: NPV of costs after system installation.
        - total_lifetime_costs: Total lifetime costs after installation.
        - lcoe: Levelized Cost of Electricity (LCOE) in EUR/kWh.
        - total_savings: Total savings compared to baseline in EUR.
        - payback_period_years: Payback period in years, or None if not achievable.
    """
    # Ensure generation_time_series is a valid list
    if generation_time_series is None:
        generation_time_series = [0]*8760
    # Handle missing time-series costs
    if total_energy_costs_baseline is None:
        total_energy_costs_baseline = [0] * len(generation_time_series)
    if total_energy_costs_now is None:
        total_energy_costs_now = [0] * len(generation_time_series)
    # Load system profile
    energy_systems_catalogue = load_energy_system_catalogue()
    system_profile = filter_energy_systems_catalogue(
        energy_systems_catalogue=energy_systems_catalogue,
        new_generation_system_id=generation_system_id)
    # Ensure system_profile is not None
    if system_profile is None:
        CAPEX = 1000  # Default: 1000 EUR/kW
        OPEX = 25  # Default: 25 EUR/kWh per year
        lifetime = 20  # Default: 20 years
    else:
        # Extract parameters with default fallback
        CAPEX = system_profile.get("capex_eur_kw", 1000)
        OPEX = system_profile.get("opex_eur_kwh_year", 25)
        lifetime = system_profile.get("lifetime_years", 20)
    if capacity is None:
        capacity=0
    discount_rate = 0.05
    # Calculate CAPEX
    total_capex = calculate_total_capex(capacity, CAPEX)
    # Total annual generation
    annual_generation = sum(generation_time_series)
    # Maintenance and operating costs
    annual_maintenance_cost = calculate_annual_opex(annual_generation=annual_generation, opex_per_kwh=OPEX)
    # Total energy costs per year
    annual_baseline_cost = sum(total_energy_costs_baseline) if isinstance(total_energy_costs_baseline,
                                                                          list) else total_energy_costs_baseline
    annual_current_cost = sum(total_energy_costs_now) if isinstance(total_energy_costs_now,
                                                                    list) else total_energy_costs_now
    # Ensure lifetime is a positive integer
    if lifetime is None or lifetime < 0:
        raise ValueError("Lifetime must be a positive integer.")
    lifetime = int(lifetime)

    # Cash flows for lifetime
    baseline_cash_flows = [annual_baseline_cost] * lifetime
    current_cash_flows = [annual_current_cost + annual_maintenance_cost] * lifetime

    # Calculate NPVs (result as floats)
    npv_opex_before = calculate_npv(baseline_cash_flows, discount_rate)
    npv_opex_after = calculate_npv(current_cash_flows, discount_rate)

    # Calculate total lifetime costs
    total_lifetime_costs = total_capex + npv_opex_after

    # Calculate total savings
    total_savings = npv_opex_before - npv_opex_after

    # Calculate LCOE
    npv_generation = calculate_npv([annual_generation] * lifetime, discount_rate)
    if npv_generation == 0:
        lcoe = None
    else:
        lcoe = calculate_lcoe(total_lifetime_costs, npv_generation)
    # Calculate payback period
    annual_savings = total_savings / lifetime

    # Calculate payback period
    if annual_savings <= 0:
        payback_period = None  # If no savings, no payback period
    else:
        payback_period = calculate_payback_period(total_capex, annual_savings, lifetime)

    # Return results
    return {
        "total_capex": total_capex,
        "npv_opex_before": npv_opex_before,
        "npv_opex_after": npv_opex_after,
        "total_lifetime_costs": total_lifetime_costs,
        "lcoe": lcoe,
        "total_savings": total_savings,
        "payback_period_years": payback_period
    }


def recalculate_indicators (community_context):
    #dictionary handlers for every KPI and every building
    rate_of_self_consumption={}
    self_sufficiency={}
    total_electricity_use={}
    self_consumption={}
    total_final_energy={}
    total_PV={}
    #groups of KPIs
    KPIs={}
    citizen_KPIs={}
    costs={}
    areas_buildings = {}
    # Totals
    hourly_KPIs = {}
    demand_profiles_context=[]
    if cte.BUILDING_ASSET_CONTEXT in community_context and isinstance(community_context[cte.BUILDING_ASSET_CONTEXT], list):
        for building_asset_context in community_context[cte.BUILDING_ASSET_CONTEXT]:
            building_id_increment=0
            # Check if GENERATION_SYSTEM_PROFILE_ID is in the building_dic
            if cte.GENERATION_SYSTEM_PROFILE_ID in building_asset_context:
                # Handle building_id: If it doesn"t exist, assign an incremented id
                building_id = building_asset_context.get(cte.ID, f"building_{building_id_increment + 1}")  # Incremental ID if missing
                # Handle consumption_profile: Raise an error if it doesn"t exist
                if cte.BUILDING_CONSUMPTION not in building_asset_context or building_asset_context[
                    cte.BUILDING_CONSUMPTION] is None:
                    raise ValueError(f"Consumption profile does not exist for building ID: {building_id}")
                consumption_profile = building_asset_context[cte.BUILDING_CONSUMPTION]
                # Handle timestep_count: If null, use the length of any of the consumption profile arrays
                timestep_count = community_context.get("timestep_count")
                if timestep_count is None:
                    if len(consumption_profile) > 0:
                        timestep_count = len(
                            next(iter(consumption_profile.values())))  # Length of first consumption array
                    else:
                        raise ValueError(f"Timestep count could not be determined for building ID: {building_id}")
                # Handle building_energy_asset: Assign None if it doesn"t exist
                building_energy_asset = building_asset_context.get("building_energy_asset", None)


                # Handle generation_system_profile: Assign None if it doesn"t exist
                generation_system_profile = building_asset_context.get(cte.GENERATION_SYSTEM_PROFILE, None)
                demand_profile=handle_demand_profile(building_asset_context,generation_system_profile,consumption_profile)
                demand_profiles_context.append({cte.DEMAND_PROFILE: demand_profile})
                building_use_id = building_asset_context.get(cte.BUILDING, {}).get(cte.BUILDING_USE_ID)
                # Further processing such as adding to KPIs, calculating other values, etc.
                #timestep_count=community_context["timestep_count"]
                #building_id = building_asset_context[ID]
                #building_energy_asset = building_asset_context["building_energy_asset"]
                #generation_system_profile = building_asset_context[GENERATION_SYSTEM_PROFILE]
                #consumption_profile = building_asset_context[BUILDING_CONSUMPTION]
                #demand_profile=building_asset_context[BUILDING][DEMANDPROFILE]
                hourly_KPIs[building_id] = {}
                # Calculate building indicators
                (
                    total_PV[building_id],
                    rate_of_self_consumption[building_id],
                    self_sufficiency[building_id],
                    total_electricity_use[building_id],
                    self_consumption[building_id],
                    total_final_energy[building_id],
                    KPIs[building_id],
                    costs[building_id]
                ) = calculate_building_indicators(consumption_profile, generation_system_profile, building_energy_asset,
                                                  timestep_count,building_use_id)

                # Add consumption_profile and demand_profile
                for key, value in consumption_profile.items():
                    hourly_KPIs[building_id].update({
                        f"consumption_profile_{key}": value})

                for key, value in demand_profile.items():
                    hourly_KPIs[building_id].update({
                        f"demand_profile_{key}" : value})
                building_id_increment+=1
            (total_primary_energy_kWh, total_co2, total_primary_energy_non_renewable, total_primary_energy_renewable,
             total_h_costs, total_non_h_costs, TV_h, streaming_hours, Pizza_h, Battery_charges, ElCar_charges,
             Trees_number,
             streaming_emissionhours, ICV_km, Wine_bottles, FinalEnergy_dic) = get_totals_per_building(KPIs[building_id],
                                                                                                       timestep_count=timestep_count,
                                                                                                       final_energy=total_final_energy[building_id])
            # calculate peak heat demand
            KPI_peak_heat_demand = max(demand_profile[cte.HEATING_DEMAND])
            # calculate peak cooling demand
            KPI_peak_elec_demand = max(total_electricity_use[building_id])
            try:
                # Extract country_id from generation_system_profile
                data = generation_system_profile[cte.ELECTRICITY_SYSTEM][cte.ENERGY_CARRIER_INPUT1][
                    cte.NATIONAL_ENERGY_CARRIER_DATA]
                if isinstance(data, list):
                    # Look for a match in the list
                    country_id=data[0][cte.COUNTRY_ID]
                else:
                    country_id=data[cte.COUNTRY_ID]
            except (KeyError, IndexError, TypeError):
                # print(f"Error: Unable to extract {COUNTRY_ID} from {GENERATION_SYSTEM_PROFILE}.")
                #assign European country id (31)
                country_id = 31
            try:
                #get national averages for KPIs comparison
                national_average_total_primary_energy_intensity,national_average_total_CO2,national_average_total_energy_cost =filter_values(filename="total_primary_energy_GHG_costs_intensity.csv",
                                                                          building_use_id=building_use_id,
                                                                          construction_year=building_asset_context.get(cte.BUILDING, {}).get(cte.CONSTRUCTION_YEAR),
                                                                          country_id=country_id)
            except (KeyError, IndexError, TypeError):
                print(f"Error: national_average_total_primary_energy_intensity, "
                      f"national_average_total_CO2 or national_average_total_energy_cost "
                      f"is None  ")
            areas_buildings[building_id]={}
            # building_use_mapping = {
            #     1: "residential",  # residential
            #     2: "residential",  # residential
            #     3: "residential",  # residential
            #     4: "office",  # office
            #     5: "commerce",  # commerce
            #     6: "education",  # education
            # }
            if building_use_id in [1,2,3]:
                total_energy_cost=sum(total_h_costs)
            else:
                total_energy_cost=sum(total_non_h_costs)
            area_building = building_asset_context.get(cte.BUILDING, {}).get(cte.AREA)
            if area_building>1:
                total_primary_energy_intensity_kWh = sum(total_primary_energy_kWh) / area_building
                total_co2_intensity=sum(total_co2)/ area_building
                total_energy_cost_intensity=total_energy_cost/area_building
            else:
                # print(f"Error: building area cannot be close to 0, e.g. 1*10-6, 100m2 is assumed")
                area_building=100 #m2 assumption
                total_primary_energy_intensity_kWh = sum(total_primary_energy_kWh) / area_building
                total_co2_intensity=sum(total_co2)/ area_building
                total_energy_cost_intensity=total_energy_cost/area_building
            areas_buildings[building_id][cte.AREA]=area_building
            #get cost data
            total_capex = costs[building_id]["total_capex"] if building_energy_asset else 0
            total_lifetime_costs = costs[building_id]["total_lifetime_costs"] if building_energy_asset else 0
            total_savings = costs[building_id]["total_savings"] if building_energy_asset else 0
            payback_period = costs[building_id]["payback_period_years"] if building_energy_asset else 0
            # Store citizen KPIs for the building
            citizen_KPIs[building_id] = [
                {cte.ID: 1, "name": "KPI_peak_heat_demand_[kWh]", "value": KPI_peak_heat_demand, "unit": "kWh"},
                {cte.ID: 2, "name": "KPI_peak_elec_demand_[kWh]", "value": KPI_peak_elec_demand, "unit": "kWh"},
                {cte.ID: 3, "name": "total_primary_energy_[kWh]", "value": total_primary_energy_kWh, "unit": "kWh"},
                {cte.ID: 4, "name": "num_members", "value": 0, "unit": "a.u."},
                {cte.ID: 5, "name": "EquivalentTVHours_[h]", "value": TV_h, "unit": "h"},
                {cte.ID: 6, "name": "EquivalentstreamingHours_[h]", "value": streaming_hours, "unit": "h"},
                {cte.ID: 7, "name": "PizzaConsumptionComparison_[pizza]", "value": Pizza_h, "unit": "pizza"},
                {cte.ID: 8, "name": "BatteryUsageEstimation_[charges]", "value": Battery_charges,
                 "unit": "charges"},
                {cte.ID: 9, "name": "ElectricCarChargingEstimation_[charges]", "value": ElCar_charges,
                 "unit": "charges"},
                {cte.ID: 10, "name": "WineBottlesProduction_[bottles]", "value": Wine_bottles, "unit": "bottles"},
                {cte.ID: 11, "name": "TreesRequiredForCarbonOffset_[trees]", "value": Trees_number,
                 "unit": "trees"},
                {cte.ID: 12, "name": "streamingEmissionsImpact_[hours]", "value": streaming_emissionhours,
                 "unit": "hours"},
                {cte.ID: 13, "name": "CarbonEmissionsPerKilometer_[km]", "value": ICV_km, "unit": "km"},
                {cte.ID: 14, "name": "Total_PV_[kWh]", "value": total_PV[building_id], "unit": "kWh"},
                {cte.ID: 15, "name": "Total_self_consumption", "value": self_consumption[building_id], "unit": "a.u."},
                {cte.ID: 16, "name": "Total_self_sufficiency", "value": self_sufficiency[building_id], "unit": "a.u."},
                {cte.ID: 17, "name": "rate_of_self_consumption", "value": rate_of_self_consumption[building_id], "unit": "%"},
                {cte.ID: 18, "name": "renewable_primary_energy_[kWh]", "value": total_primary_energy_renewable, "unit": "kWh"},
                {cte.ID: 19, "name": "non_renewable_primary_energy_[kWh]", "value": total_primary_energy_non_renewable, "unit": "kWh"},
                {cte.ID: 20, "name": "non_households_costs_[€]", "value": total_non_h_costs, "unit": "€"},
                {cte.ID: 21, "name": "households_costs_[€]", "value": total_h_costs, "unit": "€"},
                {cte.ID: 22, "name": "Total_co2", "value": total_co2, "unit": "g"},
                {cte.ID: 23, "name": "total_primary_energy_intensity","value": total_primary_energy_intensity_kWh, "unit": "kWh/m2"},
                {cte.ID: 24, "name": "national_average_total_primary_energy_intensity","value": national_average_total_primary_energy_intensity, "unit": "kWh/m2"},
                {cte.ID: 25, "name": "total_CO2_intensity","value": total_co2_intensity, "unit": "g/m2"},
                {cte.ID: 26, "name": "national_average_total_CO2_intensity","value": national_average_total_CO2, "unit": "g/m2"},
                {cte.ID: 27, "name": "total_energy_cost_intensity","value": total_energy_cost_intensity, "unit": "€/m2"},
                {cte.ID: 28, "name": "national_average_total_energy_cost_intensity","value": national_average_total_energy_cost, "unit": "€/m2"},
                {cte.ID: 29, "name": "total_capex", "value": total_capex, "unit": "€"},
                {cte.ID: 30, "name": "total_lifetime_costs", "value": total_lifetime_costs, "unit": "€"},
                {cte.ID: 31, "name": "total_savings", "value": total_savings, "unit": "€"},
                {cte.ID: 32, "name": "payback_period_years", "value": payback_period, "unit": "years"}
            ]
            id_for_citizen_kpi = 33
            for key, energy_instance in FinalEnergy_dic.items():
                citizen_KPIs[building_id].append({cte.ID: id_for_citizen_kpi, "name": key, "value": energy_instance, "unit": "kWh"})
                id_for_citizen_kpi += 1
    else:
        print("community context structure is not correct, should be a list")
    return citizen_KPIs, demand_profiles_context,areas_buildings

