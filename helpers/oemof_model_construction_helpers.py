from oemof.tools import logger
from oemof.solph import Model
import logging
from helpers import save_optimized_results_to_dataframe, generate_sankey_from_dataframe
import pandas as pd

def initialize_system():
    logger.define_logging(logfile="oemof_thermal_example.log", screen_level=logging.INFO, file_level=logging.INFO)
    logging.info("Initialize the energy system")

def optimize_and_plot_results(energysystem):
    logging.info("Optimise the energy system")
    energysystem_model = Model(energysystem)
    energysystem_model.solve(solver="cbc")
    energysystem.results = energysystem_model.results()

    results_df = save_optimized_results_to_dataframe(energysystem, energysystem.results)
    results_df[['source', 'target']] = pd.DataFrame(results_df['source'].tolist(), index=results_df.index)
    results_year = results_df.groupby(['source', 'target'])['flow'].sum().reset_index()

    generate_sankey_from_dataframe(results_year)

