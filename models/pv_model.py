import pvlib
from classes_database_viejas import PVGISAPI
from oemof.solph import components, flows, Investment
from oemof.tools import economics

class PVSystem:
    def __init__(self, config_path,**kwargs):
        """
        Initializes a photovoltaic (PV) system based on location and other parameters.

        Parameters:
            config_path (str): Path to the configuration file.
            timezone (str): Timezone for the location.
            lat (float): Latitude of the PV system.
            lon (float): Longitude of the PV system.
            altitude (float): Altitude of the PV system.
            optimal_tilt (float): Optimal tilt angle of the panels.
            optimal_azimuth (float): Optimal azimuth angle of the panels.
            date_time_index (pd.DatetimeIndex): Time series for solar position calculations.
            kwargs (dict): Additional optional parameters like capex, opex, pmaxmax, and pminmax.
        """
        # Load configuration if available
        self.PV_Parameters = PVGISAPI.load_config(config_path) if config_path else {}
        # Optional Parameters
        self.pv_maxmax = kwargs.get("pmaxmax", 1)  # Default to 1 if not provided
        self.pv_pminmax = kwargs.get("pminmax", 0)
        self.capex = kwargs.get("capex", 1000)
        self.opex = kwargs.get("opex", 0.01*self.capex)
        self.lifetime =kwargs.get("lifetime",20)
        self.pv_profile=kwargs.get("pv_profile", [0]*8760)
        self.name=kwargs.get("name","pv")

        #Other optionals parameters, when pv_profile is not available
        self.lat = kwargs.get("lat",None)
        self.lon = kwargs.get("long",None)
        self.altitude = kwargs.get("altitude",None)
        self.optimal_tilt = kwargs.get("optimal_tilt",None)
        self.optimal_azimuth = kwargs.get("optimal_azimuth",None)
        self.date_time_index = kwargs.get("date_time_index",None)
        self.timezone = kwargs.get("timezone",None)  # Example: 'Europe/Madrid'
        self.location=kwargs.get("location",None)
        self.solar_position=kwargs.get("solar_position",None)
        self.clearsky=kwargs.get("clearsky",None)
        self.dni_extra=kwargs.get("dni_extra",None)
        self.total_irradiance=kwargs.get("total_irradiance",None)
        self.solar_radiation=kwargs.get("solar_radiation",None)
        self.normalized_solar_radiation=kwargs.get("normalized_solar_radiation",None)


    def calculate_pv_parameters(self):
        # Define location and retrieve solar data
        self.location = pvlib.location.Location(self.lat, self.lon, self.timezone, self.altitude)
        self.solar_position = self.location.get_solarposition(self.date_time_index)
        self.clearsky = self.location.get_clearsky(self.date_time_index)
        self.dni_extra = pvlib.irradiance.get_extra_radiation(self.date_time_index)

        # Calculate solar radiation and normalized values
        self.total_irradiance = self.calculate_total_irradiance()
        self.solar_radiation = self.total_irradiance['poa_global']
        self.normalized_solar_radiation = self.solar_radiation / 1000  # Convert W/m² to kW/m²

    def calculate_total_irradiance(self):
        """Calculates total irradiance on the panel surface using PVLIB."""
        return pvlib.irradiance.get_total_irradiance(
            self.optimal_tilt,
            self.optimal_azimuth,
            self.solar_position['apparent_zenith'],
            self.solar_position['azimuth'],
            self.clearsky['dni'],
            self.clearsky['ghi'],
            self.clearsky['dhi'],
            dni_extra=self.dni_extra,
            model='haydavies'
        )

    def add_to_energy_system(self, energysystem, group_id, cluster_id, output_bus):
        # %% PV Sources for both buildings
        epc = economics.annuity(self.capex, self.lifetime, 0.05)  # Calculate equivalent annual cost
        energysystem.add(
            components.Source(
                label=self.name if self.name is not None else f"gsp_id: {group_id}; cluster_id: {cluster_id}; PV Generation",
                outputs={output_bus: flows.Flow(
                    fix= self.pv_profile if self.pv_profile is not None else self.normalized_solar_radiation,
                    nominal_value=Investment(ep_costs=epc, maximum=self.pv_maxmax),
                    variable_costs=self.PV_Parameters["variable_cost"]
                )}
            )
        )

