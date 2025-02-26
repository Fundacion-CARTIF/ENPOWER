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



