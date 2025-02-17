# -*- coding: utf-8 -*-
"""
Dependencies:
    python 3.12
    pillow                    10.3.0
    pandas                     2.2.2
    spyder                    5.5.1
    geopandas                 0.14.3
Created on May 2024

@author: Andrea Gabaldon Moreno
License: GNU GPLv3
The GNU General Public License is a free, copyleft license for software and other kinds of works.
https://www.gnu.org/licenses/gpl-3.0.html
You may copy, distribute and modify the software as long as you track changes/dates in source files.
 Any modifications to or software including (via compiler) GPL-licensed code must also be made 
 available under the GPL along with build & install instructions. 
 This means, you must:
     - Include original
     - State Changes
     - Disclose source
     - Include the same license -- to make sure it remains free software for all its users.
     - Include copyright
     - Include install instructions 
     
You cannot: sublicense or hold liable.

Copyright @CARTIF 2024

***********************************************************************************************

This part of the code is the main code that provides the actual recommendations

***********************************************************************************************

"""
import pandas as pd
import numpy as np
from classes_database import BuildingEnergyAsset, BuildingConsumption, CommunityEnergyAsset
import os
from kpi_module.key_performance_indicators import load_energy_system_catalogue, filter_energy_systems_catalogue
from pvlib.iotools.pvgis import get_pvgis_hourly
from pvlib.iotools import get_pvgis_tmy
from pvlib.irradiance import get_total_irradiance
import geopandas as gpd
from shapely import wkt
# from shapely.geometry import shape
# from shapely.ops import unary_union
from shapely.errors import GEOSException
from pvlib.location import Location

BUILDING_ASSET_CONTEXT="building_asset_context"
def ungroup_buildings_to_context(grouped_buildings):
    """
    Ungroups buildings from the grouped dictionary and reconstructs the original context.

    Parameters:
    grouped_buildings (dict): A dictionary where keys are 'generation_system_profile_id' and values are lists of buildings.

    Returns:
    dict: The original context with BUILDING_ASSET_CONTEXT containing the list of buildings.
    """
    
    building_asset_context = []
    
    for gen_id, buildings in grouped_buildings.items():
        building_asset_context.extend(buildings)
    
    return {BUILDING_ASSET_CONTEXT: building_asset_context}



def handle_new_system_id(new_system_id):
    """The purpose of this function is to handle the update of the buildings_generation_system
    with a new system ID (new_system_id).  It checks the type of new_system_id and
    updates buildings_generation_system accordingly, depending on whether the new_system_id is a dictionary,
    a list (or numpy array), or an integer. If the type is unexpected, it logs a message.
    Parameters
    ----------
    new_system_id

    Returns
    -------
    corrected_new_system_id
    """
    if isinstance(new_system_id, dict):
        if len(new_system_id) > 0:  # Check if the dictionary is not empty
            # Update the system id in buildings_generation_system with the first value from new_system_id
            first_key = next(iter(new_system_id))
            #It retrieves the first key of the dictionary using next(iter(new_system_id)).
            # THIS IS DONE BECAUSE the dictionary contains multiple key-value pairs, but the code only uses the first one (for now)
            corrected_new_system_id = int(new_system_id[first_key])
            # print(f"Updated system with value {new_system_id[first_key]} from new_system_id dictionary")
        else:
            # print("new_system_id is an empty dictionary")
            corrected_new_system_id = None
    elif isinstance(new_system_id, (list, np.ndarray)):
        if len(new_system_id) > 0:  # Check if the list is not empty
            # Update the system id in buildings_generation_system with the first value from new_system_id
            corrected_new_system_id = int(new_system_id[0])
            # print(f"Updated system with value {new_system_id[0]} from new_system_id list")
        else:
            # print("new_system_id is an empty list")
            corrected_new_system_id = None

    elif isinstance(new_system_id, int):
        # Directly use the integer value to update the system id
        corrected_new_system_id = int(new_system_id)
        # print(f"Updated system with value {new_system_id} from new_system_id integer")

    else:
        # print("new_system_id is of an unexpected type")
        # Handle unexpected type
        type(new_system_id)
        corrected_new_system_id=None
    return corrected_new_system_id

# Function to group buildings by 'generation_system_profile_id'
def group_buildings_by_generation_system(bd):
    """
    Groups buildings by 'generation_system_profile_id' from the BUILDING_ASSET_CONTEXT list of dictionaries.

    Parameters:
    bd (dict): The context object containing the BUILDING_ASSET_CONTEXT keys which is a group of buildings

    Returns:
    dict: A dictionary where keys are 'generation_system_profile_id' and values are lists of buildings.


    """
    
    
    grouped_buildings = {}
    
    # Check if BUILDING_ASSET_CONTEXT is in bd and is a list
    if BUILDING_ASSET_CONTEXT in bd and isinstance(bd[BUILDING_ASSET_CONTEXT], list):
        for building_dic in bd[BUILDING_ASSET_CONTEXT]:
            # Check if 'generation_system_profile_id' is in the building_dic
            if "generation_system_profile_id" in building_dic:
                gen_id = building_dic["generation_system_profile_id"]

                # Add building_dic to the appropriate group in grouped_buildings
                if gen_id not in grouped_buildings:
                    grouped_buildings[gen_id] = []
                grouped_buildings[gen_id].append(building_dic)
            else:
                print(f"No 'generation_system_profile_id' found in building_dic with id {building_dic.get("id", "unknown")}")
    else:
        print("BUILDING_ASSET_CONTEXT is not a valid list in bd")
    
    return grouped_buildings



def peak_load_distribution_curve (demand):

    # Sort the demand data in descending order to create the load distribution curve
    sorted_demand = sorted(demand, reverse=True)

    # Calculate the peak
    max_peak=max(sorted_demand)

    # Capacity at 80% and 90% demand
    capacity_70 =  0.7 * max_peak
    capacity_90 = 0.9 * max_peak

    # print(f"Capacity to meet 80% of demand: {capacity_70:.2f}")
    # print(f"Capacity to meet 90% of demand: {capacity_90:.2f}")
    return capacity_70, capacity_90, sorted_demand

def obtain_energy_signature (outdoor_temperatures,demand, mode):
    if mode ==0:
        #This is for heating
        # Filter heating demand for temperatures below 18°C
        filtered_demand = [demand[i] for i in range(len(outdoor_temperatures)) if outdoor_temperatures[i] < 18]
    else:
        # Filter cooling demand for temperatures above 26°C
        filtered_demand = [demand[i] for i in range(len(outdoor_temperatures)) if outdoor_temperatures[i] > 26]

    # Sort the demands to create load duration curves (in descending order)
    sorted_demand = sorted(filtered_demand, reverse=True)
    # Calculate the peak
    max_peak = max(sorted_demand)

    # Capacity at 80% and 90% demand
    capacity_70 =  0.7 * max_peak
    capacity_90 = 0.9 * max_peak

    # print(f"Capacity to meet 80% of demand: {capacity_70:.2f}")
    # print(f"Capacity to meet 90% of demand: {capacity_90:.2f}")
    return capacity_70, capacity_90, sorted_demand

def get_generation_system_profile_id(electricity_id, dhw_id, heating_id, cooling_id):
    """
    This function takes in system type IDs for electricity, DHW, heating, and cooling,
    looks them up in the DataFrame, and returns the corresponding generation_system_profile_id.

    Parameters:
    - electricity_id: The ID of the electricity system type.
    - dhw_id: The ID of the DHW system type.
    - heating_id: The ID of the heating system type.
    - cooling_id: The ID of the cooling system type.
    - df: DataFrame containing the system types and generation_system_profile_id.

    Returns:
    - generation_system_profile_id if a match is found, otherwise None.
    """
    system_profile_combinations_csv = os.path.join(os.path.dirname(os.path.abspath(__file__)),
                                                   "catalogues", "all_profiles.csv")
    system_profile_combinations=pd.read_csv(system_profile_combinations_csv)
    # Filter the DataFrame to match the provided system type IDs
    # Filtrar el DataFrame para que coincida con los valores proporcionados, considerando NaN
    matched_row = system_profile_combinations[
        (system_profile_combinations["electricity_id"] == electricity_id) &
        ((system_profile_combinations["dhw_id"] == dhw_id) | (pd.isna(system_profile_combinations["dhw_id"]) & (dhw_id is None))) &
        ((system_profile_combinations["heating_id"] == heating_id) | (pd.isna(system_profile_combinations["heating_id"]) & (heating_id is None))) &
        ((system_profile_combinations["cooling_id"] == cooling_id) | (pd.isna(system_profile_combinations["cooling_id"]) & (cooling_id is None)))
    ]

    # Check if we found a match
    if not matched_row.empty:
        return int(matched_row.iloc[0]["id"])  # This column contains the generation_system_profile_id
    else:
        return None



def get_system_type_for_action(actions_to_generation_systems, action_key,system):
    """
    This code is part of the logic that updates
    the generation_system_profile for a building.
     It checks if the current action_key is
     applicable to the building, finds the
     corresponding system_type_id (if available),
      and then updates the system profile for the building with the new ID.
    Parameters
    ----------
    actions_to_generation_systems is a DataFrame that contains action information, including the action_key and name_system_type columns.
    action_key represents an identifier for a recommended action.
    system represents the type of system (electricity, dhw, cooling, heating)

    Returns
    -------
    new_system_id
    """
    # Create a mask to filter the DataFrame where action_key matches and name_system_type contains the system key
    mask = (actions_to_generation_systems["action_key"] == action_key) & (
        actions_to_generation_systems["name_system_type"].str.contains(system))
    # Get the 'id' values from the filtered DataFrame
    try:
        new_system_id = actions_to_generation_systems.loc[mask, "id"].values
        if new_system_id.size == 0:
            new_system_id = None
    except ValueError as e:
        # print(f"Error retrieving new_system_id: {e}")
        new_system_id = None
    corrected_id=handle_new_system_id(new_system_id)
    return corrected_id

def get_centroid(group_of_geoms,target_epsg=4326):

    """

    Parameters
    ----------
    group_of_geoms = {
        '1': {'name': 'Building 1 Name', 'geom': 'string defining geometry'},
        '2': {'name': 'Building 2 Name', 'geom': 'string defining geometry'}
    }

    string geometries are in EPSG 4326

    Returns
    -------
    gdf containing the string geometry into a geometry object and centroids for each building geometry
    community centroid
    """

    geoms_list = []
    names_list = []
    ids_list = []

    for building_id, data in group_of_geoms.items():
        try:
            # Try converting the string geometry (WKT) to a Shapely geometry object
            geometry = wkt.loads(data["geom"])

            # Check if the geometry is valid
            if not geometry.is_valid:
                # print(f"Warning: Geometry for building {building_id} is invalid, attempting to fix...")
                geometry = geometry.buffer(0)  # Try to fix the geometry by buffering it

            # Append the valid geometry to the list
            geoms_list.append(geometry)
            names_list.append(data["name"])
            ids_list.append(building_id)

        except GEOSException as e:
            # If there's an issue loading the geometry, log it and skip
            print(f"Error loading geometry for building {building_id}: {e}")

    # Create the GeoDataFrame
    gdf = gpd.GeoDataFrame({"id": ids_list, "name": names_list, "geometry": geoms_list})
    # Assign a default CRS (you might want to choose a different CRS depending on the data source)
    gdf.set_crs(epsg=target_epsg, inplace=True)

    # Reproject the GeoDataFrame to the target CRS (e.g., EPSG:4326 for geographic coordinates)
    gdf = gdf.to_crs(epsg=target_epsg)
    # Calculate the centroid of each individual geometry
    gdf["centroid"] = gdf.geometry.centroid

    # Calculate the centroid of the entire group of geometries
    community_centroid = gdf.unary_union.centroid

    # ------------------------------------------------------
    # ASSUMES INPUT AND OUTPUT CRS IS EPSG 4326
    # IF NOT, IT MUST BE MODIFIED
    # ------------------------------------------------------
    return gdf, community_centroid


def wind_power(wind_speed):
    import numpy as np

    # Define wind speed and power from the technology (in this case wind turbine e200 https://www.enair.es/en/small-wind-turbines/e200)
    #18 meters height, nominal power of 20 kW, starts functioning at 1.85 m/s
    wind_speed_table = [0, 1.85, 2, 3, 4, 5, 6, 7, 8, 9, 10, 11, 12, 13, 14, 15, 16, 17, 18, 19, 20,20.01]
    power_table = [0, 0, 80, 500, 1350, 2800, 4700, 7000, 9600, 12300, 15500, 17800, 18500, 18000,
                   17500, 17500, 17500, 17500, 17500, 17500, 17500, 0]
    wind_speed_table_030pro=[0, 1.85, 2, 3, 4, 5, 7, 8, 9, 10, 11, 12,  15, 15.01]
    power_table_030pro=[0, 0, 0, 10, 100, 300, 1000, 1450, 1850, 2100, 2300, 2500,2500,0]
    # Scaling power values
    power_table = [p / 20000 for p in power_table]
    power_table_030pro = [p / 3000 for p in power_table_030pro]
    # Interpolating power values for the second dataset to match the wind_speed_table of the first dataset
    interpolated_power_table_030pro = np.interp(wind_speed_table, wind_speed_table_030pro, power_table_030pro)
    # Calculating mean values
    mean_power = [(p1 + p2) / 2 for p1, p2 in zip(power_table, interpolated_power_table_030pro)]
    # Setting mean power values to 0 for wind speeds above 15 m/s
    mean_power_adjusted = [0 if wind_speed > 15 else power for wind_speed, power in zip(wind_speed_table, mean_power)]

    # Interpolate power for each wind speed in tmy_data['WS10m']
    wind_potential_kWh_per_kWp = np.interp(wind_speed, wind_speed_table, mean_power_adjusted).tolist()


    return wind_potential_kWh_per_kWp


def call_PVGIS(longitude, latitude,tilt_angle):
        """
        Calculate temperatures and radiations based on TMY data and return a JSON for
        the given centroid returning temperatures, and radiations.

        Parameters
        ----------
        centroid : point (X Y)

        Returns
        -------
        dict
            A dictionary containing the original GeoJSON, temperatures, and calculated radiations.
            From PVGIS tmy_data is obtained such as:
                    {'T2m': {'description': '2-m air temperature', 'units': 'degree Celsius'},
                    'RH': {'description': 'relative humidity', 'units': '%'},
                     'G(h)': {'description': 'Global irradiance on the horizontal plane', 'units': 'W/m2'},
                      'Gb(n)': {'description': 'Beam/direct irradiance on a plane always normal to sun rays', 'units': 'W/m2'},
                      'Gd(h)': {'description': 'Diffuse irradiance on the horizontal plane', 'units': 'W/m2'},
                      'IR(h)': {'description': 'Surface infrared (thermal) irradiance on a horizontal plane', 'units': 'W/m2'},
                      'WS10m': {'description': '10-m total wind speed', 'units': 'm/s'},
                      'WD10m': {'description': '10-m wind direction (0 = N, 90 = E)', 'units': 'degree'},
                       'SP': {'description': 'Surface (air) pressure', 'units': 'Pa'}}

                       surface azimuth 180º which is south, 0=fixed

        """
        URL = 'https://re.jrc.ec.europa.eu/api/v5_3/'
        pv_data=get_pvgis_hourly (latitude, longitude, start=2023, end=2023,components=True,
                                surface_tilt=tilt_angle, surface_azimuth=180,
                                outputformat='json',
                                usehorizon=True,  pvcalculation=True,
                                peakpower=1, pvtechchoice='crystSi',
                                mountingplace='free', loss=0, trackingtype=0,
                                optimal_surface_tilt=False, optimalangles=False,
                                url=URL, map_variables=True, timeout=30)
        pv_profile_in_kWh_kWp=pv_data[0]['P'].tolist() # PV system power (W)
        pv_profile_in_kWh_kWp = [x/1000 for x in pv_profile_in_kWh_kWp]  # PV system power in kW/kWp
        solar_elevation=pv_data[0]['solar_elevation'].copy() #     Sun height / elevation(degrees) dataframe
        solar_elevation = solar_elevation.reset_index()  # Converts the index to a column
        solar_elevation['time'] = pd.to_datetime(solar_elevation['time'])
        date_filter = (solar_elevation['time'].dt.date == pd.to_datetime('2023-12-12').date())
        # Filter for midday hours
        time_filter = (solar_elevation['time'].dt.time >= pd.to_datetime('12:00').time()) & \
                      (solar_elevation['time'].dt.time <= pd.to_datetime('14:00').time())
        filtered_rows = solar_elevation[date_filter & time_filter]
        solar_elevation_midday_values = filtered_rows[['time', 'solar_elevation']]
        # Call PVGIS API (with pvlib) to get TMY data
        tmy_data, months_selected, inputs, meta = get_pvgis_tmy(latitude, longitude, map_variables=False, url=URL)

        # Ensure 'tmy_data' index is in datetime format
        tmy_data.index = pd.to_datetime(tmy_data.index)
        #get other data
        T2m = tmy_data['T2m'].tolist()
        WS10m = tmy_data['WS10m'].tolist()
        #get wind potential at 10 meters height
        wind_potential_kWh_per_kWp=wind_power(WS10m)
        # Define the location using 'inputs' data
        latitude = inputs['location']['latitude']
        longitude = inputs['location']['longitude']
        site = Location(latitude, longitude,altitude=inputs['location']['elevation'])  # Use Location class directly
        #Location class sets times as UTC

        # The angles apparent zenith and azimuth are obtained
        solar_position = site.get_solarposition(times=tmy_data.index)

        # Define orientations of vertical surfaces
        orientations = {
            'rad_n': 0,
            'rad_s': 180,
            'rad_e': 90,
            'rad_o': 270  # 'rad_o' changed to 'rad_w' for clarity
        }

        # Tilt angle (90 degrees for vertical surfaces)
        tilt_angle = tilt_angle
        irradiance_dic={}
        for orientation_name, azimuth_angle in orientations.items():
            irradiance = get_total_irradiance(
                surface_tilt=tilt_angle,
                surface_azimuth=azimuth_angle,
                solar_zenith=solar_position['apparent_zenith'], #The angles are in degrees.
                solar_azimuth=solar_position['azimuth'],#The angles are in degrees.
                dni=tmy_data['Gb(n)'], #units': 'W/m2
                ghi=tmy_data['G(h)'],
                dhi=tmy_data['Gd(h)'],
            )

            irradiance_dic[orientation_name] = irradiance['poa_global'].tolist()  # Radiation list

        irradiance_dic_with_tmy_data=irradiance_dic
        irradiance_dic_with_tmy_data['Gb(n)']=tmy_data['Gb(n)'].tolist()
        irradiance_dic_with_tmy_data['G(h)']=tmy_data['G(h)'].tolist()
        irradiance_dic_with_tmy_data['Gd(h)']=tmy_data['Gd(h)'].tolist()

        return irradiance_dic, pv_profile_in_kWh_kWp, solar_elevation_midday_values, T2m, wind_potential_kWh_per_kWp, irradiance_dic_with_tmy_data



def handle_storage_system(action_key, actions_to_generation_systems,community_node, energy_systems_catalogue):
    new_gen_system_id = get_system_type_for_action(actions_to_generation_systems, action_key, system="storage")
    filtered_systems_info = filter_energy_systems_catalogue(energy_systems_catalogue, new_generation_system_id=new_gen_system_id)
    new_community_energy_asset=CommunityEnergyAsset(generation_system_id=new_gen_system_id, pmaxmin_scalar=0,
                                                    pmaxmax_scalar=1000, input_node_geom=community_node,
                                                    output_node_geom=community_node, name="storage")
    new_community_energy_asset.add_input1_profile(input1_profile= [100]*8760)
    new_community_energy_asset.add_generation_systems_info(Generation_system_info=filtered_systems_info)
    new_community_enegy_asset_dic=new_community_energy_asset.to_dict()
    #storage assumde of 1 MW and available all year long
    del new_community_energy_asset


    return new_community_enegy_asset_dic


def handle_wind_system(action_key, actions_to_generation_systems,community_node, wind_potential_kWh_per_kWp,energy_systems_catalogue):
    new_gen_system_id = get_system_type_for_action(actions_to_generation_systems, action_key, system="electricity_system_id")
    filtered_systems_info = filter_energy_systems_catalogue(energy_systems_catalogue, new_generation_system_id=new_gen_system_id)
    new_community_energy_asset=CommunityEnergyAsset(generation_system_id=new_gen_system_id, pmaxmin_scalar=0,
                                                    pmaxmax_scalar=20000, input_node_geom=community_node,
                                                    output_node_geom=community_node, name="wind")
    new_community_energy_asset.add_input1_profile(input1_profile= wind_potential_kWh_per_kWp)
    new_community_energy_asset.add_generation_systems_info(Generation_system_info=filtered_systems_info)
    new_community_enegy_asset_dic=new_community_energy_asset.to_dict()
    del new_community_energy_asset

    return new_community_enegy_asset_dic

def handle_chp_system(action_key, actions_to_generation_systems,community_node,energy_systems_catalogue):
    new_gen_system_id = get_system_type_for_action(actions_to_generation_systems, action_key, system="electricity_system_id")
    filtered_systems_info = filter_energy_systems_catalogue(energy_systems_catalogue, new_generation_system_id=new_gen_system_id)
    new_community_energy_asset=CommunityEnergyAsset(generation_system_id=new_gen_system_id, pmaxmin_scalar=0,
                                                    pmaxmax_scalar=20000, input_node_geom=community_node,
                                                    output_node_geom=community_node, name="chp")
    new_community_energy_asset.add_input1_profile(input1_profile= [100]*8760)
    new_community_energy_asset.add_generation_systems_info(Generation_system_info=filtered_systems_info)
    new_community_enegy_asset_dic=new_community_energy_asset.to_dict()
    del new_community_energy_asset

    return new_community_enegy_asset_dic
def handle_electricity_system(updated_generation_system_profile, new_gen_system_id, energy_systems_catalogue, building_id,building_geom,generation_profile):
    new_building_energy_asset_dic={}
    if float(new_gen_system_id) == 83:  # solar fleet
        new_building_energy_asset = BuildingEnergyAsset(
            generation_system_id=new_gen_system_id,
            pmaxmin_scalar=0,
            pmaxmax_scalar=building_geom * 0.6 / 6,
            building_asset_context_id=building_id,
            name=f"pv_building_{building_id}"
        )
        new_building_energy_asset.add_PV_profile(generation_profile)
        pv_info = filter_energy_systems_catalogue(energy_systems_catalogue, 83)
        new_building_energy_asset.add_generation_systems_info(Generation_system_info=pv_info)
        new_building_energy_asset_dic = new_building_energy_asset.to_dict()
        del new_building_energy_asset

        # the final id for PV is grid as PV is an asset, and grid will continue
        # to supply electricity demand
        filtered_systems_info = filter_energy_systems_catalogue(energy_systems_catalogue, new_generation_system_id=79)
        updated_generation_system_profile["electricity_system"] = filtered_systems_info
    else:
        filtered_systems_info = filter_energy_systems_catalogue(energy_systems_catalogue, new_gen_system_id)
        yield1 = filtered_systems_info["fuel_yield1"]
        name=filtered_systems_info["name"]
        if filtered_systems_info["fuel_yield2"] is not None:
            yield2 = filtered_systems_info["fuel_yield2"]
        new_building_energy_asset = BuildingEnergyAsset(
            generation_system_id=new_gen_system_id,
            pmaxmin_scalar=0,
            pmaxmax_scalar=3, #by the default?
            building_asset_context_id=building_id,
            name=f"{name}_building_{building_id}"
        )
        new_building_energy_asset.add_PV_profile(generation_profile)
        new_building_energy_asset.add_generation_systems_info(Generation_system_info=filtered_systems_info)
        new_building_energy_asset_dic = new_building_energy_asset.to_dict()
        del new_building_energy_asset

        # the final id for PV is grid as PV is an asset, and grid will continue
        # to supply electricity demand
        filtered_systems_info = filter_energy_systems_catalogue(energy_systems_catalogue, new_generation_system_id=79)
        updated_generation_system_profile["electricity_system"] = filtered_systems_info

    return updated_generation_system_profile , new_building_energy_asset_dic

def handle_dhw_system(updated_generation_system_profile, new_gen_system_id, dhw_demand, energy_systems_catalogue,building_id):
    new_building_energy_asset_dic={}
    list_of_hps = [1, 2, 3, 4, 5, 6, 7, 8, 27, 28, 29, 30, 31, 32, 33, 34, 35, 36, 41, 61, 62, 63, 64, 65, 66,
                   67, 68, 73]
    if float(new_gen_system_id) in list_of_hps:  # heat pump
        filtered_systems_info = filter_energy_systems_catalogue(energy_systems_catalogue, new_gen_system_id)
        capacity_70, capacity_90, sorted_demand = peak_load_distribution_curve(dhw_demand)
        updated_generation_system_profile["dhw_system"] = filtered_systems_info
        name=filtered_systems_info["name"]
        new_building_energy_asset = BuildingEnergyAsset(
            generation_system_id=new_gen_system_id,
            pmaxmin_scalar=0,
            pmaxmax_scalar=capacity_70,
            building_asset_context_id=building_id,
            name=f"{name}_dhw_building_{building_id}"
        )
        yield1 = updated_generation_system_profile["dhw_system"]["fuel_yield1"]
        yield2 = updated_generation_system_profile["dhw_system"]["fuel_yield2"]
        new_building_energy_asset.calculate_inputs_and_outputs(demand=dhw_demand,
                                                               fuel_yield1=yield1,
                                                               fuel_yield2=yield2,
                                                               type="heat_pump"
                                                               )
        new_building_energy_asset.add_generation_systems_info(Generation_system_info=filtered_systems_info)
        new_building_energy_asset_dic = new_building_energy_asset.to_dict()
        del new_building_energy_asset

        difference_capacities = capacity_90 - capacity_70
        # if difference_capacities > 1:
        #     #1kW
    else:
        filtered_systems_info = filter_energy_systems_catalogue(energy_systems_catalogue, new_gen_system_id)
        capacity_70, capacity_90, sorted_demand = peak_load_distribution_curve(dhw_demand)
        updated_generation_system_profile["dhw_system"] = filtered_systems_info
        name=updated_generation_system_profile["dhw_system"]["name"]
        new_building_energy_asset = BuildingEnergyAsset(
            generation_system_id=new_gen_system_id,
            pmaxmin_scalar=0,
            pmaxmax_scalar=capacity_70,
            building_asset_context_id=building_id,
            name=f"{name}_dhw_building_{building_id}"
        )
        yield1 = updated_generation_system_profile["dhw_system"]["fuel_yield1"]
        yield2 = updated_generation_system_profile["dhw_system"]["fuel_yield2"]
        new_building_energy_asset.calculate_inputs_and_outputs(demand=dhw_demand,
                                                               fuel_yield1=yield1,
                                                               fuel_yield2=yield2,
                                                               type=name
                                                               )
        new_building_energy_asset.add_generation_systems_info(Generation_system_info=filtered_systems_info)
        new_building_energy_asset_dic = new_building_energy_asset.to_dict()

        del new_building_energy_asset
        difference_capacities = capacity_90 - capacity_70
        # if difference_capacities > 1:
        #     #1kW

    return updated_generation_system_profile, new_building_energy_asset_dic

def handle_cooling_system(updated_generation_system_profile, new_gen_system_id, cooling_demand, energy_systems_catalogue,building_id):
    new_building_energy_asset_dic = {}
    return updated_generation_system_profile, new_building_energy_asset_dic

def handle_heating_system(updated_generation_system_profile, new_gen_system_id,  heating_demand, energy_systems_catalogue,building_id):
    new_building_energy_asset_dic={}
    list_of_hps = [1, 2, 3, 4, 5, 6, 7, 8, 27, 28, 29, 30, 31, 32, 33, 34, 35, 36, 41, 61, 62, 63, 64, 65, 66,
                   67, 68, 73]
    if float(new_gen_system_id) in list_of_hps:  # heat pump
        filtered_systems_info = filter_energy_systems_catalogue(energy_systems_catalogue, new_gen_system_id)
        capacity_70, capacity_90, sorted_demand = peak_load_distribution_curve(heating_demand)
        updated_generation_system_profile["heating_system"] = filtered_systems_info
        name=updated_generation_system_profile["heating_system"]["name"]
        new_building_energy_asset = BuildingEnergyAsset(
            generation_system_id=new_gen_system_id,
            pmaxmin_scalar=0,
            pmaxmax_scalar=capacity_70,
            building_asset_context_id=building_id,
            name=f"{name}_heating_building_{building_id}"
        )
        yield1 = updated_generation_system_profile["heating_system"]["fuel_yield1"]
        yield2 = updated_generation_system_profile["heating_system"]["fuel_yield2"]
        new_building_energy_asset.calculate_inputs_and_outputs(demand=heating_demand,
                                                               fuel_yield1=yield1,
                                                               fuel_yield2=yield2,
                                                               type="heat_pump"
                                                               )
        new_building_energy_asset.add_generation_systems_info(Generation_system_info=filtered_systems_info)
        new_building_energy_asset_dic = new_building_energy_asset.to_dict()
        del new_building_energy_asset
    else:
        filtered_systems_info = filter_energy_systems_catalogue(energy_systems_catalogue, new_gen_system_id)
        capacity_70, capacity_90, sorted_demand = peak_load_distribution_curve(heating_demand)
        updated_generation_system_profile["heating_system"] = filtered_systems_info
        name = updated_generation_system_profile["heating_system"]["name"]
        new_building_energy_asset = BuildingEnergyAsset(
            generation_system_id=new_gen_system_id,
            pmaxmin_scalar=0,
            pmaxmax_scalar=capacity_70,
            building_asset_context_id=building_id,
            name=f"{name}_heating_building_{building_id}"
        )
        yield1 = updated_generation_system_profile["heating_system"]["fuel_yield1"]
        yield2 = updated_generation_system_profile["heating_system"]["fuel_yield2"]
        new_building_energy_asset.calculate_inputs_and_outputs(demand=heating_demand,
                                                               fuel_yield1=yield1,
                                                               fuel_yield2=yield2,
                                                               type=name
                                                               )
        new_building_energy_asset.add_generation_systems_info(Generation_system_info=filtered_systems_info)
        new_building_energy_asset_dic = new_building_energy_asset.to_dict()
        del new_building_energy_asset
    return updated_generation_system_profile, new_building_energy_asset_dic

# Function to update building system based on recommended action key
def update_building_system(goal, building_id,building_geom, demandprofile,pvprofile, buildings_generation_system,
                           building_energy_asset, actions_to_generation_systems, action_key,solar_elevation):
    """
    Updates the building's generation system profile and energy assets based on the recommended action key.

    This function takes in various inputs related to the building's energy systems, demand profiles, and recommended actions
    to update the building's energy generation systems (e.g., electricity, heating, cooling, and DHW) according to
    the `action_key`. It processes each system, applies updates from the energy systems catalogue, and returns the
    updated generation system profile and a list of energy assets.

    Parameters
    ----------
    goal : key. The high-level objective or goal associated with the update
            (could be a target energy goal, strategy, etc.).
    building_id : int. The unique identifier for the building being updated.
    building_geom : building footprint area in m2
    demandprofile : dict
        A dictionary containing the demand profiles for the building's energy systems. It should include:
        - 'heating_demand': Array of 8670 representing the heating energy demand
        - 'cooling_demand': Array of 8670 representing the cooling energy demand
        - 'dhw_demand':  Array of 8670 representing the domestic hot water (DHW) energy demand
        - 'electricity_demand':  Array of 8670 representing the electricity energy demand

    pvprofile:  Array of 8670 representing the photovoltaic production per kWp

    buildings_generation_system : dict
        A dictionary containing the current generation system configuration for the building. It includes the IDs of
        the current systems for heating, cooling, DHW, and electricity.

    building_energy_asset : list of dicts or None
        The dictionary within the list can represent the current energy asset for the building (if available).
        If no asset is present, this is `None` or []

    actions_to_generation_systems : pd.DataFrame
        A DataFrame that maps action keys to corresponding system types and system IDs. This is used to look up
        the new system IDs based on the action being applied.

    action_key : int
        The key representing the recommended action to be applied to the building's systems. This key is used to look
        up the corresponding new system configurations.

    Returns
    -------
    updated_generation_system_profile : dict
        A dictionary containing the updated generation system profile for the building, including the updated system IDs
        for heating, cooling, DHW, and electricity.

    building_energy_assets : list of dicts
        A list of updated building energy assets based on the new systems added or modified as part of the update process.
        This list will be empty if no new assets were added or updated.

    Notes
    -----
    - The function iterates through the building's generation systems (electricity, heating, DHW, cooling) and applies
      updates based on the action key and the corresponding system in the energy systems catalogue.
    - The function supports systems applied at the building level for the following keys:
      `[1, 2, 3, 7, 8, 9, 10, 19, 21]` which are: reduction of demand, demand response, solar fleet,  solar thermal, biomass boiler, gas boiler
      heat pump, connection to DHN, and charging station
             it only works for 3 and 10 for now
    - If the `building_energy_asset` is not `None`, it is appended to the `building_energy_assets` list.
    - For each system (electricity, heating, DHW, cooling), the function calls the respective handler functions
      (e.g., `handle_electricity_system`, `handle_heating_system`) to update the system profile and the energy assets.
    - If the action key is not found in the predefined building-level recommendations, a message is printed and no changes
      are applied.

    """
    heating_demand=demandprofile['heating_demand'].copy()
    cooling_demand = demandprofile["cooling_demand"].copy()
    dhw_demand = demandprofile["dhw_demand"].copy()

    # Iterate through each system type in the building
    # we will have systems that are applied at building level
    keys_buildings_level_recommendations = [1, 2, 3, 7, 8, 9, 10, 19, 21]

    # Iterate through each key in buildings_generation_system dictionary
    updated_generation_system_profile = buildings_generation_system
    # updated_generation_system_profile will be updated with the new keys, dictionary and info from generation_system_profile
    # Initialize an empty list for building_energy_assets

    if building_energy_asset is not None:
        building_energy_assets=building_energy_asset
    else:
        building_energy_assets=[]
    #get energy systems catalogue
    energy_systems_catalogue=load_energy_system_catalogue()
    if action_key in keys_buildings_level_recommendations:
        for system in buildings_generation_system:
            # Check if the key ends with '_id' and the value is not None
            if system.endswith("_id") and buildings_generation_system[system] is not None:
                new_gen_system_id=get_system_type_for_action(actions_to_generation_systems, action_key, system)
                new_system = False
                if new_gen_system_id is not None and buildings_generation_system[system] != new_gen_system_id:
                    # Print the current system id value
                    new_system = True
                    # print(f"For {system}, the old system id is:{buildings_generation_system[system]}")
                    updated_generation_system_profile[system] = new_gen_system_id
                    # print(f"For {system}, the new system id is:{updated_generation_system_profile[system]}")
                    if system.startswith("electricity"):
                        updated_generation_system_profile, new_building_energy_asset_dic=handle_electricity_system(updated_generation_system_profile,
                                                                                                                   new_gen_system_id,
                                                                                                                   energy_systems_catalogue,
                                                                                                                   building_id,
                                                                                                                   building_geom,
                                                                                                                   pvprofile)
                        updated_generation_system_profile["electricity_system_id"] = 79
                        if new_building_energy_asset_dic:
                            building_energy_assets.append(new_building_energy_asset_dic)
                    elif system.startswith("dhw"):
                        updated_generation_system_profile, new_building_energy_asset_dic=handle_dhw_system(updated_generation_system_profile,
                                                                                                           new_gen_system_id,  dhw_demand,
                                                                                                           energy_systems_catalogue,
                                                                                                           building_id)
                        if new_building_energy_asset_dic:
                            building_energy_assets.append(new_building_energy_asset_dic)
                    elif system.startswith("cooling"):
                        updated_generation_system_profile, new_building_energy_asset_dic=handle_cooling_system(updated_generation_system_profile
                                                                                                               ,new_gen_system_id,  cooling_demand,
                                                                                                               energy_systems_catalogue,
                                                                                                               building_id)
                        if new_building_energy_asset_dic:
                            building_energy_assets.append(new_building_energy_asset_dic)
                    elif system.startswith("heating"):
                        updated_generation_system_profile, new_building_energy_asset_dic=handle_heating_system(updated_generation_system_profile,
                                                                                                               new_gen_system_id, heating_demand,
                                                                                                               energy_systems_catalogue,
                                                                                                               building_id)
                        if new_building_energy_asset_dic:
                            building_energy_assets.append(new_building_energy_asset_dic)
                else:
                    # Print a message if the system value is None (not necessary due to previous checks)
                    print(f"{system} is None, no change applied.")

    else:
        # Print a message if the action key does not apply
        # print(f"Action key {action_key} is not in the dictionary and does not apply")
        new_system=False
    # Create a copy of the updated buildings_generation_system dictionary
    # Return the updated dictionary
    return updated_generation_system_profile, building_energy_assets, new_system


def update_community_energy_assets (community_node,action_key,actions_to_generation_systems,wind_potential_kWh_per_kWp):
    # we will have systems that are applied at community level, to be done[3, 4, 5, 6, 11, 12, 13, 14, 15, 16, 17, 18, 20]
    keys_community_level_recommendations = [15]
    energy_systems_catalogue=load_energy_system_catalogue()
    if action_key ==15:
        # Print a message if the action key applies to community level
        community_energy_asset=handle_storage_system(action_key, actions_to_generation_systems,community_node,energy_systems_catalogue)
    elif action_key ==4:
        #handle wind turbine asset
        community_energy_asset=handle_wind_system(action_key, actions_to_generation_systems,community_node, wind_potential_kWh_per_kWp,energy_systems_catalogue)
    elif action_key==14:
        community_energy_asset =handle_chp_system(action_key, actions_to_generation_systems, community_node, energy_systems_catalogue)

    return community_energy_asset

def create_grid_community_asset(community_centroid):
    energy_systems_catalogue=load_energy_system_catalogue()
    filtered_systems_info = filter_energy_systems_catalogue(energy_systems_catalogue=energy_systems_catalogue, new_generation_system_id=79)
    grid={
            "id": None,
            "generation_system_id": 79,
            "pmaxmin_scalar": None,
            "availability_ts_id": None,
            "pmax_scalar": None,
            "pmaxmax_scalar": None,
            "input_node_id": 1,
            "output_node_id": None,
            "input_node": {
                "id": None,
                "context_id": None,
                "geom": community_centroid,
                "name": "GRID"
            },
            "availability_ts": None,
            "generation_system": filtered_systems_info,
    }
    return grid


def convert_geometries_to_strings(geom):
    new_geom = geom.wkt
    return new_geom

def update_building_consumption(temp_id,demandprofile,building_asset_context):
    updated_building_consumption = BuildingConsumption(
        building_consumption_id_temp=temp_id,
        elec_consumption=demandprofile["electricity_demand"]
    )
    if building_asset_context["generation_system_profile"]["heating_system"] is not None:
        updated_building_consumption.re_calculate_consumption(
            demandprofile["heating_demand"],
            fuel_yield1=building_asset_context["generation_system_profile"]["heating_system"]["fuel_yield1"],
            type="heat_consumption"
        )
    if building_asset_context["generation_system_profile"]["cooling_system"] is not None:
        updated_building_consumption.re_calculate_consumption(
            demandprofile["cooling_demand"],
            fuel_yield1=building_asset_context["generation_system_profile"]["cooling_system"]["fuel_yield1"],
            type="cool_consumption"
        )
    if building_asset_context["generation_system_profile"]["dhw_system"] is not None:
        updated_building_consumption.re_calculate_consumption(
            demandprofile["dhw_demand"],
            fuel_yield1=building_asset_context["generation_system_profile"]["dhw_system"]["fuel_yield1"],
            type="dhw_consumption"
        )
    updated_building_dic = updated_building_consumption.to_dict()
    del (updated_building_consumption)
    return updated_building_dic