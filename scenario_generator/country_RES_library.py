# -*- coding: utf-8 -*-
"""
Dependencies:
    pillow                    10.2.0
    pandas                    2.2.0
    
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

***********************************************************************************************

This part of the code manages and creates the Country class

***********************************************************************************************

"""
        
import json
import os
import csv
import pandas as pd

#Class country  
#it must have a name and country code
#any other data you want to add is up to you !
class Country:
    def __init__(self, name, country_code, *args, **kwargs):
        self.name = name
        self.country_code = country_code
        self.additional_info = kwargs
        #*args collects any additional positional arguments, and
        #**kwargs collects any additional keyword arguments. 
        #The attributes are then set based on the values passed in kwargs
        #This allows for flexibility in initializing the object with 
        #additional attributes beyond name and country_code.
        for key, value in kwargs.items():
            setattr(self, key, value)

    def __str__(self):
        return f"Country: {self.name}, Country Code: {self.country_code}"
    def get_all_attributes(self):
        attributes = {'name': self.name, 'country_code': self.country_code}
        attributes.update(vars(self))
        return attributes

def country_res_recommendations (country_code):
    #read the recommended scenarios per country according to scenarios from https://www.researchgate.net/publication/333371930_Development_of_Energy_demand_for_buildings_industry_and_transport_in_the_SET-Nav_pathways_-_WP5_Summary_report
    recommendations='country_scenarios_recomended.csv'
    json_file_path= os.path.join(os.path.dirname(os.path.abspath(__file__)),
                                 'data', 'RESlibrary','country_scenarios_recommended.json')
    # Load the JSON file
    with open(json_file_path, 'r') as file:
        data = json.load(file)

    # Iterate over each entry to find the properties for the specified country
    for entry in data:
        if entry['Country'] == country_code:
            properties = {
                "Ambitious_renovator": eval(entry['properties']["Ambitious_renovator"]),
                "HighDHN": eval(entry['properties']["HighDHN"]),
                "HighElectrification": eval(entry['properties']["HighElectrification"]),
                "Biomass": eval(entry['properties']["Biomass"]),
                "Solar": eval(entry['properties']["Solar"]),
                "SmartHeating": eval(entry['properties']["SmartHeating"]),
                "Allow_gas": eval(entry['properties']["Allow_gas"]),
            }
            return properties

    # If the country is not found, return an empty dictionary or a message
    return f"No data found for country: {country_code}"
    
#read csvs and create the class country from it
def country_library(country_code):

    # Define the path to the directory containing the CSV files
    directory_path = os.path.join(os.getcwd(), 'data', 'RESlibrary', 'Country_data')
    
    # List all files in the directory
    files = os.listdir(directory_path)
    
    # Filter out only the CSV files
    csv_files = [file for file in files if file.endswith('.csv')]
    # Create a dictionary that will contain all RES data
    res_dic={}
    res_dic_filtered={}
    # Loop through each CSV file and read its content
    for csv_file in csv_files:
        file_path = os.path.join(directory_path, csv_file)
        # Read CSV file into a DataFrame
        df = pd.read_csv(file_path)
        # Save DataFrame into dictionary with filename as key
        res_dic[csv_file] = df
        # Apply the mask to filter the DataFrame
        mask = df['Country'] == country_code
        filtered_df = df[mask]
        # Update the DataFrame in the csv_data dictionary with the filtered DataFrame
        res_dic_filtered[csv_file]=filtered_df
    
    # Create a base Country object
    country_object = Country(name=res_dic_filtered['country.csv']['name'].iloc[0],country_code=country_code)
    # Iterate through each CSV file and its corresponding DataFrame
    for csv_file, df in res_dic_filtered.items():
        if not df.empty:  # Check if the DataFrame is not empty
            # Iterate through each column (except the first one, assuming it's 'Country')
            for column_name in df.columns:
                if column_name == 'Country':
                    continue
                # Add each attribute to the Country object
                setattr(country_object, column_name, df[column_name].iloc[0])

    return res_dic_filtered, country_object
    # del filtered_df, df, mask    


# # Create an object for Austria ('AT') using information from CSV files
# dic, AT, country_recommended_scenarios_df = country_res_library(country_code='AT')
# print(AT)
# all_attributes = AT.get_all_attributes()
# print(all_attributes)


#the inputs from the user interface will be stored in a json file that will connect with this module
def assign_country_from_json():
    # Define the path to the JSON file, e.g. json= 'inputs_user.json'
    
    file_path = os.path.join(os.getcwd(), 'data','inputs_user.json')
    
    # Read the JSON data from the file
    with open(file_path, 'r') as file:
        inputs_users = json.load(file)
    print(json)
    
    dic, country = country_library(country_code=inputs_users['country'])
    country_recommended_scenarios_df=country_res_recommendations (country_code=inputs_users['country'])
    return  inputs_users , country, country_recommended_scenarios_df