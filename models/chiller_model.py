from oemof.thermal.compression_heatpumps_and_chillers import calc_cops, calc_max_Q_dot_chill, calc_max_Q_dot_heat, calc_chiller_quality_grade
import pandas as pd
from oemof.solph import components, flows

class CompressionHeatPumpChiller:
    def __init__(self, chpc_parameters, epw):
        self.chpc_parameters = chpc_parameters
        self.epw = epw
        self.COP_HEAT, self.COP_COOL = self.calculate_cops()

    def calculate_cops(self):
        heating_season = self.get_heating_season()
        cooling_season = self.get_cooling_season()

        T_amb_HEAT = self.epw['T'].copy()
        T_low_HEAT = T_amb_HEAT - 10
        T_high_HEAT = pd.Series([self.chpc_parameters['SETPOINT_HEAT']] * len(T_amb_HEAT), index=T_amb_HEAT.index)

        T_low_HEAT[T_low_HEAT - T_high_HEAT >= 0] = 1
        T_high_HEAT[T_low_HEAT - T_high_HEAT >= 0] = 0

        COP_HEAT = calc_cops(
            temp_high=T_high_HEAT,
            temp_low=T_low_HEAT,
            quality_grade=self.chpc_parameters['QGRADE'],
            temp_threshold_icing=self.chpc_parameters['THR_ICING'],
            factor_icing=self.chpc_parameters['FACTOR_ICING'],
            mode='heat_pump'
        )

        COP_HEAT = COP_HEAT * heating_season

        T_amb_COOL = self.epw['T'].copy()
        T_high_COOL = T_amb_COOL + 10
        T_low_COOL = pd.Series([self.chpc_parameters['SETPOINT_COOL']] * len(T_amb_COOL), index=T_amb_COOL.index)

        T_high_COOL[T_high_COOL - T_low_COOL <= 0] = 1
        T_low_COOL[T_high_COOL - T_low_COOL <= 0] = 0

        COP_COOL = calc_cops(
            temp_high=T_high_COOL,
            temp_low=T_low_COOL,
            quality_grade=self.chpc_parameters['QGRADE'],
            temp_threshold_icing=self.chpc_parameters['THR_ICING'],
            factor_icing=None,
            mode='chiller'
        )

        COP_COOL = COP_COOL * cooling_season

        return COP_HEAT, COP_COOL

    def get_heating_season(self):
        heating_season = pd.Series(0, index=self.epw.index)
        heating_start = pd.to_datetime('2019-09-16')
        heating_end = pd.to_datetime('2019-05-14')
        heating_season[(heating_start <= self.epw.index) | (self.epw.index <= heating_end)] = 1
        return heating_season

    def get_cooling_season(self):
        cooling_season = pd.Series(0, index=self.epw.index)
        cooling_start = pd.to_datetime('2019-05-15')
        cooling_end = pd.to_datetime('2019-09-15')
        cooling_season[(cooling_start <= self.epw.index) & (self.epw.index <= cooling_end)] = 1
        return cooling_season

    def add_to_energy_system(self, energysystem, group_id, cluster_id, elec_bus, heat_bus, cool_bus):
        # Air-Source Compression Heat Pump
        energysystem.add(
            components.Converter(
                label=f"gsp_id: {group_id}; cluster_id: {cluster_id}; ASHP Generation [kWh]",
                inputs={elec_bus: flows.Flow()},
                outputs={heat_bus: flows.Flow(nominal_value=5, variable_costs=0)},  # Heating Capacity: 5 kW
                conversion_factors={heat_bus: self.COP_HEAT}
            )
        )

        # Air-Source Compression Chiller
        energysystem.add(
            components.Converter(
                label=f"gsp_id: {group_id}; cluster_id: {cluster_id}; ASC Generation [kWh]",
                inputs={elec_bus: flows.Flow()},
                outputs={cool_bus: flows.Flow(nominal_value=15, variable_costs=0)},  # Cooling Capacity: 15 kW
                conversion_factors={cool_bus: self.COP_COOL}
            )
        )