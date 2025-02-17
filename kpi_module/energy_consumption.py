# -*- coding: utf-8 -*-
"""
Created on Mon Mar 18 11:56:09 2024

@author: iciber
"""
'''
-------------------------------------------------------------------------------
numpy                         1.26.4
jsonschema                    4.19.2
jsonschema-specifications     2023.7.1
pandas                        2.2.1
Python                        3.9
spyder                        5.5.1
-------------------------------------------------------------------------------

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

'''

"""

Explanation of the script:

1- Accessing Database Information:
The function generation_system_function accesses the database to retrieve the parameters needed to calculate consumption and creates a dictionary for each system:
generation_system_profile = {
    "heating_system": {
        "system_type": EC_type,
        "fuel_yield_1": FY_1,
        "fuel_yield_2": FY_2,
    } 
}
Calling the energy_consumption Function:
The dictionary {} is passed to the energy_consumption function, where it first filters the type of system being processed and patches it if the corresponding demand exists in the demand profile.
Example:
    if 'heating_system' in generation_system_profile and 'heating_demand' in demand_profile:
    If this condition is true, consumption is calculated using fuel_yield_1 and the demand profile.

Assumption: All cases of generation_system have fuel_yield_2 = 0, except for CHP systems. However, no baseline case is derived from this technology, so filtering for fuel_yield_2 is not applied.

Returning to generation_system_function:
Once the consumption profile is calculated, the script returns to the generation_system_function to save the profile and continue with the next system.

The function ultimately returns:
building_consumption_dict[f"building_id_{i+1}"] = {    
    "elec_consumption": electricity_consumption,
    "heat_consumption": heating_consumption,
    "cool_consumption": cooling_consumption,
    "dhw_consumption": dhw_consumption,
    "generation_system_profile_id": generation_system_profile_id 
}
"""
# Define constants for recurring string literals
ELECTRICITY_CONSUMPTION = "elec_consumption"
HEAT_CONSUMPTION = "heat_consumption"
COOL_CONSUMPTION = "cool_consumption"
DHW_CONSUMPTION = "dhw_consumption"
FUEL_YIELD_1="fuel_yield1"



def generation_system_function(front_data, data, demand_profile):
    """
    This function processes data related to generation systems and calculates energy consumption based on the provided profiles.
    It reads information about generation system profiles, including heating, cooling, electricity, and DHW systems. It then iterates through each system and calculates the energy consumption.

    Parameters
    ----------
    front_data : list or dict
        A list or dictionary containing building data.
    data : list or dict
        A list or dictionary containing information about generation system profiles, demand profiles, and building statistics.
    demand_profile : list or dict
        A list or dictionary containing information about demand profiles for heating, cooling, electricity, and DHW.

    Returns
    -------
    building_consumption_dict : dict
        A dictionary containing the calculated energy consumption values for each building.
    """
    building_consumption_dict = {}

    # Count the number of buildings in front_data
    if isinstance(front_data, list):
        items = [item for item in front_data if "building_use_id" in item]
    elif isinstance(front_data, dict):
        items = [front_data] if "building_use_id" in front_data else []

    for i, item in enumerate(items):
        # Caso 1: building_statistics_profile_id está en front_data
        if "building_statistics_profile_id" in item:
            print(f'{item}')
            building_statistics_profile_id = item["building_statistics_profile_id"]

            building_profile = next(
                (profile for profile in data if profile.get("id") == building_statistics_profile_id), None)
            generation_system_p = building_profile.get("generation_system_profile", {})
            demand_profile_for_building = demand_profile[i].get("demand_profile", {})

            # Initialize lists to store generation system profiles and consumption values
            heating_consumption = []
            electricity_consumption = []
            dhw_consumption = []
            cooling_consumption = []

            # Extract individual system profiles
            heating_system = generation_system_p.get("heating_system", {})
            electricity_system = generation_system_p.get("electricity_system", {})
            dhw_system = generation_system_p.get("dhw_system", {})
            cooling_system = generation_system_p.get("cooling_system", {})
            generation_system_profile_id = generation_system_p.get("id", {})
        else:
            building_statistics_profiles = data.get("building_statistics_profile", [])
            # Initialize dictionaries to store generation system information and consumption values
            if isinstance(building_statistics_profiles, dict):
                building_statistics_profiles = [building_statistics_profiles]

            # Loop through each building's statistics profile
            for building_profile in building_statistics_profiles:
                # Extract generation system information for each building
                generation_system_p = building_profile["generation_system_profile"]
                demand_profile_for_building = demand_profile["demand_profile"]
                # Initialize lists to store generation system profiles and consumption values
                generation_system_profile_list = []
                heating_consumption = []
                electricity_consumption = []
                dhw_consumption = []
                cooling_consumption = []

                # Extract individual system profiles
                heating_system = generation_system_p.get("heating_system", {})
                electricity_system = generation_system_p.get("electricity_system", {})
                dhw_system = generation_system_p.get("dhw_system", {})
                cooling_system = generation_system_p.get("cooling_system", {})
                generation_system_profile_id = generation_system_p.get("id", {})

        # Processing heating system
        if heating_system:
            EC_type = "heating_demand"
            demand_profile_list=demand_profile_for_building[EC_type]
            FY_1 = heating_system.get(FUEL_YIELD_1)
            heating_consumption = energy_consumption_function(fuel_yield1=FY_1,demand_profile_list=demand_profile_list)
            if heating_consumption is None:
                heating_consumption = [0] * 8760
        else:
            heating_consumption = [0] * 8760

        # Processing electricity system
        if electricity_system:
            EC_type = "electricity_demand"
            FY_1 = 1
            demand_profile_list=demand_profile_for_building[EC_type]
            electricity_consumption =energy_consumption_function(fuel_yield1=FY_1,demand_profile_list=demand_profile_list)
            if electricity_consumption is None:
                electricity_consumption = [0] * 8760
        else:
            electricity_consumption = [0] * 8760

        # Processing DHW system
        if dhw_system:
            EC_type = "dhw_demand"
            FY_1 = dhw_system.get(FUEL_YIELD_1)
            demand_profile_list=demand_profile_for_building[EC_type]
            dhw_consumption =energy_consumption_function(fuel_yield1=FY_1,demand_profile_list=demand_profile_list)
            if dhw_consumption is None:
                dhw_consumption = [0] * 8760
        else:
            dhw_consumption = [0] * 8760

        # Processing cooling system
        if cooling_system:
            EC_type = "cooling_demand"
            FY_1 = cooling_system.get(FUEL_YIELD_1)
            FY_2 = cooling_system.get("fuel_yield2")
            generation_system_profile = {
                "cooling_system": {
                    "system_type": EC_type,
                    "fuel_yield_1": FY_1,
                    "fuel_yield_2": FY_2,
                }
            }
            demand_profile_list=demand_profile_for_building[EC_type]
            cooling_consumption =energy_consumption_function(fuel_yield1=FY_1,demand_profile_list=demand_profile_list)
            if cooling_consumption is None:
                cooling_consumption = [0] * 8760
        else:
            cooling_consumption = [0] * 8760

        building_consumption_dict[f"building_id_{i + 1}"] = {
            ELECTRICITY_CONSUMPTION: electricity_consumption,
            HEAT_CONSUMPTION: heating_consumption,
            COOL_CONSUMPTION: cooling_consumption,
            DHW_CONSUMPTION: dhw_consumption,
            "generation_system_profile_id": generation_system_profile_id
        }

    return building_consumption_dict
# %% ENERGY CONSUMPTION

def energy_consumption_function(fuel_yield1,demand_profile_list):
    '''
    This function calculates the energy consumption for different systems based on the provided generation system profiles and demand profiles.
    It iterates through each system in the generation system profile and checks if the corresponding demand exists in the demand profile. If the demand is present, it calculates the energy consumption using the fuel yield values of the respective systems.

    For heating demand:
    - It checks if heating demand is present in the generation system profile.
    - If present, it calculates the heating consumption based on the fuel yield for heating.
    - Then, it extends the consumption list with the calculated heating consumption.

    For DHW demand:
    - It checks if DHW demand is present in the generation system profile.
    - If present, it calculates the DHW consumption based on the fuel yield for DHW.
    - Then, it extends the consumption list with the calculated DHW consumption.

    For electricity demand:
    - It checks if electricity demand is present in the generation system profile.
    - If present, it calculates the electricity consumption based on the fuel yield for electricity.
    - Then, it extends the consumption list with the calculated electricity consumption.

    For cooling demand:
    - It checks if cooling demand is present in the generation system profile.
    - If present, it calculates the cooling consumption based on the fuel yield for cooling.
    - Then, it extends the consumption list with the calculated cooling consumption.

    Finally, it returns the list of consumption values for each generation system.

    Parameters
    ----------
    fuel_yiel1 : float
        efficiency (or fuel yield) of the heating, cooling, electricity, and DHW systems.

    demand_profile_list : dict
        A list with one demand profiles: heating, cooling, electricity, and DHW needs

    Returns
    -------
    consumption_per_generation_system : list
        A list containing the calculated energy consumption values for each generation system.


    '''

    consumption= [x/fuel_yield1 for x in demand_profile_list]



    return consumption
