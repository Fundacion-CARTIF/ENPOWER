# -*- coding: utf-8 -*-
"""
Created on Thu Dec 12 13:32:38 2024

"""

def transform_structure_nodes(community_energy_assets):
    """
    Transforms the input structure to the desired 'node' output format, excluding specific fields 
    and adhering to the desired structure.

    Parameters:
    -----------
    assets : list
        List of 'community_energy_asset' dictionaries containing node information.

    Returns:
    --------
    dict
        Transformed JSON with nodes structured around 'community_energy_asset_input' and 
        'community_energy_asset_output', excluding unwanted fields.
    """
    nodes = {}

    for asset in community_energy_assets:
        # Procesar el nodo de entrada si existe un id_temp
        if "input_node" in asset and "id_temp" in asset["input_node"]:
            id_temp = asset["input_node"]["id_temp"]
            if id_temp not in nodes:
                nodes[id_temp] = {
                    "id": None,
                    "geom": asset["input_node"].get("geom"),
                    "name": asset["input_node"].get("name"),
                    "context_id": asset["input_node"].get("context_id"),
                    "community_energy_asset_input": [],
                    "community_energy_asset_output": [],
                }
            # Añadir el asset al nodo correspondiente
            nodes[id_temp]["community_energy_asset_input"].append(
                {k: v for k, v in asset.items() if k not in ["input_node_id", "output_node_id", "input_node", "output_node"]}
            )

        # Procesar el nodo de salida si existe un id_temp
        if "output_node" in asset and "id_temp" in asset["output_node"]:
            id_temp = asset["output_node"]["id_temp"]
            if id_temp not in nodes:
                nodes[id_temp] = {
                    "id": None,
                    "geom": asset["output_node"].get("geom"),
                    "name": asset["output_node"].get("name"),
                    "context_id": asset["output_node"].get("context_id"),
                    "community_energy_asset_input": [],
                    "community_energy_asset_output": [],
                }
            # Añadir el asset al nodo correspondiente
            nodes[id_temp]["community_energy_asset_output"].append(
                {k: v for k, v in asset.items() if k not in ["input_node_id", "output_node_id", "input_node", "output_node"]}
            )

    # Convertir el diccionario de nodos a una lista
    node_list = list(nodes.values())

    # Crear la salida final
    output_json = {
        "node": node_list
    }

    return output_json



def transform_whole_structure(community_context):
    """
    Transforms the entire structure to include nodes.

    Parameters:
    -----------
    community_context : dict
        Dictionary containing the context of the community including assets.

    Returns:
    --------
    dict
        Updated community context with transformed node structure.
    """
    community_context_updated = {
        "author": community_context.get("author", ""),
        "description": community_context.get("description", ""),
        "name": community_context.get("name", ""),
        "creation_date": community_context.get("creation_date", ""),
        "context_parent": community_context.get("context_parent", None),
        "building_asset_context": community_context.get("building_asset_context", []),
        "timestep_count": community_context.get("timestep_count", 8760),
        "timestep_duration": community_context.get("timestep_duration", 3600000)
    }

    # Transform the community_energy_asset into nodes
    # Transform the community_energy_asset into nodes
    try:
        assets = community_context.get("community_energy_asset", [])
        new_structure = transform_structure_nodes(assets)
        community_context_updated["node"] = new_structure.get("node", [])
    except KeyError:
        # Handle cases where expected keys are missing
        community_context_updated["node"] = []
    except Exception as e:
        # Handle unexpected errors
        print(f"An error occurred while transforming the structure: {e}")
        community_context_updated["node"] = []

    return community_context_updated


def reverse_transform_structure_nodes(nodes):
    """
    Reverts the transformed node structure back to the original asset-based format.

    Parameters:
    -----------
    nodes : list
        List of node dictionaries containing community_energy_asset_input and 
        community_energy_asset_output information.

    Returns:
    --------
    dict
        Reconstructed JSON with assets structured as in the original format.
    """
    assets = []

    for node in nodes:
        input_assets = node.get("community_energy_asset_input", [])
        for asset in input_assets:
            id_temp = asset.get("id_temp")
            reversed_asset = {**asset}  # Copy the original asset

            # Set input node details
            reversed_asset.update({
                "input_node_id": node.get("id"),
                "input_node": {
                    "id": node.get("id"),
                    "context_id": node.get("context_id"),
                    "geom": node.get("geom"),
                    "name": node.get("name"),
                    "id_temp": id_temp
                },
                "output_node_id": node.get("id"),
                "output_node": {
                    "id": node.get("id"),
                    "context_id": node.get("context_id"),
                    "geom": node.get("geom"),
                    "name": node.get("name"),
                    "id_temp": id_temp
                }
            })


            assets.append(reversed_asset)

    return {"community_energy_asset": assets}

def reverse_whole_structure(community_context):
    """
    Transforms the entire structure to have community_energy_assets as a list, instead of nodes

    Parameters:
    -----------
    community_context : dict
        Dictionary containing the context of the community including assets.

    Returns:
    --------
    dict
        Updated community context with transformed structure.
    """
    try:
        assets = reverse_transform_structure_nodes(community_context["node"])
        if assets is None:
            assets = []
    except KeyError:
        assets = []  # Handle the case where 'node' key is missing
    except Exception as e:
        # Handle other exceptions if necessary
        print(f"An error occurred: {e}")

    community_context_updated = {
        "author": community_context.get("author", ""),
        "description": community_context.get("description", ""),
        "name": community_context.get("name", ""),
        "creation_date": community_context.get("creation_date", ""),
        "context_parent": community_context.get("context_parent", None),
        "building_asset_context": community_context.get("building_asset_context", []),
        "timestep_count": community_context.get("timestep_count", 8760),
        "timestep_duration": community_context.get("timestep_duration", 3600000),
        "community_energy_asset": assets["community_energy_asset"]
    }

    return community_context_updated


