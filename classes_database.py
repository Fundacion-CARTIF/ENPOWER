# -*- coding: utf-8 -*-
"""
Created on Wed Jun 12 11:52:35 2024

@author: andgab
"""

import numpy as np
import helpers.constants as cte
import json
import os



class BuildingEnergyAsset:
    def __init__(self, generation_system_id, pmaxmin_scalar,pmaxmax_scalar,
                 building_asset_context_id, name, **kwargs):
        self.generation_system_id = generation_system_id
        self.pmaxmin_scalar= pmaxmin_scalar
        self.pmaxmax_scalar=pmaxmax_scalar
        self.building_asset_context_id = building_asset_context_id if building_asset_context_id is not None else "no_id"
        self.name = name

        # Initialize time series data placeholders for input1, input2, output1, and output2
        self.input1 = []  # Represents electricity or other input1
        self.input2 = []  # Represents air or other input2
        self.output1 = []  # Represents heating demand or other output1
        self.output2 = []  # Empty by default
        self.generation_system_info={}
        # Optional Parameters
        self.pmaxmax = kwargs.get("pmaxmax", 1)  # Default to 1 if not provided
        self.ppminmax = kwargs.get("pminmax", 0)
        self.capex = kwargs.get("capex", 1000)
        self.opex = kwargs.get("opex", 0.01*self.capex)
        self.lifetime =kwargs.get("lifetime",20)
        self.availability_profile=kwargs.get("availability_profile", [])
        self.name=kwargs.get("name",f"asset_{building_asset_context_id}")


    def add_production_profile(self,production_profile):
        self.input1 = production_profile

    def calculate_inputs_and_outputs(self, demand, fuel_yield1, fuel_yield2, type="heat_pump"):
        """
        General method to calculate input1, input2 (e.g., electricity and air)
        based on demand and fuel_yield. You can specify the input_type as 'electricity' or another.
        """
        for d in demand:
            if type == "heat_pump":
                input1_value = d / fuel_yield1
                input2_value = (fuel_yield1 - 1) * input1_value
            else:
                input1_value = d / fuel_yield1
                input2_value=[]
                if fuel_yield2 is not None:
                    output2_value = d*fuel_yield2
                    self.output2 = output2_value

            self.input1.append(input1_value)
            self.input2.append(input2_value)

        # Store demand in output1 or output2 based on the context
        self.output1 = demand  # This could represent heating demand or another output
    def add_generation_systems_info(self,Generation_system_info):
        self.generation_system_info = Generation_system_info


    def to_dict(self):
        """Convert the object to a dictionary matching the required JSON structure."""
        return {
                "id_temp": None,
                "generation_system_id": self.generation_system_id,
                "pmaxmin_scalar": self.pmaxmin_scalar,
                "availability_ts_id": None,
                "pmax_scalar": None,
                "pmaxmax_scalar": self.pmaxmax_scalar,
                "building_asset_context_id": self.building_asset_context_id,
                "availability_ts": {
                    "temp_id": None,
                    "name": self.name,
                    "value_input1": self.input1,
                    "value_input2": self.input2,
                    "value_output1": self.output1,
                    "value_output2": self.output2,
                    "testcase": "TC_0"
                },
                "generation_system": self.generation_system_info

            }


class CommunityEnergyAsset:
    def __init__(self, generation_system_id, pmaxmin_scalar, pmaxmax_scalar, input_node_geom, output_node_geom, name):
        self.generation_system_id = generation_system_id
        self.pmaxmin_scalar = pmaxmin_scalar
        self.pmaxmax_scalar = pmaxmax_scalar
        self.input_node_geom = input_node_geom
        self.output_node_geom= output_node_geom
        self.name = name

        # Initialize time series data placeholders for input1, input2, output1, and output2
        self.input1 = []  # Represents electricity or other input1
        self.input2 = []  # Represents air or other input2
        self.output1 = []  # Represents heating demand or other output1
        self.output2 = []  # Empty by default
        self.generation_system_info = {}
        self.pmax_scalar=None
    def add_input1_profile(self, input1_profile):
        self.input1 = input1_profile

    def add_generation_systems_info(self, Generation_system_info):
        self.generation_system_info = Generation_system_info

    def add_inputs_ARTELYS(self, inputs_ARTELYS):
        self.pmax_scalar = inputs_ARTELYS.get("pmax_scalar", {})
        self.input1 = inputs_ARTELYS.get("availability_ts", {}).get("value_input1", [])
        self.input2 = inputs_ARTELYS.get("availability_ts", {}).get("value_input2", [])
        self.output1 = inputs_ARTELYS.get("availability_ts", {}).get("value_output1", [])
        self.output2 = inputs_ARTELYS.get("availability_ts", {}).get("value_output2", [])
    def to_dict(self):
        """Convert the object to a dictionary matching the required JSON structure."""
        return {
                "id_temp": None,
                "generation_system_id":  self.generation_system_id,
                "pmaxmin_scalar": self.pmaxmin_scalar,
                "availability_ts_id": None,
                "pmax_scalar":  self.pmax_scalar,
                "pmaxmax_scalar": self.pmaxmax_scalar, #1MW
                "input_node_id": None,
                "output_node_id": None,
                "input_node": {
                    "id_temp": None,
                    "context_id": None,
                    "geom": self.input_node_geom,
                    "name": self.name
                },
                "output_node": {
                    "id_temp": None,
                    "context_id": None,
                    "geom": self.output_node_geom,
                    "name": self.name
                },
                "availability_ts": {
                    "id_temp": None,
                    "value_input1": self.input1,
                    "value_input2": self.input2,
                    "value_output1": self.output1,
                    "value_output2": self.output2,
                    "testcase": "TC_0",
                    "name": "multi_time_series"
                },
                "generation_system": self.generation_system_info
    }



class BuildingConsumption:
    """
    Represents building consumption dict
    Attributes:
        building (dict): Detailed information about the building.
        building_consumption (dict): Information about the building's energy consumption.
    """
    
    def __init__(self, building_consumption_id_temp,elec_consumption):
        self.building_consumption_id_temp = building_consumption_id_temp
        hours_in_year = 8760  # 8760 hours for a year-long hourly model
        # Initialize time series data placeholders for input1, input2, output1, and output2
        self.heat_consumption = [0] * hours_in_year  # Empty by default
        self.dhw_consumption = [0] * hours_in_year # Empty by default
        # Check if elec_consumption is None, if so, fill with zeros
        if elec_consumption is None:
            self.elec_consumption = [0] * hours_in_year
        else:
            self.elec_consumption = elec_consumption
        self.cool_consumption = [0] * hours_in_year  # Empty by default
    def add_existing_consumptions(self,heat_consumption,dhw_consumption,cool_consumption):
        self.heat_consumption = heat_consumption  # Empty by default
        self.dhw_consumption = dhw_consumption# Empty by default
        self.cool_consumption = cool_consumption # Empty by default

    def to_dict(self):
        return {
                cte.ID: self.building_consumption_id_temp,
                cte.HEAT_CONSUMPTION: self.heat_consumption,
                cte.DHW_CONSUMPTION: self.dhw_consumption,
                cte.ELECTRICITY_CONSUMPTION: self.elec_consumption,
                cte.COOL_CONSUMPTION: self.cool_consumption
        }

    def re_calculate_consumption(self, demand, fuel_yield1, type=cte.HEAT_CONSUMPTION):
        """
               General method to calculate consumption based on demand and fuel_yield1.
               Parameters:
                   demand (list): A list of demand array values [8760 values per type of demand]
                   fuel_yield1 (float): A yield value to adjust consumption.
                   type (str): The type of consumption to update (default is 'heat_consumption').
               """
        hours_in_year = 8760  # 8760 hours for a year-long hourly model

        # If demand is None or fuel_yield1 is None, set consumption to zeros
        if demand is None or fuel_yield1 is None:
            output = [0] * hours_in_year
        else:
            if fuel_yield1 == 0:
                raise ValueError("fuel_yield1 cannot be zero.")  # Prevent division by zero

            # Calculate consumption based on demand and fuel_yield1
            output = [x / fuel_yield1 for x in demand]

        # Assign the output to the appropriate consumption type
        if type == cte.HEAT_CONSUMPTION:
            self.heat_consumption = output
        elif type == cte.DHW_CONSUMPTION:
            self.dhw_consumption = output
        elif type == cte.COOL_CONSUMPTION:
            self.cool_consumption = output

class BuildingDemand:
    def __init__(self, electricity_consumption):
        hours_in_year = 8760  # 8760 hours for a year-long hourly model
        # Initialize time series data placeholders for input1, input2, output1, and output2
        self.heating_demand = [0] * hours_in_year  # Empty by default
        self.dhw_demand = [0] * hours_in_year  # Empty by default
        # Check if elec_consumption is None, if so, fill with zeros
        # Check if elec_consumption is None, if so, fill with zeros
        if electricity_consumption is None:
            self.electricity_demand = [0] * hours_in_year
        else:
            self.electricity_demand = electricity_consumption
        self.cooling_demand = [0] * hours_in_year  # Empty by defaul
 
    def to_dict(self):
        return {
            cte.HEATING_DEMAND: self.heating_demand,
            cte.DHW_DEMAND: self.dhw_demand,
            cte.ELECTRICITY_DEMAND: self.electricity_demand,
            cte.COOLING_DEMAND: self.cooling_demand
        }
 
    def re_calculate_demand(self, consumption, fuel_yield1, type=cte.HEATING_DEMAND):
        """
               General method to calculate demand based on consumption and fuel_yield1.
               Parameters:
                   consumption (list): A list of demand array values [8760 values per type of demand]
                   fuel_yield1 (float): A yield value to adjust consumption.
                   type (str): The type of consumption to update (default is 'heat').
               """
        hours_in_year = 8760  # 8760 hours for a year-long hourly model
 
        # If demand is None or fuel_yield1 is None, set consumption to zeros
        if consumption is None or fuel_yield1 is None:
            output = [0] * hours_in_year
        else:
            # Calculate consumption based on demand and fuel_yield1
            output = [x * fuel_yield1 for x in consumption]
 
        # Assign the output to the appropriate consumption type
        if type == cte.HEATING_DEMAND:
            self.heating_demand = output
        elif type == cte.DHW_DEMAND:
            self.dhw_demand = output
        elif type == cte.COOLING_DEMAND:
            self.cooling_demand = output


class Building_data:
    def __init__(self, id,**kwargs):
        self.id = id
        self.name = None
        # Optional Parameters
        self.building_consumption={}
        self.building_energy_assets = {}
        self.geometry = kwargs.get(cte.GEOMETRY, None)
        self.construction_year = kwargs.get(cte.CONSTRUCTION_YEAR, None)
        self.building_use_id = kwargs.get(cte.BUILDING_USE_ID, None)
        self.subdivision_community = kwargs.get(cte.SUBDIVISION_COMMUNITY, None)
        self.subdivision_total=kwargs.get(cte.SUBDIVISION_TOTAL, None)
        self.generation_system_for_electricity=kwargs.get(cte.ELECTRICITY_SYSTEM, None)
        self.generation_system_for_dhw=kwargs.get(cte.DHW_SYSTEM, None)
        self.generation_system_for_cooling=kwargs.get(cte.COOLING_SYSTEM, None)
        self.generation_system_for_heating=kwargs.get(cte.HEATING_SYSTEM, None)
        self.building_demand={}
    def associate_building_data(self,building):
        """
        Args:
            building= {
                    "id": 291,
                    "common_profile_id": 2,
                    "area_conditioned": 1.0765222400168464e-08,
                    "construction_year": 1989.0,
                    "subdivision_community": 4,
                    "subdivision_total": 3,
                    "geom": "POLYGON ((-3.8568252 36.9550853, -3.8567684 36.9550295, -3.85691 36.9549374, -3.8569668 36.9549931, -3.8568252 36.9550853))",
                    "height": 6.0,
                    "demandprofile_id": 212,
                    "building_use_id": 1,
                    "occupants": 4
                },

        Returns:

        """
        self.geometry = building.get(cte.GEOMETRY, None)
        self.construction_year = building.get(cte.CONSTRUCTION_YEAR, None)
        self.building_use_id = building.get(cte.BUILDING_USE_ID, None)
        self.subdivision_community = building.get(cte.SUBDIVISION_COMMUNITY, None)
        self.subdivision_total = building.get(cte.SUBDIVISION_TOTAL, None)
    def associate_building_consumption(self,consumption_data):
        elec_consumption = [float(value) for value in consumption_data.get(cte.ELECTRICITY_CONSUMPTION, [])]
        dhw_consumption = [float(value) for value in consumption_data.get(cte.DHW_CONSUMPTION, [])]
        heat_consumption = [float(value) for value in consumption_data.get(cte.HEAT_CONSUMPTION, [])]
        cool_consumption = [float(value) for value in consumption_data.get(cte.COOL_CONSUMPTION, [])]

        building_consumption_id_temp = consumption_data.get("id", None)
        building_consumption =BuildingConsumption(building_consumption_id_temp,elec_consumption=elec_consumption)
        building_consumption.add_existing_consumptions(heat_consumption, dhw_consumption, cool_consumption)
        self.building_consumption=building_consumption
    def associate_building_demand(self):
        electricity_demand = self.building_consumption.elec_consumption
        building_demand = BuildingDemand(electricity_consumption=electricity_demand)
        if self.generation_system_for_dhw is None:
            fuel_yield1_dhw = 0 #demanda nula porque sistema nulo, y no se cubre
        else:
            fuel_yield1_dhw = self.generation_system_for_dhw.get(cte.FUEL_YIELD_1, 0)
        if self.generation_system_for_cooling is None:
            fuel_yield1_cooling =0 #demanda nula porque sistema nulo, y no se cubre
        else:
            fuel_yield1_cooling = self.generation_system_for_cooling.get(cte.FUEL_YIELD_1, 0)
        if self.generation_system_for_heating is None:
            fuel_yield1_heating = 0 #demanda nula porque sistema nulo, y no se cubre
        else:
            fuel_yield1_heating =  self.generation_system_for_heating.get(cte.FUEL_YIELD_1, 0)
        building_demand.re_calculate_demand(consumption=self.building_consumption.dhw_consumption,
                                            fuel_yield1=fuel_yield1_dhw
                                            , type=cte.DHW_DEMAND)
        building_demand.re_calculate_demand(consumption=self.building_consumption.heat_consumption,
                                            fuel_yield1=fuel_yield1_heating, type=cte.HEATING_DEMAND)
        building_demand.re_calculate_demand(consumption=self.building_consumption.cool_consumption,
                                            fuel_yield1=fuel_yield1_cooling, type=cte.COOLING_DEMAND)
        self.building_demand = building_demand.to_dict()
    def associate_generation_system_info(self,generation_system_profile):
        self.generation_system_for_electricity=generation_system_profile.get(cte.ELECTRICITY_SYSTEM, None)
        self.generation_system_for_dhw=generation_system_profile.get(cte.DHW_SYSTEM, None)
        self.generation_system_for_cooling=generation_system_profile.get(cte.COOLING_SYSTEM, None)
        self.generation_system_for_heating=generation_system_profile.get(cte.HEATING_SYSTEM, None)
    def associate_building_energy_asset(self,building_energy_assets_of_the_building):
        building_energy_assets={}
        for building_energy_asset_data in building_energy_assets_of_the_building:
            name=building_energy_asset_data.get(cte.AVAILABILITY_TS,None).get(cte.NAME,None)
            # Safely access keys with .get()
            generation_system_id = building_energy_asset_data.get("generation_system_id", None)
            generation_system_info = building_energy_asset_data.get("generation_system", None)
            capex = generation_system_info.get("capex_eur_kw", 1000)
            # Create BuildingEnergyAsset instance
            building_energy_assets[name] = BuildingEnergyAsset(
                generation_system_id=generation_system_id,
                pmaxmin_scalar=building_energy_asset_data.get("pmaxmin_scalar", None),
                pmaxmax_scalar=building_energy_asset_data.get("pmaxmax_scalar", None),
                building_asset_context_id=building_energy_asset_data.get("building_asset_context_id", None),
                name=building_energy_asset_data.get("availability_ts", {}).get("name", None),
                capex=capex,
                opex=generation_system_info.get("opex_eur_kwh_year", 0.01 * capex),
                lifetime=generation_system_info.get("lifetime_years", 20),
            )

            generation_profile = []
            if generation_system_id == 83:
                generation_profile = [
                    float(value) for value in
                    building_energy_asset_data.get("availability_ts", {}).get("value_input1", [])
                ]
            building_energy_assets[name].add_production_profile(generation_profile)

        self.building_energy_assets=building_energy_assets

def testing_classes():
    import os
    # %% Load the JSON file
    file_path_bd = os.path.join(os.getcwd(), 'data', 'community_context_updated_2_granada.json')

    try:
        with open(file_path_bd, 'r') as file:
            bd = json.load(file)
    except (IOError, json.JSONDecodeError) as e:
        print(f"Error loading JSON file: {e}")
        exit()
    print("this is a test")
    buildings = {}  # Use a dictionary instead of a list

    for context in bd.get(cte.BUILDING_ASSET_CONTEXT, []):
        id = context.get(cte.BUILDING_ID, None)
        if id is not None:  # Ensure id is valid
            buildings[id] = Building_data(id=id)
            # Extract consumption profiles
            consumption_data = context.get(cte.BUILDING_CONSUMPTION, {})
            buildings[id].associate_building_data(building=context.get(cte.BUILDING, {}))
            buildings[id].associate_building_consumption(consumption_data)
            buildings[id].associate_generation_system_info(generation_system_profile=context.get(cte.GENERATION_SYSTEM_PROFILE, {}))
            if context.get(cte.BUILDING_ENERGY_ASSET, []):
                buildings[id].associate_building_energy_asset(building_energy_assets_of_the_building=context.get(cte.BUILDING_ENERGY_ASSET, []))
    print("this is a test")

class FinalEnergy:
    def __init__(self, id):
        self.id = id
        self.name = None
        self.final = False
        self._hourly_data = [0] * 8760  # Using a leading underscore to indicate this is "private" and a method is assigned
                                        #to recalculate monthly and yearly data every time hourly data is changed
        self.monthly_data = [0] * 12
        self.yearly_data = 0
        self.recalculate()  # Initial calculation

    @property
    def hourly_data(self):
        return self._hourly_data

    @hourly_data.setter
    def hourly_data(self, new_hourly_data):
        #the setter is used: e.g. energy_instance.hourly_data = new_hourly_data  # This triggers the setter
        if len(new_hourly_data) != 8760:
            raise ValueError("Hourly data must have 8760 entries.")
        self._hourly_data =  [0 if value is None else value for value in new_hourly_data]
        self.recalculate()  # Recalculate monthly and yearly data when hourly data changes

    def recalculate(self):
        """ Recalculate the monthly and yearly data whenever hourly data is changed """
        self.monthly_data = self.calculate_monthly(self._hourly_data)
        self.yearly_data = sum(self._hourly_data)

    def calculate_monthly(self, hourly_data):
        # Define the number of hours per month in a non-leap year
        hours_per_month = [744, 672, 744, 720, 744, 720, 744, 744, 720, 744, 720, 744]
        monthly_data = []
        start = 0
        for hours in hours_per_month:
            monthly_data.append(sum(hourly_data[start:start + hours]))
            start += hours
        return monthly_data

    def final_energy_to_dic(self):
        return {
            "name": self.name,
            "final": self.final,
            "hour": self._hourly_data[:],  # return a copy of the list
            "month": self.monthly_data[:],  # return a copy of the list
            "year": self.yearly_data
        }

    def add_new_consumption(self, consumption):
        """
        Adds new fuels or electricity consumption to the current _hourly_data for the energy carrier
        :param consumption: List of 8760 values representing the new consumption to add.
        """
        if len(consumption) != 8760:
            raise ValueError("Consumption data must have 8760 entries.")
        # Add each hour's consumption to the existing _hourly_data
        self._hourly_data =[self._hourly_data[i] + (consumption[i] if consumption[i] is not None else 0) for i in range(8760)]
        # Recalculate monthly and yearly values after adding new consumption
        self.recalculate()



class BuildingKPIs:
    def __init__(self, final_energy_instance, kpi_data):
        """
        Initialize the BuildingKPIs object with the FinalEnergy instance and KPI data such as PEF_total, PEF_nren, etc.
        :param final_energy_instance: The FinalEnergy object for a specific energy carrier.
        :param kpi_data: A dictionary containing the external KPI factors for that energy carrier.For each energy carrier,
        you store the values for pef_tot, pef_nren, f_co2_eq_g_kwh, etc.
        For each energy carrier, the hourly KPIs will be calculated as products of FinalEnergy._hourly_data
        and the external factor.
        # Monthly and yearly values will also be calculated based on the hourly values.
        """
        self.final_energy = final_energy_instance
        self.energy_carrier_name=final_energy_instance.name
        self.energy_carrier_id = kpi_data['energy_carrier_id']
        self.pef_tot = kpi_data.get('pef_tot', 0.0)  # Default to 0 if None
        self.pef_nren = kpi_data.get('pef_nren', 0.0)  # Default to 0 if None
        self.f_co2_eq_g_kwh = kpi_data.get('f_co2_eq_g_kwh', 0.0)  # Default to 0 if None
        self.pef_ren = kpi_data.get('pef_ren', 0.0)  # Default to 0 if None

        if kpi_data.get('non_h_costs_eur_kwh', 0.0) == None:
            self.non_h_costs_eur_kwh = 0
        else:
            self.non_h_costs_eur_kwh=kpi_data.get('non_h_costs_eur_kwh', 0.0)  # Default to 0 if None

        if  kpi_data.get('house_costs_eur_kwh', 0.0)== None:
            self.house_costs_eur_kwh = 0  # Default to 0 if None
        else:
            self.house_costs_eur_kwh = kpi_data.get('house_costs_eur_kwh', 0.0)  # Default to 0 if None

        # Calculate the KPIs (hourly, monthly, yearly)
        self.calculate_kpis()

    def calculate_kpis(self):
        """
        Calculate the KPIs based on FinalEnergy's hourly data and the provided external factors.
        """
        # Perform element-wise calculation
        hourly_data = self.final_energy._hourly_data
        self.PEF_total = [hourly_data[i] * self.pef_tot for i in range(len(hourly_data))] #kWh
        self.PEF_nren = [hourly_data[i] * self.pef_nren for i in range(len(hourly_data))] #kWh
        self.PEF_ren = [hourly_data[i] * self.pef_ren for i in range(len(hourly_data))] #kWh
        self.co2 = [hourly_data[i] * self.f_co2_eq_g_kwh for i in range(len(hourly_data))] #g
        self.non_h_costs = [hourly_data[i] * self.non_h_costs_eur_kwh for i in range(len(hourly_data))] #euros
        self.household_costs = [hourly_data[i] * self.house_costs_eur_kwh for i in range(len(hourly_data))] #euros
        # Monthly KPIs in appropriate units (MWh, tonnes, k€)
        self.PEF_total_monthly = [value * 1e-3 for value in
                                  self.calculate_monthly(self.PEF_total)]  # Convert kWh to MWh
        self.PEF_nren_monthly = [value * 1e-3 for value in self.calculate_monthly(self.PEF_nren)]  # Convert kWh to MWh
        self.PEF_ren_monthly = [value * 1e-3 for value in self.calculate_monthly(self.PEF_ren)]  # Convert kWh to MWh
        self.co2_monthly = [value * 1e-6 for value in self.calculate_monthly(self.co2)]  # Convert grams to tonnes
        self.non_h_costs_monthly = [value * 1e-3 for value in
                                    self.calculate_monthly(self.non_h_costs)]  # Convert € to k€
        self.household_costs_monthly = [value * 1e-3 for value in
                                        self.calculate_monthly(self.household_costs)]  # Convert € to k€

        # Yearly KPIs in appropriate units (MWh, tonnes, k€)
        self.PEF_total_yearly = sum(self.PEF_total) * 1e-3  # Convert kWh to MWh
        self.PEF_nren_yearly = sum(self.PEF_nren) * 1e-3  # Convert kWh to MWh
        self.PEF_ren_yearly = sum(self.PEF_ren) * 1e-3  # Convert kWh to MWh
        self.co2_yearly = sum(self.co2) * 1e-6  # Convert grams to tonnes
        self.non_h_costs_yearly = sum(self.non_h_costs) * 1e-3  # Convert € to k€
        self.household_costs_yearly = sum(self.household_costs) * 1e-3  # Convert € to k€

    def calculate_monthly(self, hourly_data):
        """
        Calculate monthly data from hourly data. Based on the assumption of non-leap year.
        :param hourly_data: Array of hourly data (8760 values)
        :return: Monthly data (12 values)
        """
        hours_per_month = [744, 672, 744, 720, 744, 720, 744, 744, 720, 744, 720, 744]
        monthly_data = []
        start = 0
        for hours in hours_per_month:
            monthly_data.append(sum(hourly_data[start:start + hours]))
            start += hours
        return monthly_data

    def to_dict(self):
        """
        Return the KPIs as a dictionary, including hourly, monthly, and yearly values.
        """

        return {
            "energy_carrier_name":self.energy_carrier_name,
            "energy_carrier_id": self.energy_carrier_id,
            "PEF_total_hourly": self.PEF_total.tolist(),
            "PEF_total_monthly": self.PEF_total_monthly,
            "PEF_total_yearly": self.PEF_total_yearly,
            "PEF_nren_hourly": self.PEF_nren.tolist(),
            "PEF_nren_monthly": self.PEF_nren_monthly,
            "PEF_nren_yearly": self.PEF_nren_yearly,
            "PEF_ren_hourly": self.PEF_ren.tolist(),
            "PEF_ren_monthly": self.PEF_ren_monthly,
            "PEF_ren_yearly": self.PEF_ren_yearly,
            "co2_hourly": self.co2.tolist(),
            "co2_monthly": self.co2_monthly,
            "co2_yearly": self.co2_yearly,
            "non_h_costs_hourly": self.non_h_costs.tolist(),
            "non_h_costs_monthly": self.non_h_costs_monthly,
            "non_h_costs_yearly": self.non_h_costs_yearly,
            "household_costs_hourly": self.household_costs.tolist(),
            "household_costs_monthly": self.household_costs_monthly,
            "household_costs_yearly": self.household_costs_yearly
        }
