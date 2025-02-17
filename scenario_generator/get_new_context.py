# -*- coding: utf-8 -*-
"""
Created on Wed Jun 12 16:10:28 2024

@author: andgab
"""
import pandas as pd
import os
from context_creation import (update_building_system, get_centroid, call_PVGIS, update_community_energy_assets,
                              create_grid_community_asset, convert_geometries_to_strings,
                              update_building_consumption, get_system_type_for_action)
from datetime import datetime
from kpi_module.key_performance_indicators import handle_demand_profile

# Define constants for recurring string literals
AVAILABILITY_TS = "availability_ts"
BUILDING_ASSET_CONTEXT="building_asset_context"
COMMUNITY_ENERGY_ASSET="community_energy_asset"
GENERATION_SYSTEM_PROFILE="generation_system_profile"
GENERATION_SYSTEM_PROFILE_ID="generation_system_profile_id"
BUILDING = "building"
BUILDING_CONSUMPTION="building_consumption"
DEMANDPROFILE = "demandprofile"
HEATING_SYSTEM = "heating_system"
COOLING_SYSTEM = "cooling_system"
DHW_SYSTEM = "dhw_system"
ELECTRICITY_SYSTEM="electricity_system"
ELECTRICITY_DEMAND = "electricity_demand"
HEATING_DEMAND = "heating_demand"
COOLING_DEMAND = "cooling_demand"
DHW_DEMAND = "dhw_demand"
ELECTRICITY_CONSUMPTION = "elec_consumption"
HEAT_CONSUMPTION = "heat_consumption"
COOL_CONSUMPTION = "cool_consumption"
DHW_CONSUMPTION = "dhw_consumption"
ENERGY_CARRIER_INPUT1_ID = "energy_carrier_input_1_id"
ENERGY_CARRIER_INPUT1="energy_carrier_input_1"
FINAL_ENERGY_ELECTRICITY_GRID = "final_energy_electricity_grid"
VALUE_INPUT1 = "value_input1"
PMAX_SCALAR = "pmax_scalar"
GENERATION_SYSTEM_ID="generation_system_id"
FUEL_YIELD_1="fuel_yield1"
DEMAND_PROFILE="demand_profile"
NATIONAL_ENERGY_CARRIER_DATA="national_energy_carrier_production"
DHW_SYSTEM_ID="dhw_system_id"
HEATING_SYSTEM_ID="heating_system_id"
COOLING_SYSTEM_ID="cooling_system_id"
ELECTRICITY_SYSTEM_ID="electricity_system_id"


def assign_incremental_ids_to_community_assets(community_energy_asset):
    current_id = 1  # Start with an initial id value
    nodes_id=1
    # Loop through each building in the list
    for assets in community_energy_asset:
        # Loop through each energy asset within the building
            assets["id_temp"] = current_id
            if assets[AVAILABILITY_TS] is not None:
                assets[AVAILABILITY_TS]["id_temp"]= current_id
            assets["input_node"]["id_temp"] = nodes_id #DE MOMENTO MIRA AL MISMO ID, CAMBIAR SI SE CAMBIA GEOMETRIA
            # nodes_id+=1
            if "output_node" in assets:
                assets["output_node"]["id_temp"] = nodes_id
                # nodes_id += 1
            # Increment the id for the next asset
            current_id += 1

    return community_energy_asset
def assign_incremental_ids(building_asset_context):
    current_id = 1  # Start with an initial id value

    # Loop through each building in the list
    for building_assets_context in building_asset_context:
        # Loop through each energy asset within the building
        for building_energy_asset in building_assets_context["building_energy_asset"]:
            # Assign the current incremental id to the "id" field
            building_energy_asset["id_temp"] = current_id
            building_energy_asset[AVAILABILITY_TS]["id_temp"]= current_id
            # Increment the id for the next asset
            current_id += 1

    return building_asset_context

# Check if the asset exists by generation_system_id
def asset_exists(community_context, new_gen_system_id):
    for node in community_context.get("node", []):
        for asset_data in node.get("community_energy_asset_input", []):
            if asset_data.get("generation_system_id") == new_gen_system_id:
                return True
    return False

def resbased_generator_context_creation(goal, community_context,recommendations_dic):
    """
    Modifies the systems of each building, according to the list of recommended actions for one scenario

    Parameters
    ----------
    goal: from front, is an int representing the goal
            "1": "Higher rate of renewable energy",
            "2": "Higher efficiency",
            "3": "Energy self-sufficiency",
            "4": "Decarbonisation of H&C",
            "5": "Electrification",
            "6": "E-mobility",
    community_context: The context input of the energy community
    recommendations_dic : ids of the recommended actions

    Returns
    -------
    generation_system_profile_df : modified building systems, as well as new building_energy_assets
    This means a new context is produced

    """
    #Esto es solo una prueba, falta: que sea aplicable para varias action keys,y que permita
    #añadir nuevos energy assets

    # Call the function and get the grouped buildings
    community_context_updated = community_context.copy()
    group_of_geoms = {}
    community_context_updated["context_parent"]=community_context.get("id")
    community_context_updated["id_temp"]= community_context_updated["context_parent"]+1
    if "id" in community_context_updated:
        del(community_context_updated["id"])
    name_of_actions_applied="Scenario with actions_"
    if BUILDING_ASSET_CONTEXT in community_context and isinstance(community_context[BUILDING_ASSET_CONTEXT], list):
        new_buildings_asset_contexts=[]
        temp_id = 1
        for building_asset_context in community_context[BUILDING_ASSET_CONTEXT]:
            # get group of geoms
            group_of_geoms[building_asset_context["building"]["id"]] = {
                "geom": building_asset_context["building"]["geom"],
                "name": building_asset_context["name"]
            }
        # get gdf and centroids
        gdf, community_centroid = get_centroid(group_of_geoms)
        longitude, latitude = community_centroid.x, community_centroid.y
        # get pv_profile, wind profile and temperature for the centroid of the community
        irradiance_dic, pv_profile_kWh_per_kWp, solar_elevation, T2m, wind_potential_kWh_per_kWp, irradiance_dic_with_tmy_data= call_PVGIS(longitude, latitude, tilt_angle=35)
        # translate actions to new generation systems
        file_path = os.path.join(os.path.dirname(os.path.abspath(__file__)), "data",
                                 "actions_to_generation_systems.csv")
        actions_to_generation_systems = pd.read_csv(file_path)

        for building_asset_context in community_context[BUILDING_ASSET_CONTEXT]:
            # Check if GENERATION_SYSTEM_PROFILE_ID is in the building_dic
            if GENERATION_SYSTEM_PROFILE_ID in building_asset_context:
                for i, actions in recommendations_dic.items():
                    #get the action key
                    if "id" in actions:
                        action_key = int(actions["id"])
                        #Action key is demand reduction then:
                        if action_key ==1:
                            # print("these actions are not yet populated")
                            # geojson_object = generate_geojson(front_data=front_data)
                            # geojson_file = fetch_geojson(geojson_object=geojson_object)
                            # demand_profile = demand_thermagrid(data=data, front_data=front_data,
                            #                                    geojson_file=geojson_file)
                            new_system=False
                            pass
                        elif action_key == 2:
                            # print("these actions are not yet populated")
                            new_system=False
                            pass
                        elif action_key in [4,15,14,16,21]:
                            # print("this action is populated at community level")
                            new_system=False
                            pass
                        else:
                            #get building_id
                            building_id_geom=building_asset_context["building"]["id"]
                            #get the name of actions applied to the scenario
                            name_of_actions_applied += f"_{action_key} with name {actions["action_name"]}_"
                            # print(f"Processing action_key {action_key} with name {actions["action_name"]}")
                            #get existing building energy assets
                            building_energy_asset = building_asset_context["building_energy_asset"]
                            # get generation system profile dics
                            generation_system = building_asset_context[GENERATION_SYSTEM_PROFILE]
                            #get building footprint
                            building_geom=float(building_asset_context["building"]["area_conditioned"])
                            #get connsumption profile
                            consumption_profile= building_asset_context["building_consumption"]
                            # get building demand profile
                            demandprofile=handle_demand_profile(building_asset_context,generation_system,consumption_profile)
                            #change building system
                            updated_generation_system_profile,updated_building_energy_asset,new_system= update_building_system (goal=goal, building_id=building_id_geom,
                                                                                                                                 building_geom=building_geom,demandprofile=demandprofile,pvprofile=pv_profile_kWh_per_kWp,
                                                                                                                                 buildings_generation_system=generation_system,building_energy_asset=building_energy_asset,
                                                                                                                                 actions_to_generation_systems=actions_to_generation_systems,action_key=action_key,solar_elevation=solar_elevation)
                            #update building energy assets
                            building_asset_context["building_energy_asset"]=updated_building_energy_asset.copy()
                            #update generation_system_profile_dic
                            building_asset_context[GENERATION_SYSTEM_PROFILE]=updated_generation_system_profile.copy()
                    else:
                        print("error encountered with action id")
                        pass

                building_asset_context["id_temp"]=building_id_geom
                # print(temp_id)

                building_asset_context["context_id"]=community_context_updated["id_temp"]
                # print(action_key)
                # print(building_asset_context["name"])
                if building_asset_context["name"] is not None:
                    building_asset_context["name"]=building_asset_context["name"]+f" with action {action_key}_ "
                # print(f"  Building id {building_asset_context["id_temp"]} changed its generation system profile"
                #       f"to {building_asset_context[GENERATION_SYSTEM_PROFILE_ID]}")
                building_asset_context["building_consumption_id_temp"]=temp_id
                if new_system:  # Only check if new_system is True
                    updated_building_dic=update_building_consumption(temp_id,demandprofile,building_asset_context)
                    building_asset_context["building_consumption"] = updated_building_dic
                new_buildings_asset_contexts.append(building_asset_context)
                temp_id+=1
    else:
        print("building_asset_context is not a valid list in bd")

    for building_asset_context in community_context[BUILDING_ASSET_CONTEXT]:
        # del (building_asset_context[GENERATION_SYSTEM_PROFILE][ELECTRICITY_SYSTEM])
        # del (building_asset_context[GENERATION_SYSTEM_PROFILE][HEATING_SYSTEM])
        # del (building_asset_context[GENERATION_SYSTEM_PROFILE][COOLING_SYSTEM])
        # del (building_asset_context[GENERATION_SYSTEM_PROFILE][DHW_SYSTEM])
        del (building_asset_context["building_consumption_id"])
        del (building_asset_context["id"])
        building_asset_context[GENERATION_SYSTEM_PROFILE_ID] = None
    existing_community_assets = []

    for node in community_context.get("node", []):
        assets = node.get("community_energy_asset_input", [])
        if assets:
            existing_community_assets.extend(assets)

    if existing_community_assets:
        updated_community_energy_asset = existing_community_assets
    else:
        updated_community_energy_asset = []

    community_centroid_string=convert_geometries_to_strings(community_centroid)
    updated_community_energy_asset.append(create_grid_community_asset(community_centroid_string))
    for i, actions in recommendations_dic.items():
        # get the action key
        action_key = int(actions["id"])
        if action_key in [15,4,14]:
            # Main logic
            # Determine the system type based on action_key
            system = "storage" if action_key == 15 else "electricity_system_id"
            new_gen_system_id = get_system_type_for_action(actions_to_generation_systems, action_key, system)

            # updated_community_energy_asset.append(update_community_energy_assets(community_centroid_string, action_key,actions_to_generation_systems,wind_potential_kWh_per_kWp))
            # Add a new asset only if it doesn't already exist
            if not asset_exists(community_context, new_gen_system_id):
                updated_community_energy_asset.append(
                    update_community_energy_assets(
                        community_centroid_string, action_key, actions_to_generation_systems, wind_potential_kWh_per_kWp
                    )
                )

    updated_community_energy_asset=assign_incremental_ids_to_community_assets(community_energy_asset=updated_community_energy_asset)
                                   #create new context (id=2) with context_parent=bd.get("id")
    community_context["building_asset_context"]=assign_incremental_ids(new_buildings_asset_contexts)
    #update community assets and nodes (Alberto)
    if COMMUNITY_ENERGY_ASSET in community_context and not community_context[COMMUNITY_ENERGY_ASSET]:
        # If it"s an empty list, replace it with `updated_community_energy_asset`
        community_context_updated[COMMUNITY_ENERGY_ASSET] = updated_community_energy_asset
    else:
        community_context_updated[COMMUNITY_ENERGY_ASSET] = []
        # If it"s not empty, append every asset from `updated_community_energy_asset`
        for asset in updated_community_energy_asset:
            community_context_updated[COMMUNITY_ENERGY_ASSET].append(asset)
    # datetime object containing current date and time
    community_context_updated["creation_date"] = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    community_context_updated["name"] =name_of_actions_applied
    community_context_updated["description"] = name_of_actions_applied+ f"with goal {goal}"
    return community_context_updated


