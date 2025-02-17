from matplotlib.sankey import Sankey  # Importar la clase Sankey para crear diagramas
import matplotlib.pyplot as plt
import plotly.graph_objects as go
import plotly.offline as pyo
import pandas as pd
import json
from classes_database import Building_data
import os
import random
from oemof.solph import components, views
import helpers.constants as cte
import geopandas as gpd
from shapely import wkt

#%% Helper function for normalization
def normalize_profile(profile):
    if not profile:
        return profile  # Retorna el perfil vacío si no hay datos
    max_value = max(profile)
    return [x / max_value if max_value != 0 else 0 for x in profile]

def initialise(bd):
    # Initialize data for buildings
    buildings = {}  # Dictionary to store buildings

    # Loop through building contexts
    for context in bd.get(cte.BUILDING_ASSET_CONTEXT, []):  
        try:
            id = context.get(cte.BUILDING_ID, None)
            if id is not None:  
                buildings[id] = Building_data(id=id)

                # Extract consumption profiles
                consumption_data = context.get(cte.BUILDING_CONSUMPTION, {})
                buildings[id].associate_building_data(building=context.get(cte.BUILDING, {}))
                buildings[id].associate_building_consumption(consumption_data)
                buildings[id].associate_generation_system_info(
                    generation_system_profile=context.get(cte.GENERATION_SYSTEM_PROFILE, {}))
                buildings[id].associate_building_demand()
                if context.get(cte.BUILDING_ENERGY_ASSET, []):
                    buildings[id].associate_building_energy_asset(
                        building_energy_assets_of_the_building=context.get(cte.BUILDING_ENERGY_ASSET, []))

        except KeyError as e:
            print(f"Missing key {e} in context: {context}")
        except IndexError as e:
            print(f"Index error in {cte.BUILDING_ENERGY_ASSET}: {context}")

    return buildings

def create_epw_dataframe(datetime_vector, epw_data):
    days_of_year, hours = extract_day_hour(datetime_vector)
    epw = pd.DataFrame({
        'datetime': datetime_vector,
        'day_of_year': days_of_year,
        'hour': hours,
        'T': epw_data['Dry Bulb Temperature'],
        'Ig': epw_data['Global Horizontal Radiation'],
        'Id': epw_data['Diffuse Horizontal Radiation']
    })
    epw.set_index('datetime', inplace=True)
    return epw
# def inner_instance_context(context_object):
#     file_path_bd = os.path.join(os.getcwd(), 'data', context_object)
#     try:
#         with open(file_path_bd, 'r') as file:
#             bd = json.load(file)
#     except IOError:
#         print("An error occurred while reading the file.")
#     except json.JSONDecodeError:
#         print("An error occurred while decoding the JSON file.")
#     return Context(context_data=bd)


def create_datetime_vector(year: int) -> pd.DatetimeIndex:
    start_date = f'{year}-01-01 00:00:00'
    end_date = f'{year}-12-31 23:00:00'
    datetime_vector = pd.date_range(start=start_date, end=end_date, freq='h')
    return datetime_vector

def extract_day_hour(datetime_vector: pd.DatetimeIndex):
    day_of_year = datetime_vector.dayofyear
    hour = datetime_vector.hour
    return day_of_year, hour

def save_optimized_results_to_dataframe(energy_system, results) -> pd.DataFrame:
    results_list = []

    for node in energy_system.nodes:
        if isinstance(node, (components.Source, components.Sink, components.Converter, components.GenericStorage)):
            node_results = views.node(results, node.label)
            for (source, target), flow in node_results['sequences'].items():
                results_list.append({
                    'source': source,
                    'target': target,
                    'datetime': flow.index,
                    'flow': flow.values
                })

    results_df = pd.DataFrame(results_list)
    results_df = results_df.explode(['datetime', 'flow'])

    return results_df


def random_color():
    r = lambda: random.randint(0, 255)
    return f'#{r():02X}{r():02X}{r():02X}'


def plot_figures_for(energy_system, results) -> None:
    for node in energy_system.nodes:
        if isinstance(node, (components.Source, components.Sink, components.Converter, components.GenericStorage)):
            node_results = views.node(results, node.label)
            for key in node_results['sequences']:
                figure, axes = plt.subplots(figsize=(10, 5))
                node_results['sequences'][key].plot(ax=axes, kind='line', drawstyle='steps-post', color=random_color())
                plt.title(f"{node.label} - {key}")
                plt.xlabel("Time")
                plt.ylabel("Flow")
                plt.legend(loc="upper center", prop={"size": 8}, bbox_to_anchor=(0.5, 1.25), ncol=2)
                figure.subplots_adjust(top=0.8)
                plt.show()


def generate_sankey_from_dataframe(df: pd.DataFrame, label_path, label_title) -> None:
    df['flow'] = pd.to_numeric(df['flow'])

    all_labels = list(pd.concat([df['source'], df['target']]).unique())
    label_indices = {label: i for i, label in enumerate(all_labels)}

    colors = [
        "rgba(31, 119, 180, 0.8)", "rgba(255, 127, 14, 0.8)", "rgba(44, 160, 44, 0.8)",
        "rgba(214, 39, 40, 0.8)", "rgba(148, 103, 189, 0.8)", "rgba(140, 86, 75, 0.8)",
        "rgba(227, 119, 194, 0.8)", "rgba(127, 127, 127, 0.8)", "rgba(188, 189, 34, 0.8)",
        "rgba(23, 190, 207, 0.8)", "rgba(31, 119, 180, 0.8)", "rgba(255, 127, 14, 0.8)",
        "rgba(214, 39, 40, 0.8)", "rgba(148, 103, 189, 0.8)", "rgba(140, 86, 75, 0.8)",
        "rgba(214, 39, 40, 0.8)", "rgba(148, 103, 189, 0.8)", "rgba(148, 103, 189, 0.8)",
        "rgba(227, 119, 194, 0.8)", "rgba(127, 127, 127, 0.8)", "rgba(188, 189, 34, 0.8)",
        "rgba(23, 190, 207, 0.8)"
    ]

    if len(colors) < len(all_labels):
        colors.extend(["rgba(127, 127, 127, 0.8)"] * (len(all_labels) - len(colors)))

    fig = go.Figure(data=[go.Sankey(
        node=dict(
            pad=15,
            thickness=20,
            line=dict(color="black", width=0.5),
            label=all_labels,
            color=colors[:len(all_labels)]
        ),
        link=dict(
            source=[label_indices[src] for src in df['source']],
            target=[label_indices[trg] for trg in df['target']],
            value=df['flow']
        )
    )])

    fig.update_layout(title_text=f"Sankey Diagram of Energy Flows for {label_title}", font_size=10)

    pyo.plot(fig, filename=f'data/sankey_diagram{label_path}.html', auto_open=True)
    fig.show()

# Function to calculate building areas
def calculate_building_areas(buildings, projected_crs="EPSG:3857"):
    """
    Calculate the area for each building's geometry.

    Args:
        buildings (dict): Dictionary of Building_data instances.
        projected_crs (str): CRS for accurate area calculation (default: EPSG:3857).

    Returns:
        dict: Dictionary with building IDs as keys and areas in m² as values.
    """
    areas = {}
    for building_id, building_data in buildings.items():
        if building_data.geometry:
            try:
                # Convert WKT to shapely geometry
                geom = wkt.loads(building_data.geometry)
                
                # Create GeoDataFrame for projection and area calculation
                gdf = gpd.GeoDataFrame({"geometry": [geom]}, crs="EPSG:4326")
                gdf_projected = gdf.to_crs(projected_crs)
                
                # Calculate the area
                building_area = gdf_projected.geometry.area.iloc[0]
                areas[building_id] = building_area
                print(f"Building {building_id}: Area = {building_area:.2f} m²")
            except Exception as e:
                print(f"Failed to calculate area for Building {building_id}: {e}")
    return areas