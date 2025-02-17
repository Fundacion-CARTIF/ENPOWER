import math
import numpy as np
import pandas as pd
import geopandas as gpd
from shapely import wkt

## CODE FROM CITY ENERGY ANALYST

__author__ = "Jimeno A. Fonseca"
__copyright__ = "Copyright 2015, Architecture and Building Systems - ETH Zurich"
__credits__ = ["Jimeno A. Fonseca"]
__license__ = "MIT"
__version__ = "0.1"
__maintainer__ = "Daren Thomas"
__email__ = "cea@arch.ethz.ch"
__status__ = "Production"


def calc_geothermal_potential(Tm2, building_geom):
    "A very simplified calculation based on the area available"
    # dataprocessing
    area_below_buildings = wkt.building_geom
    # Buffer outward by 1 meter
    outward_buffer = building_geom.buffer(1)
    # local variables
    depth_m = 150 #meters
    extra_area = outward_buffer.area - building_geom
    T_ambient_C = Tm2

    # total area available
    area_geothermal = extra_area + area_below_buildings

    T_ground_K = calc_ground_temperature(T_ambient_C, depth_m)

    # convert back to degrees C
    t_source_final = [x[0] - 273 for x in T_ground_K]

    GHP_A = 25  # [m^2] area occupancy of one borehole Gultekin et al. 5 m separation at a penalty of 10% less efficeincy

    GHP_HMAX_SIZE = 2E3  # max heating design size [Wth] FOR ONE PROBE
    Q_max_kwh = np.ceil(area_geothermal / GHP_A) * GHP_HMAX_SIZE / 1000  # [kW th]

    # export
    return {"Ts_C": t_source_final, "QGHP_kW": Q_max_kwh, "Area_avail_m2": area_geothermal}



def calc_ground_temperature(T_ambient_C, depth_m):
    """
    Calculates hourly ground temperature fluctuation over a year following [Kusuda, T. et al., 1965]_.

    :param T_ambient_C: vector with outdoor temperature
    :type T_ambient_C: np array
    :param depth_m: depth


    :return T_ground_K: vector with ground temperatures in [K]
    :rtype T_ground_K: np array

    ..[Kusuda, T. et al., 1965] Kusuda, T. and P.R. Achenbach (1965). Earth Temperatures and Thermal Diffusivity at
    Selected Stations in the United States. ASHRAE Transactions. 71(1):61-74
    """
    # ground temperature values from City Energy Analyst
    SOIL_Cp_JkgK = 2000  # _[A. Kecebas et al., 2011]
    SOIL_lambda_WmK = 1.6
    SOIL_rho_kgm3 = 1600
    heat_capacity_soil = SOIL_Cp_JkgK
    conductivity_soil = SOIL_lambda_WmK
    density_soil = SOIL_rho_kgm3

    T_amplitude = abs((max(T_ambient_C) - min(T_ambient_C)) + 273.15)  # to K
    T_avg = np.mean(T_ambient_C) + 273.15  # to K
    T_ground_K = calc_temperature_underground(T_amplitude, T_avg, conductivity_soil, density_soil, depth_m,
                                              heat_capacity_soil)

    return T_ground_K

HOURS_IN_YEAR=8760
def calc_temperature_underground(T_amplitude_K, T_avg, conductivity_soil, density_soil, depth_m, heat_capacity_soil):
    diffusivity = conductivity_soil / (density_soil * heat_capacity_soil)  # in m2/s
    wave_lenght = (math.pi * 2 / HOURS_IN_YEAR)
    hour_with_minimum = 1
    e = math.sqrt(wave_lenght / (2 * diffusivity)) * depth_m  # soil constants
    T_ground_K = [T_avg + T_amplitude_K * (math.exp(-e) * math.cos(wave_lenght * (i - hour_with_minimum) - e))
                  for i in range(1, HOURS_IN_YEAR + 1)]

    return T_ground_K
