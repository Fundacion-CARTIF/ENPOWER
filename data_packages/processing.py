def merge_building_assets(context, new_assets):
    """
    Parameters
    ----------
    context: community context from script get_new_context.py
    new_assets: results from optimisation for new assets

    Returns
    -------
    Updated context with replaced or merged building energy assets.
    """
    # Index building_asset_context by id for quick access
    context_dict = {c["id_temp"]: c for c in context.get("building_asset_context", [])}

    # Iterate through the new building energy assets
    for asset in new_assets.get("building_energy_asset", []):
        id_temp = asset.get("id_temp")
        if id_temp in context_dict:
            # Get the existing building_energy_asset list
            building_energy_assets = context_dict[id_temp].setdefault("building_energy_asset", [])

            # Check if the asset already exists
            existing_asset = next((a for a in building_energy_assets if a.get("id_temp") == asset.get("id_temp")), None)
            if existing_asset:
                # Replace the existing asset
                building_energy_assets[building_energy_assets.index(existing_asset)] = asset
            else:
                # Add the new asset if it doesn't already exist
                building_energy_assets.append(asset)

    return context


def merge_community_assets(context, new_assets):
    """
    Merges new assets into the existing community context. Existing assets will be updated, and new ones added.

    Parameters
    ----------
    context: dict
        Community context containing existing assets.
    new_assets: dict
        Results from the optimization for new community assets.

    Returns
    -------
    dict
        Updated community context with merged assets.
    """
    # Index community assets by id_temp for quick access
    context_assets = context.get('community_energy_asset', [])
    context_asset_dict = {asset['id_temp']: asset for asset in context_assets if 'id_temp' in asset}

    # Iterate through the new community energy assets
    for asset in new_assets.get('community_energy_asset', []):
        asset_id_temp = asset.get('id_temp')

        if asset_id_temp in context_asset_dict:
            # If asset exists in context, update its values
            context_asset_dict[asset_id_temp].update(asset)
        else:
            # If asset is new, add it to the context
            context_assets.append(asset)

    # Update the context with the merged assets
    context['community_energy_asset'] = context_assets
    return context


#
# # Example usage:
# data = {
#     "id": 1,
#     "name": "Baseline Ispaster",
#     "start_date": "2023-01-01",
#     "timestep_count": 8760,
#     "timestep_duration": 3600000,
#     "creation_date": "2024-11-03",
#     "context_parent": None,
#     "author": "andgab",
#     "description": "This is the baseline of Ispaster, without including building assets and community assets. The data now stored corresponds to the outputs of the City Energy Analyst model",
#     "node": [
#         {
#             "id": 1,
#             "geom": "POINT (-3 41)",
#             "name": "TEST",
#             "context_id": 1,
#             "community_energy_asset_output": [],
#             "community_energy_asset_input": []
#         }
#     ],
#     "building_asset_context": [
#         {
#             "id": 6,
#             "building_energy_asset": []
#         },
#         {
#             "id": 7,
#             "building_energy_asset": []
#         }
#     ]
# }
#
# new_building_assets = {
#     "building_energy_asset": [
#         {
#             "id_temp": 1,
#             "generation_system_id": 83,
#             "pmaxmin_scalar": 0,
#             "availability_ts_id": None,
#             "pmax_scalar": 2,
#             "pmaxmax_scalar": 62.3,
#             "building_asset_context_id": 6,
#             "availability_ts": {
#                 "temp_id": None,
#                 "name": "pv_building_6",
#                 "value_input1": [0.0, 0.05552, 0.18315]
#             }
#         }
#     ]
# }
#
# new_community_assets = {
#     "community_energy_asset": [
#         {
#             "id_temp": 1,
#             "generation_system_id": 79,
#             "pmaxmin_scalar": None,
#             "availability_ts_id": None,
#             "pmax_scalar": None,
#             "pmaxmax_scalar": None,
#             "input_node": {
#                 "id_temp": 1,
#                 "geom": "POINT (-2.5438995325737133 43.362092317437714)",
#                 "name": "GRID"
#             },
#             "output_node": None
#         },
#         {
#             "id_temp": 2,
#             "generation_system_id": 83,
#             "pmaxmin_scalar": 0,
#             "availability_ts_id": None,
#             "pmax_scalar": 60,
#             "pmaxmax_scalar": 100,
#             "input_node": {
#                 "id_temp": 1,
#                 "geom": "POINT (-2.5438995325737133 43.362092317437714)",
#                 "name": "pv_input"
#             },
#             "output_node": {
#                 "id_temp": 1,
#                 "geom": "POINT (-2.5438995325737133 43.362092317437714)",
#                 "name": "pv_output"
#             }
#         }
#     ]
# }
#
# import json
# input_file = r"D:\Documents\localres_local\scripts\data_packages\SC1_ispaster_pv_on_roofs_new.json"  # Replace with your input JSON file path
#
# with open(input_file, 'r') as file:
#     data = json.load(file)
#
# input_file_ARTELYS = r"D:\Documents\localres_local\scripts\data_packages\output.json"  # Replace with your input JSON file path
#
# with open(input_file_ARTELYS, 'r') as file:
#     new_info_ARTELYS = json.load(file)
# input_file_comm_asset = r"D:\Desktop\community_system.json"  # Replace with your input JSON file path
# with open(input_file_comm_asset, 'r') as file:
#     new_comm = json.load(file)
#
# # Merge the data and print the result
# merged_data = merge_building_assets(data, new_info_ARTELYS)
# # merged_data = merge_community_assets(merged_data, new_comm)
# print('test')
