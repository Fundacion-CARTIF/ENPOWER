from oemof.thermal.solar_thermal_collector import flat_plate_precalc
from oemof.solph import components, flows
import math

class SolarThermalCollector:
    def __init__(self, lat, lon, optimal_tilt, optimal_azimuth, stc_parameters, epw):
        self.lat = lat
        self.lon = lon
        self.optimal_tilt = optimal_tilt
        self.optimal_azimuth = optimal_azimuth
        self.stc_parameters = stc_parameters
        self.epw = epw
        #STC te devuelve:
        #
        self.STC = self.calculate()

    def calculate(self):
        return flat_plate_precalc(
            self.lat,
            self.lon,
            self.optimal_tilt,
            self.optimal_azimuth,
            self.stc_parameters['eta_0'],
            self.stc_parameters['a_1'],
            self.stc_parameters['a_2'],
            self.stc_parameters['collector_inlet_temperature'],
            self.stc_parameters['temperature_mean'] - self.stc_parameters['collector_inlet_temperature'],
            self.epw['Ig'],
            self.epw['Id'],
            self.epw['T']
        )

    def add_to_energy_system(self, energysystem, group_id, cluster_id, output_bus):
        STC_heat = self.STC['collectors_heat'] * self.stc_parameters['area'] / 1000  # [kWh]
        STC_max = STC_heat.max()
        STC_norm = STC_heat / STC_max

        energysystem.add(
            components.Source(
                label=f"gsp_id: {group_id}; cluster_id: {cluster_id}; STC Generation",
                outputs={output_bus: flows.Flow(
                    fix=STC_norm, nominal_value=STC_max, variable_costs=self.stc_parameters['variable_costs'])}
            )
        )


def calculate_max_collector_area(total_roof_area, tilt_angle):
    """
    Calculate the maximum collector area that can be installed based on the roof area and tilt angle.
    """
    # Convert tilt angle from degrees to radians
    tilt_angle_rad = math.radians(tilt_angle)

    # Calculate the maximum possible surface of collector according to the tilt
    max_collector_area = total_roof_area / math.cos(tilt_angle_rad)

    return max_collector_area


