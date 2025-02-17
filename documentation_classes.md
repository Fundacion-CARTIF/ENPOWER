# How to Use the `Classes` 

## Overview
The `buildings` variable is a **dictionary** that should instantiate the Building_data class.
The idea is to assign data from the Context to Building_data to be used throughout the code.

For example, for `buildings` **dictionary**:
- The **keys** are building IDs (e.g., `291`, `292`).
- The **values** are instances of `Building_data`, each containing information about a building.

Each `Building_data` object has attributes such as:
- `building_consumption`: Energy consumption data (cooling, heating, electricity, etc.).
- `building_energy_assets`: Energy asset details. Energy assets are the ones optimised later on
- `construction_year`: Year of construction.
- `generation_systems`: Data about heating, dhw, cooling, and electricity systems.
- `geometry`: Building geometry (e.g., multipolygon coordinates).
- `subdivision_community` and `subdivision_total`: Subdivision details of the members of
the community and the total dwellings in a building, respectively

--- 

## 0. buildings dictionary is created and for each key, the classes are instantiated
```python
    import os
    import helpers.constants as cte
    from classes_database import Building_data
    import json
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
```

---

## 1. Accessing a Specific Building's Data
To retrieve details for a specific building (e.g., ID `291`):

```python
building_291 = buildings[291]  # Get the object
print(building_291.construction_year)  # Access construction year
print(building_291.geometry)  # Print geometry
print(buildings[291].construction_year) # Access in a simple way too
```

---

## 2. Iterating Through All Buildings
If you want to process every building in the dataset:

```python
for building_id, building_data in buildings.items():
    print(f"Building ID: {building_id}, Construction Year: {building_data.construction_year}")
```

---

## 3. Extracting Energy Asset Data
To retrieve energy assets for a specific building:

```python
energy_assets = buildings[291].building_energy_assets
for asset_name, asset_data in energy_assets.items():
    print(f"Asset: {asset_name}, Input1 Data(availability_profile): {asset_data.input1}")

#ORR FOR ALL BUILDINGS AND ASSETS
for building_id, building_data in buildings.items():
    print(f"Building ID: {building_id}, Construction Year: {building_data.construction_year}")

    for asset_name, asset_data in building_data.building_energy_assets.items():
        print(f"Asset: {asset_name}, Input1 Data(availability_profile): {asset_data.input1}")
```

---

## 4. Analyzing Consumption Data
For example, checking electricity consumption:

```python
elec_consumption = buildings[291].building_consumption.elec_consumption
print(f"Electricity consumption (first 10 hours): {elec_consumption[:10]}")
```

---

## 5. Filtering Buildings by Construction Year
Find buildings that were constructed before the year 2000:

```python
old_buildings = {bid: bdata for bid, bdata in buildings.items() if bdata.construction_year < 2000}
print(f"Buildings before 2000: {list(old_buildings.keys())}")
```

---

## 6. Identifying Missing Generation Systems
Find buildings missing a cooling system:

```python
missing_cooling_systems = [bid for bid, bdata in buildings.items() if bdata.generation_system_for_cooling is None]
print(f"Buildings missing cooling systems: {missing_cooling_systems}")
```

---

## 7. Getting Geometry Information
To retrieve the geometry data for mapping or spatial analysis:

```python
geometry_data = buildings[291].geometry
print(f"Building 291 Geometry: {geometry_data}")
```

---

## Summary
- The `buildings` dictionary allows easy retrieval and analysis of building data.
- Iterate, filter, and analyze energy consumption, assets, and construction details.
- Use Python loops and conditionals to extract meaningful insights.

---

### 🚀 Happy Coding!
