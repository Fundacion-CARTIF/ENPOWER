# -*- coding: utf-8 -*-
"""
Dependencies:
    python 3.11
    pillow                    10.2.0
    pandas                    2.2.0
    spyder                    5.5.0
    geopandas                 0.14.2
Created on October 2023

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


"""
import os
from pathlib import Path
import pandas as pd
import json
import requests
import geopandas as gpd
from shapely import wkt
from shapely.geometry import shape
from shapely.ops import unary_union 
import pvlib 
from pvlib.location import Location
#
# from api.constants import SRID, THERMAGRID_API_KEY, THERMAGRID_API_URL
from Electricity_profiles import Electricity_demand_calculation as el
from country_RES_library import  country_res_recommendations

building_use_mapping = {
        1: "residential",  # residential
        2: "residential",  # residential
        3: "residential",  # residential
        4: "office",  # office
        5: "commerce",  # commerce
        6: "education",  # education
}

def res_based_generator_list_technologies(inputs_users):
    """
    This function allows to create a list of recommended technologies for user preferences
    
    Parameters
    ----------
    inputs_users : it comes from the front-end user interface, where the user selects 
        the location (country) and the goal of their community
    # goals={
    #         "1": "Higher rate of renewable energy",
    #         "2": "Higher efficiency",
    #         "3": "Energy self-sufficiency",
    #         "4": "Decarbonisation of H&C",
    #         "5": "Electrification",
    #         "6": "E-mobility",
    #     }
        It is a json file with the following structure:  
          
           # {
           #   "goals": "3",
           #   "country": "AT" 
           # }
    
    
    Returns
    -------
    output_dictionary : dictionary of recommendations with the following strcture. For example:
        {0: {'id': 1, 'action_name': 'reduction_of_demand'},
         1: {'id': 2, 'action_name': 'demand_response'},
         2: {'id': 16, 'action_name': 'heat_storage'},
         3: {'id': 3, 'action_name': 'solar_fleet'},
         4: {'id': 7, 'action_name': 'solar_thermal'}}
        where the id is the action_key that will be later used to transform the data model
    
    """
    
    #read inputs from users
    user_objective=inputs_users['goals']
    country_code=inputs_users['country']
    #translate to string
    goals = {
        "1": "Higher rate of renewable energy",
        "2": "Higher efficiency",
        "3": "Energy self-sufficiency",
        "4": "Decarbonisation of H&C",
        "5": "Electrification",
        "6": "E-mobility",
        "7": "Otra cosa,No estoy seguro"
    }
    goal_numeric_value=float(user_objective)
    user_objective = goals[str(user_objective)]
    #create country object and obtain recommended scenarios for the country selected
    country_properties= country_res_recommendations(country_code=country_code)
    #read the tables Country_VS_Actions and Goals_VS_Actions to make the MCDA analysis
    directory_path =os.path.join(os.path.dirname(os.path.abspath(__file__)),'data', 'RESlibrary')
    json_file_path_country_vs_actions_df=os.path.join(directory_path,'country_vs_actions.json')
    json_file_path_goals_vs_actions_df=os.path.join(directory_path,'goals_vs_actions.json')
    #obtain w2
    w2_df=calculate_action_values (goal_numeric_value, country_properties,json_file_path_country_vs_actions_df)
    # obtain w1
    goals_vs_actions_df_filtered = get_goal_values(user_objective, json_file_path_goals_vs_actions_df)
    if goal_numeric_value != 7:
        #obtain wT
        wT=  goals_vs_actions_df_filtered.iloc[:, 1:]
        wT=wT.multiply(w2_df)
        wT_final = pd.concat([goals_vs_actions_df_filtered['Action'], wT], axis=1)
    # wT.set_index(goals_vs_actions_df['Action'], inplace=True)
    # Actions_weight=pd.concat([ goals_vs_actions_df['Action'], wT], axis=1, ignore_index=True)
    if goal_numeric_value == 7:
        list_technologies=pd.concat([goals_vs_actions_df_filtered['Action'], w2_df], axis=1)
        list_technologies = top_values(list_technologies)
    else:      
        list_technologies=top_values(wT_final)

    list_technologies=list_technologies.reset_index()
    data = {
        1:'reduction_of_demand',
        2:'demand_response',
        3:'solar_fleet',
        4: 'wind_fleet',
        5: 'solar_thermal',
        6: 'biomass_boiler',
        7: 'heat_pump',
        8: 'biomass_chp',
        9: 'battery_storage',
        10: 'heat_storage',
        11: 'creation_of_dhn',
        12: 'charging_station'
    }
    #translate into a useful json
    output_dictionary = {}
    for idx, row in list_technologies.iterrows():
        id_ = row['index'] + 1  # Increment by 1 to do match with the previous dictionary
        action_name = data[id_]
        output_dictionary[idx] = {'id': id_, 'action_name': action_name}
    actions_keys_csv_file_path=os.path.join(directory_path, 'action_keys.csv')
    action_keys = pd.read_csv(actions_keys_csv_file_path)
    output_dictionary_matched=match_actions(action_keys, output_dictionary)
    return output_dictionary_matched


# Define a function to match action names with the data dictionary
def match_actions(action_keys, data):
    matched_actions = {}

    # Iterate over the data dictionary (which has 'id' and 'action_name' as nested dict values)
    for key, item in data.items():
        action_name = item['action_name']

        # Check if the action_name from the data exists in the CSV DataFrame
        matched_row = action_keys[action_keys['action_name'] == action_name]

        if not matched_row.empty:
            # Extract the action_key from the matched row
            action_key = int(matched_row['action_key'].values[0])
            # Store the matched result in the same format as the original data
            matched_actions[key] = {"id": action_key, "action_name": action_name}

    return matched_actions


def calculate_action_values(goal_numeric_value,country_properties,json_file_path_country_vs_actions_df):
    # Load the JSON file
    with open(json_file_path_country_vs_actions_df, 'r') as file:
        country_vs_actions_data = json.load(file)

    # Prepare a list to store the results
    results_list = []
    #read goal_vs_country data:
    goal_data =goal_vs_country(goal_numeric_value)
    country_properties_adjusted={}
    for country_goals, value in country_properties.items():
        country_properties_adjusted[country_goals] = value and goal_data[country_goals]
        # print(f"old value is {value} and new is {country_properties_adjusted[country_goals]}")
    # Iterate over each action
    for action_entry in country_vs_actions_data:
        action_name = action_entry['Action']
        action_properties = action_entry['properties']
        action_result = {"Action": action_name}  # Start with Action as the first key

        # Multiply matching properties
        for prop, value in action_properties.items():
            if prop in country_properties_adjusted and country_properties_adjusted[prop] == True:
                action_result[prop] = value * 1.0  # Convert "True" to 1.0
            elif prop in country_properties_adjusted and country_properties_adjusted[prop] == False:
                action_result[prop] = value * 0.0  # Convert "False" to 0.0

        # Add the result to the list
        results_list.append(action_result)

    # Convert the list to a DataFrame
    results_df = pd.DataFrame(results_list)

    # Ensure "Action" is the first column
    if 'Action' in results_df.columns:
        columns = ['Action'] + [col for col in results_df.columns if col != 'Action']
        results_df = results_df[columns]
    # Normalize
    Xj_max = results_df.iloc[:, 1:].max().max()
    results_df.iloc[:, 1:] = results_df.iloc[:, 1:] / Xj_max
    #sum
    w2 = results_df.iloc[:, 1:].sum(axis=1)
    # Create a new DataFrame with the summed values and column name 'w2'
    w2_df = pd.DataFrame(w2, columns=['w'])

    return w2_df


def goal_vs_country(goal_numeric_value):
    pairwise_comparison = \
        {1: {"Ambitious_renovator": False,"HighDHN": True,"HighElectrification": True,
            "Biomass": True,"Solar": True, "SmartHeating": True,"Allow_gas": False},
         2: {"Ambitious_renovator": True,"HighDHN": False,"HighElectrification": False,
            "Biomass": False,"Solar": True,"SmartHeating": True,"Allow_gas": False},
         3: {"Ambitious_renovator": False,"HighDHN": True,"HighElectrification": True,
            "Biomass": True,"Solar": True,"SmartHeating": True,"Allow_gas": False},
         4: {"Ambitious_renovator": False,"HighDHN": True,"HighElectrification": True,
            "Biomass": True,"Solar": True,"SmartHeating": True,"Allow_gas": False},
         5: {"Ambitious_renovator": False,"HighDHN": False,"HighElectrification": True,
            "Biomass": False,"Solar": True,"SmartHeating": True,"Allow_gas": False},
         6: {"Ambitious_renovator": False,"HighDHN": False,"HighElectrification": True,
            "Biomass": False,"Solar": True,"SmartHeating": False,"Allow_gas": False},
         7: {"Ambitious_renovator": True,"HighDHN": True,"HighElectrification": True,
            "Biomass": True,"Solar": True,"SmartHeating": True,"Allow_gas": False}
            }
    goal_data=pairwise_comparison.get(goal_numeric_value, "Goal not found")

    return goal_data


def get_goal_values(goal_name, json_file_path_goals_vs_actions_df):
    # Load the JSON file
    with open(json_file_path_goals_vs_actions_df, 'r') as file:
        data = json.load(file)

    # Iterate over each entry to collect the values for the specified goal
    goal_values = {}
    for entry in data:
        action = entry['Action']
        properties = entry['properties']

        # Check if the goal exists in the properties
        if goal_name in properties:
            goal_values[action] = properties[goal_name]

    # Convert dictionary to DataFrame
    goal_df = pd.DataFrame(list(goal_values.items()), columns=['Action', 'w'])
    return goal_df

def top_values(df):
    """
    This function generates a ranking of a DataFrame.

    Parameters
    ----------
    df : pandas.DataFrame
        The DataFrame to be ranked.

    Returns
    -------
    filtered_values : pandas.DataFrame
        The filtered values from the DataFrame (greater than 2/3),
        limited to 5 rows if there are more than 5.
    """
    # Filter the DataFrame to keep only values where 'w' > 2/3
    filtered_df = df[df['w'] > 2 / 3]

    # Sort the filtered DataFrame by 'w' in descending order
    top_5_values = filtered_df.sort_values(by='w', ascending=False)

    # If there are more than 5 rows, limit to the top 5
    if len(top_5_values) > 5:
        top_5_values = top_5_values.head(5)

    return top_5_values




#%%  BASIC BASELINE

def baseline_pathway_simple(data, front_data, demand_profile, building_consumption_dict):
    """
    Reads information for a specified number of buildings and their building use from the provided data.
    This function reads information for a specified number of buildings, 
    their building use, and the common consumption profile of the community.
    It then constructs dictionaries with building information and building asset context 
    based on the provided data and front-end information.
    Each building dictionary includes details such as building ID, area, construction year, 
    demand profile ID, and building use. The building asset context dictionary includes information 
    such as building ID, generation system profile ID, and calculated building consumption.

    Parameters
    ----------
    data : dict
        A dictionary containing information about the buildings, including statistics and generation system profiles.
    
    front_data : dict
        A dictionary containing front-end data about the community, such as the number of buildings and their use.

    Returns
    -------
    output_context_kpi_module : dict
        A dictionary containing the output context for the KPI module.
    """
    
    # Retrieve building characteristics
    common_construction_year = data["building_statistics"]["common_construction_year"]
    avg_surface = data["building_statistics"]["avg_surface_m2"]
    geom = front_data["location"]  # Analyze if geometry is included in the intermediate data
    num_building = front_data["num_building"]
    building_use = front_data["building_use_id"]
    
    # Initialize lists to store building and asset context dictionaries
    building_asset_context = []
    
    # Loop through each building
    for i in range(num_building):
        # Build the building dictionary
        building_id_key = f"building_id_1"
        # Get the building consumption data using the constructed key
        building_consumption = building_consumption_dict[building_id_key]
        # Build the building dictionary
        building_dict = {
            "generation_system_profile_id": building_consumption["generation_system_profile_id"],
            "building_energy_asset_id": None,
            "building_consumption_id": None,
            "building_id": None,
            "building_consumption": {
                "elec_consumption": building_consumption["elec_consumption"],
                "heat_consumption": building_consumption["heat_consumption"],
                "cool_consumption": building_consumption["cool_consumption"],
                "dhw_consumption": building_consumption["dhw_consumption"]
            },
            "building": {
                "geom": geom,
                "height": 6,  # meters
                "construction_year": common_construction_year,
                "building_use_id": building_use,
                "id": None,
                "area_conditioned": avg_surface*0.82, #correction for the complete area of the building
                "demandprofile_id": demand_profile["demand_profile"]["id"],
                "common_profile_id": front_data["common_profile"],
                "subdivision_community": 2,
                "subdivision_total": 6,
                "occupants": 3,
                "demandprofile": {
                    "heating_demand": demand_profile["demand_profile"]["heating_demand"],
                    "cooling_demand": demand_profile["demand_profile"]["cooling_demand"],
                    "dhw_demand": demand_profile["demand_profile"]["dhw_demand"],
                    "electricity_demand":  demand_profile["demand_profile"]["electricity_demand"],
                },
            }
        }
        building_asset_context.append(building_dict)   
            
    # Construct the output context
    output_context_kpi_module = {
        "context_parent": None,
        # "kpis": kpis.kpi_df,
        "building_asset_context": building_asset_context
    }
    
    # Create the "outputs" folder if it doesn't exist
    # output_folder = "outputs"
    # if not os.path.exists(output_folder):
    #     os.makedirs(output_folder)
    
    # # Save the JSON to a file
    # output_file = os.path.join(output_folder, "output_context.json")
    # with open(output_file, "w") as f:
        # json.dump(output_context_kpi_module, f, indent=4)
    
    # print("File saved successfully at:", output_file)
    
    # Return output context
    return output_context_kpi_module

# building_consumption_dict = generation_system_function(data=data, demand_profile=demand_profile)
def demand_statistics(data, front_data):
    """
    This function retrieves the demand profile for a community.

    Parameters
    ----------
    data : dict
        A dictionary containing information about building statistics profiles, including the demand profile.
    front_data : dict
        A dictionary containing front-end data about the community, the common demand profile of the buildings.
    
    Returns
    -------
    demand_profile : dict
        A dictionary containing the demand profile for the community.
            - id : int
                The ID of the demand profile.
            - heating_demand : list
                A list representing the heating demand profile.
            - cooling_demand : list
                A list representing the cooling demand profile.
            - dhw_demand : list
                A list representing the domestic hot water demand profile.
            - electricity_demand : list
                A list representing the electricity demand profile.
    """
    
    common_profile = front_data["common_profile"]
    if common_profile == 1: #STUDENTS # CHR01
        answer = {"usuario": 
            {"number_of_family_members": 2, 
             "number_of_people_working": 2, 
             "number_of_people_students": None,
             "number_of_people_retired": None,
             "number_of_toddler": None,
             "number_of_children": None,
             "number_of_adult_young": 2,
             "number_of_adult": None,
             "number_of_senior": None}  #This is the hosuehold characteristics coming from the UI
        }
    if common_profile == 2: #ADULT COUPLE #CHR02
        answer = {"usuario": 
            {"number_of_family_members": 2, 
             "number_of_people_working": 2, 
             "number_of_people_students": None,
             "number_of_people_retired": None,
             "number_of_toddler": None,
             "number_of_children": None,
             "number_of_adult_young": None,
             "number_of_adult": 2,
             "number_of_senior": None}  #This is the hosuehold characteristics coming from the UI
        }
    if common_profile == 3: #FAMILY WITH KIDS #CHR44
        answer = {"usuario": 
            {"number_of_family_members": 4, 
             "number_of_people_working": 1, 
             "number_of_people_students": 2,
             "number_of_people_retired": None,
             "number_of_toddler": None,
             "number_of_children": 2,
             "number_of_adult_young": None,
             "number_of_adult": 2,
             "number_of_senior": None}  #This is the hosuehold characteristics coming from the UI
        }
    if common_profile == 4: #RETIRED COUPLE #CHR16
        answer = {"usuario": 
            {"number_of_family_members": 2, 
             "number_of_people_working": None, 
             "number_of_people_students": None,
             "number_of_people_retired": 2,
             "number_of_toddler": None,
             "number_of_children": None,
             "number_of_adult_young": None,
             "number_of_adult": None,
             "number_of_senior": 2}  #This is the hosuehold characteristics coming from the UI
        }    
    route_base = os.path.join(os.path.dirname(os.path.abspath(__file__)), "Electricity_profiles")
    route_jsons = os.path.join(route_base, "Unique_Usuarios")
    route_csvs = os.path.join(route_base, "Electricity_Profiles_LPG_Hourly")
    profile = el.lpg_electricity_profile_generator(ruta_jsons=route_jsons, ruta_csvs=route_csvs, answer=answer)
    electricity_profile_df = profile.to_frame(name='electricity_demand')
    electricity_profile = electricity_profile_df['electricity_demand'].tolist()
    dict_demand_default = data['building_statistics']['demand_profile_default']
    demand_profile = {
        "demand_profile": {
            "id": 1,  # This ID might change depending on the number of demand profiles provided
            "heating_demand": dict_demand_default["heating_demand"],
            "cooling_demand": dict_demand_default["cooling_demand"],
            "dhw_demand": dict_demand_default["dhw_demand"],
            "electricity_demand":  electricity_profile,
        }
    }
        
    return demand_profile
#%%  INTERMEDIATE BASELINE

def calculate_areas(geojson_file):
    """
    Calculate the area of each polygon in a GeoJSON file.

    Parameters:
    geojson_object (str): Path to the GeoJSON file containing polygons.

    Returns:
    dict: A dictionary with polygon indices as keys and their respective areas as values.
    """

    areas = {}
    heights = {}
    community_demand = []
    
    for i, feature in enumerate(geojson_file['features']):
        geom = shape(feature['geometry'])
        area = geom.area
        height = feature['properties']['height']
        building_demand = {
            'id': feature['id'],
            'heating': feature['properties']['heating'],
            'cooling': feature['properties']['cooling'],
            'dhw': feature['properties']['dhw']
        } 
        areas[i] = area
        heights[i] = height
        community_demand.append(building_demand)
    return areas, heights, community_demand

def baseline_pathway_intermediate(data, front_data, geojson_file, demand_profile, building_consumption_dict):
    """
    Function to calculate baseline pathway intermediate.
    
    Parameters
    ----------
    data_intermediate : dict
        Intermediate data for the calculation.
    front_data_intermediate : dict
        Front-end intermediate data.
    geojson_file : dict
        GeoJSON data for the buildings.
    demand_profile : dict
        Demand profile information.
    building_consumption_dict : dict
        Dictionary with building consumption data.
    
    Returns
    -------
    output_context_kpi_module : dict
        The output context for the KPI module.
    """
    areas, heights, community_demand = calculate_areas(geojson_file=geojson_file)
    
    # Initialize lists to store building and asset context dictionaries
    building_asset_context = []
    building_id = 0
    # Loop through each building in the JSON data
    for buildings_id, item_output in enumerate(front_data):
        # Get the matching demand profile by index
        demand = demand_profile[buildings_id]["demand_profile"]
        
        # Construct the key for the building consumption dictionary
        building_id_key = f"building_id_{buildings_id + 1}"
        
        # Get the building consumption data using the constructed key
        building_consumption = building_consumption_dict[building_id_key]
        # Build the building dictionary
        building_dict = {
            "generation_system_profile_id": building_consumption["generation_system_profile_id"],
            "building_energy_asset_id": None,
            "building_consumption_id": None,
            "building_id": None,
            "building_consumption": {
                "elec_consumption": building_consumption["elec_consumption"],
                "heat_consumption": building_consumption["heat_consumption"],
                "cool_consumption": building_consumption["cool_consumption"],
                "dhw_consumption": building_consumption["dhw_consumption"]
            },
            "building": {
                "geom": item_output["geom"],
                "height": heights[buildings_id],  # meters
                "construction_year": item_output["construction_year"],
                "building_use_id": item_output["building_use_id"],
                "id": None,
                "area_conditioned": areas[buildings_id] * 0.82,  # correction for the complete area of the building
                "demandprofile_id": None,
                "common_profile_id": item_output["common_profile_id"],
                "subdivision_community": item_output["subdivision_community"],
                "subdivision_total": item_output["subdivision_total"],
                "occupants": item_output["occupants"],
                "demandprofile": {
                    "heating_demand": demand["heating_demand"],
                    "cooling_demand": demand["cooling_demand"],
                    "dhw_demand": demand["dhw_demand"],
                    "electricity_demand":  demand["electricity_demand"]
                },
            }
        }

        building_asset_context.append(building_dict)
        building_id +=1
    # Construct the output context
    output_context_kpi_module = {
        "context_parent": None,
        "building_asset_context": building_asset_context
    }
    
    # Create the "outputs" folder if it doesn't exist
    output_folder = "outputs"
    if not os.path.exists(output_folder):
        os.makedirs(output_folder)
    
    # Save the JSON to a file
    # output_file = os.path.join(output_folder, "output_context.json")
    # with open(output_file, "w") as f:
    #     json.dump(output_context_kpi_module, f, indent=4)

    return output_context_kpi_module

'''
###############################################
    BUILDINGS DEMAND 
###############################################
'''

def fetch_geojson(geojson_object):
    """
    Fetches a GeoJSON file from the API.

    Parameters:
    api_url (str): The URL of the API endpoint.
    payload (dict): The data to send in the POST request.

    Returns:
    dict: The GeoJSON object received from the API.
    """
    api_url = THERMAGRID_API_URL
    
    inputs_thermagrid = generate_demand_inputs(geojson_object=geojson_object)
    api_key = str(THERMAGRID_API_KEY)
    headers = {
        'Content-Type': 'application/json',
        'x-api-key': api_key
    }

    params_json = json.dumps(inputs_thermagrid, indent=2)
    #response = requests.post(api_url, json=params_json, data=api_key)
    response = requests.post(api_url, data=params_json, headers=headers, timeout=None)
    if response.status_code == 200:
        print("response 200 OK")
        geojson_file = response.json()
        return geojson_file
    else:
        response.raise_for_status()
        print("Error in response request")

def demand_thermagrid(data, front_data, geojson_file):
    """
    Reads demand data from a file and generates a demand profile for each user profile in the list.

    Parameters:
    data (dict): Dictionary containing the API request payload.
    front_data (list): List of dictionaries containing user profile data.

    Returns:
    list: List of generated demand profiles.
    """
    # api_url = 'http://teide:8101/calculate_demand_demand_post'  # Asegúrate de usar la URL correcta del endpoint de la API
    areas, heights, community_demand = calculate_areas(geojson_file=geojson_file)
    # areas = {}
    # heights = {}
    # community_demand = []

    # for i, feature in enumerate(geojson_file['features']):
    #     geom = shape(feature['geometry'])
    #     area = geom.area
    #     height = feature['properties']['height']
    #     building_demand = {
    #         'id': feature['id'],
    #         'heating': feature['properties'].get('heating', 0),
    #         'cooling': feature['properties'].get('cooling', 0),
    #         'dhw': feature['properties'].get('dhw', 0)
    #     }
    #     areas[i] = area
    #     heights[i] = height
    #     community_demand.append(building_demand)
    
    demand_profiles = []
    buildings_id = 0
    
    for buildings in front_data:
        common_profile = buildings["common_profile_id"]
        occupants = buildings["occupants"]
        answer = {}

        if common_profile == 1: # STUDENTS # CHR01
            answer = {
                "usuario": {
                    "number_of_family_members": occupants,
                    "number_of_people_working": occupants,
                    "number_of_people_students": None,
                    "number_of_people_retired": None,
                    "number_of_toddler": None,
                    "number_of_children": None,
                    "number_of_adult_young": occupants,
                    "number_of_adult": None,
                    "number_of_senior": None
                }
            }
        elif common_profile == 2: # ADULT COUPLE # CHR02
            answer = {
                "usuario": {
                    "number_of_family_members": occupants,
                    "number_of_people_working": occupants,
                    "number_of_people_students": None,
                    "number_of_people_retired": None,
                    "number_of_toddler": None,
                    "number_of_children": None,
                    "number_of_adult_young": None,
                    "number_of_adult": occupants,
                    "number_of_senior": None
                }
            }
        elif common_profile == 3: # FAMILY WITH KIDS # CHR44
            answer = {
                "usuario": {
                    "number_of_family_members": occupants,
                    "number_of_people_working": 2,
                    "number_of_people_students": (occupants - 2),
                    "number_of_people_retired": None,
                    "number_of_toddler": None,
                    "number_of_children": (occupants - 2),
                    "number_of_adult_young": None,
                    "number_of_adult": 2,
                    "number_of_senior": None
                }
            }
        elif common_profile == 4: # RETIRED COUPLE # CHR16
            answer = {
                "usuario": {
                    "number_of_family_members": occupants,
                    "number_of_people_working": None,
                    "number_of_people_students": None,
                    "number_of_people_retired": occupants,
                    "number_of_toddler": None,
                    "number_of_children": None,
                    "number_of_adult_young": None,
                    "number_of_adult": None,
                    "number_of_senior": occupants
                }
            }

        # Generate electricity profile
        route_base = os.path.join(os.path.dirname(os.path.abspath(__file__)), "Electricity_profiles")

        route_jsons = os.path.join(route_base, "Unique_Usuarios")
        route_csvs = os.path.join(route_base, "Electricity_Profiles_LPG_Hourly")
        profile = el.lpg_electricity_profile_generator(ruta_jsons=route_jsons, ruta_csvs=route_csvs, answer=answer)
        electricity_profile_df = profile.to_frame(name='electricity_demand')
        electricity_profile = electricity_profile_df['electricity_demand'].tolist()
        
        demand_profile = {
            "demand_profile": {
                "id": community_demand[buildings_id]['id'],  # Use the ID from community_demand
                "heating_demand": community_demand[buildings_id]['heating'],
                "cooling_demand": community_demand[buildings_id]['cooling'],
                "dhw_demand": community_demand[buildings_id]['dhw'],
                "electricity_demand": electricity_profile,
            }
        }
        buildings_id += 1
        demand_profiles.append(demand_profile)
        demand_profile = demand_profiles

    return demand_profile


def generate_demand_inputs(geojson_object):
    """
    Calculate temperatures and radiations based on TMY data and return a JSON with 
    the original GeoJSON, temperatures, and radiations.

    Parameters
    ----------
    geojson_input : dict
        The GeoJSON object containing the multipolygons.

    Returns
    -------
    dict
        A dictionary containing the original GeoJSON, temperatures, and calculated radiations.
    """
    URL = 'https://re.jrc.ec.europa.eu/api/v5_2/'

    # Calculate the centroid of the provided multipolygons
    multipolygons = [shape(feature['geometry']) for feature in geojson_object['features']]
    union_multipolygon = unary_union(multipolygons)
    centroid = union_multipolygon.centroid
    longitude, latitude = centroid.x, centroid.y
    
    #------------------------------------------------------
    # ASSUMES INPUT AND OUTPUT CRS IS EPSG 4326
    # IF NOT, IT MUST BE MODIFIED
    #------------------------------------------------------

    print("\n·····························")
    print("** LOCATION SUMMARY **")
    print("·····························")
    print(f"centroid: {centroid}")
    print(f"latitude: {latitude}")
    print(f"longitude: {longitude}")

    # Call PVGIS API (with pvlib) to get TMY data
    tmy_data, months_selected, inputs, meta = pvlib.iotools.get_pvgis_tmy(
        latitude, longitude, map_variables=False, url=URL)

    # Ensure 'tmy_data' index is in datetime format
    tmy_data.index = pd.to_datetime(tmy_data.index)

    # Define the location using 'inputs' data
    latitude = inputs['location']['latitude']
    longitude = inputs['location']['longitude']
    site = Location(latitude, longitude)  # Use Location class directly

    # Get solar data
    solar_position = site.get_solarposition(times=tmy_data.index)

    # Define orientations of vertical surfaces
    orientations = {
        'rad_n': 0,
        'rad_s': 180,
        'rad_e': 90,
        'rad_o': 270  # 'rad_o' changed to 'rad_w' for clarity
    }

    # Tilt angle (90 degrees for vertical surfaces)
    tilt_angle = 90

    # Create the output dictionary (json)
    inputs_thermagrid = {
        "geojson": geojson_object,  # Provided GeoJSON
        "temperature": tmy_data['T2m'].tolist()  # Temperature list
    }

    for orientation_name, azimuth_angle in orientations.items():
        irradiance = pvlib.irradiance.get_total_irradiance(
            surface_tilt=tilt_angle,
            surface_azimuth=azimuth_angle,
            solar_zenith=solar_position['apparent_zenith'],
            solar_azimuth=solar_position['azimuth'],
            dni=tmy_data['Gb(n)'],
            ghi=tmy_data['G(h)'],
            dhi=tmy_data['Gd(h)'],
        )
        
        inputs_thermagrid[orientation_name] = irradiance['poa_global'].tolist()  # Radiation list

    # Create the "outputs" folder if it doesn't exist
    output_folder = "outputs"
    if not os.path.exists(output_folder):
        os.makedirs(output_folder)
    
    # Save the JSON to a file
    # output_json = os.path.join(output_folder, "inputs_thermagrid.json")
    # with open(output_json, "w") as f:
    #     json.dump(inputs_thermagrid, f, indent=4)
        
    return inputs_thermagrid

def generate_geojson(front_data):
    """
    Generates a GeoJSON object from the input data and saves it to the 'outputs' folder.

    Parameters:
    front_data (list): A list of dictionaries containing building information.

    Returns:
    dict: A GeoJSON object with the building information.
    """
    gdf = gpd.GeoDataFrame(front_data)
    gdf["geometry"]=gdf["geom"].apply(wkt.loads)
    gdf.set_geometry("geometry")
    gdf.drop("geom",axis=1)
    gdf.set_crs(epsg=SRID, inplace=True)
    gdf["id"] = range(1, len(gdf) + 1)
    gdf["use"] = gdf["building_use_id"].map(building_use_mapping)
    gdf["height"] = 6
    gdf["year"] = gdf["construction_year"]
    gdf["heating_system"] = 1
    gdf["cooling_system"] = 2

    return json.loads(gdf.to_json())

