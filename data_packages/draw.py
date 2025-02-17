# -*- coding: utf-8 -*-
"""
Created on Mon Jul 19 13:43:49 2021

@author: andgab
"""

# import os
# from graphviz import Digraph
# import oemof.solph
# import logging

import os
from graphviz import Digraph
import oemof.solph

def draw_energy_system(energy_system=None, filepath="network", img_format="png", legend=False):
    """Draw the energy system with Graphviz."""
    
    file_name, file_ext = os.path.splitext(filepath)
    img_format = img_format or (file_ext.replace(".", "") if file_ext else "png")
    dot = Digraph(filename=file_name, format=img_format)
    
    if legend:
        dot.node("Bus", shape='rectangle', fontsize="10", label="Bus")
        dot.node("Converter", shape='ellipse', fontsize="10", label="Converter")
        dot.node("Source", shape='invtrapezium', fontsize="10", label="Source")
        dot.node("Sink", shape='trapezium', fontsize="10", label="Sink")

    # Add nodes for each component
    for key, component in energy_system.groups.items():
        if isinstance(component, set):
            continue  # Skip internal blocks (e.g., BusBlock, ConverterBlock)
        
        if isinstance(component, oemof.solph.Bus):
            # print(f"Adding Bus: {key}")
            dot.node(key, shape='rectangle', fontsize="10", label=f"Bus: {key}")
        
        elif isinstance(component, oemof.solph.components.Converter):
            # print(f"Adding Converter: {key}")
            dot.node(key, shape='ellipse', fontsize="10", label=f"Converter: {key}")
        
        elif isinstance(component, oemof.solph.components.Source):
            # print(f"Adding Source: {key}")
            dot.node(key, shape='invtrapezium', fontsize="10", label=f"Source: {key}")
        
        elif isinstance(component, oemof.solph.components.Sink):
            # print(f"Adding Sink: {key}")
            dot.node(key, shape='trapezium', fontsize="10", label=f"Sink: {key}")
        
        elif isinstance(component, oemof.solph.components.GenericStorage):
            # print(f"Adding Storage: {key}")
            dot.node(key, shape='box', fontsize="10", label=f"Storage: {key}")

    # Add edges for inputs and outputs of each bus
    for key, component in energy_system.groups.items():
        if isinstance(component, oemof.solph.Bus):
            for input_comp in getattr(component, "inputs", []):
                dot.edge(input_comp.label, key)  # Edge from input component to bus
            for output_comp in getattr(component, "outputs", []):
                dot.edge(key, output_comp.label)  # Edge from bus to output component

    # Render the graph to a .png file
    dot.render(filename=filepath, format=img_format, cleanup=True)
    # print(f"Graph saved as {filepath}.{img_format}")


# def draw_energy_system(energy_system=None, filepath="network", img_format=None, legend=False):
#     """Draw the energy system with Graphviz.
    
#     Parameters
#     ----------
#     energy_system: `oemof.solph.network.EnergySystem`
#         The oemof energy stystem
        
#     filepath: str
#         path, where the rendered result shall be saved, if an extension is provided, the format will be 
#         automatically adapted except if the `img_format` argument is provided
#         Default: "network"
        
#     img_format: str
#         extension of one of the available image formats of graphviz (e.g "png", "svg", "pdf" ...)
#         Default: "pdf"

#     legend: bool
#         specify, whether a legend will be added to the graph or not
#         Default: False

#     Returns
#     -------
#     None: render the generated dot graph in the filepath
#     """
    
#     file_name, file_ext = os.path.splitext(filepath)
    
#     if img_format is None:
#         if file_ext != "":
#             img_format = file_ext.replace(".", "")
#         else:
#             img_format = "pdf"
    
#     # Creates the Directed-Graph
#     dot = Digraph(filename=file_name, format=img_format)
    
#     if legend is True:
#         dot.node("Bus", shape='rectangle', fontsize="10")
#         dot.node("Sink", shape='trapezium', fontsize="10")
#         dot.node("Source", shape='invtrapezium', fontsize="10")
#         dot.node("Transformer", shape='rectangle', fontsize="10")
#         dot.node("Storage", shape='rectangle', style='dashed', fontsize="10", color="green")
    
#     busses = []
#     # draw a node for each of the network's component. The shape depends on the component's type
#     for nd in energy_system.nodes:
#         if isinstance(nd, oemof.solph.network.Bus):
#             dot.node(nd.label, shape='rectangle', fontsize="10", fixedsize='shape', width='2.1', height='0.6')
#             # keep the bus reference for drawing edges later
#             busses.append(nd)
#         if isinstance(nd, oemof.solph.network.Sink):
#             dot.node(nd.label, shape='trapezium', fontsize="10")
#         if isinstance(nd, oemof.solph.network.Source):
#             dot.node(nd.label, shape='invtrapezium', fontsize="10")
#         if isinstance(nd, oemof.solph.network.Transformer):
#             dot.node(nd.label, shape='rectangle', fontsize="10")
#         if isinstance(nd, oemof.solph.components.GenericStorage):
#             dot.node(nd.label, shape='rectangle', style='dashed', fontsize="10", color="green")

#     # draw the edges between the nodes based on each bus inputs/outputs        
#     for bus in busses:
#         for component in bus.inputs:
#             #draw an arrow from the component to the bus
#             dot.edge(component.label, bus.label)
#         for component in bus.outputs:
#             #draw an arrow from the bus to the component
#             dot.edge(bus.label, component.label)

#     dot.view()