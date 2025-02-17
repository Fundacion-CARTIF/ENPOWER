# import api.services.scripts.KPI_module as KPI_module
from kpi_module import KPI_module as KPI_module
# from api.services.scripts.RESbased_scenario_generator import res_based_generator_list_technologies, generate_geojson, fetch_geojson, baseline_pathway_simple, baseline_pathway_intermediate, demand_statistics, demand_thermagrid
from scenario_generator.RESbased_scenario_generator import res_based_generator_list_technologies
from scenario_generator.RESbased_scenario_generator import generate_geojson, fetch_geojson, baseline_pathway_simple, baseline_pathway_intermediate, demand_statistics, demand_thermagrid
from kpi_module.key_performance_indicators import recalculate_indicators, get_indicators_from_baseline, aggregate_demand_profiles, community_KPIs
# , generate_geojson
# from api.services.scripts.energy_consumption import generation_system_function
from kpi_module.energy_consumption import generation_system_function
from scenario_generator.get_new_context import resbased_generator_context_creation
# from data_packages.transform_structure import transform_whole_structure, reverse_whole_structure
# from data_packages.processing import  merge_building_assets, merge_community_assets

def get_new_context(goal, community_context,recommendations_dic):
    # front data: "goals": 2
    # backend data: community context from database
    # recommendations_dic --> selection of the user from the result of generate_resbased_generator_list_technologies(front_data)
    community_context_updated = reverse_whole_structure(community_context)
    # get new based on the recommendations
    new_context = resbased_generator_context_creation(goal, community_context_updated, recommendations_dic)
    #call ARTELYS
    ARTELYS_output={}
    #Transform ARTELYS Outputs
    merged_context_with_building_assets=merge_building_assets(new_context,ARTELYS_output)
    merged_context=merge_community_assets(merged_context_with_building_assets, ARTELYS_output)
    #with new structure calculate indicators
    citizen_KPIs_per_building, demand_profiles_context,areas_buildings=recalculate_indicators(merged_context)
    #calculate total aggregated demand
    total_demand = aggregate_demand_profiles(demand_profiles_context)
    #calculate total community indicators
    community_indicators = community_KPIs(citizen_KPIs_per_building, total_demand,areas_buildings)
    # reverse node structure
    new_context_updated = transform_whole_structure(merged_context)
    return new_context_updated,community_indicators

def calculate_indicators(community_context):
    #adapt structure
    community_context_updated=reverse_whole_structure(community_context)
    #with new structure calculate indicators
    citizen_KPIs_per_building, demand_profiles_context,areas_buildings=recalculate_indicators(community_context_updated)
    #calculate total aggregated demand
    total_demand = aggregate_demand_profiles(demand_profiles_context)
    #calculate total community indicators
    community_indicators = community_KPIs(citizen_KPIs_per_building, total_demand,areas_buildings)
    #devolver más adelante citizen_KPIs_per_building
    return community_indicators

def generate_resbased_generator_list_technologies(front_data):
    # front_data = {
    #     "goals": 2,
    #     "country": "ES"
    # }
    list_technologies = res_based_generator_list_technologies(inputs_users=front_data)
    return list_technologies

def generate_baseline_pathway_intermediate(data, front_data):
    geojson_object=generate_geojson(front_data=front_data)
    geojson_file = fetch_geojson(geojson_object=geojson_object)
    demand_profile=demand_thermagrid(data=data, front_data=front_data, geojson_file=geojson_file)
    #calculate energy consumption based on the technology
    building_consumption_dict = generation_system_function(data=data, front_data=front_data, demand_profile=demand_profile)
    #create baseline object
    baseline = baseline_pathway_intermediate(data=data, front_data=front_data, geojson_file=geojson_file, demand_profile=demand_profile, building_consumption_dict=building_consumption_dict )
    #calculate kpis per building
    citizen_KPIs_per_building,areas_buildings = get_indicators_from_baseline(front_data, data, building_consumption_dict, demand_profile)
    #calculate total aggregated demand
    total_demand = aggregate_demand_profiles(demand_profile)
    #calculate total community indicators
    community_indicators = community_KPIs(citizen_KPIs_per_building, total_demand, areas_buildings)
    #devolver más adelante citizen_KPIs_per_building,
    return baseline,  community_indicators

def generate_baseline_pathway_simple(data, front_data):
    #calculate electricity and heat demand
    demand_profile=demand_statistics(data=data, front_data=front_data)
    #calculate energy consumption based on the technology
    building_consumption_dict = generation_system_function(data=data, front_data=front_data, demand_profile=demand_profile)
    #create baseline object
    baseline=baseline_pathway_simple(data=data, front_data=front_data, demand_profile=demand_profile, building_consumption_dict=building_consumption_dict )
    #calculate kpis
    #kpis_community = inner_perform_kpis(data=data, front_data=front_data, building_consumption_dict=building_consumption_dict, demand_profile=demand_profile)
    #calculate kpis per building
    citizen_KPIs_per_building,areas_buildings = get_indicators_from_baseline(front_data, data, building_consumption_dict, demand_profile)
    #calculate total aggregated demand
    total_demand = aggregate_demand_profiles(demand_profile)
    #calculate total community indicators
    kpis_community = community_KPIs(citizen_KPIs_per_building, total_demand, areas_buildings)
    return baseline, kpis_community

def inner_perform_kpis(data, front_data, building_consumption_dict, demand_profile):
    #Calculate primary energy consumption
    total_primary_energy, total_primary_energy_MWh = KPI_module.total_primary_energy_function(data=data, front_data=front_data, building_consumption_dict=building_consumption_dict)
    #calculate peak heat demand
    KPI_peak_heat_demand = KPI_module.kpi_peak_heat_demand(demand_profile=demand_profile)
    #calculate peak cooling demand
    KPI_peak_elec_demand = KPI_module.kpi_peak_electricity_demand(demand_profile=demand_profile)
    #Extract dictionary of citizen_kpis_factors
    citizen_kpis_factors= KPI_module.kpi_ctz_factors()
    #KPI number of members of the community
    num_members = KPI_module.kpi_scenario_objective(front_data=front_data)
    #KPI Equivalent TV hours
    TV_h = KPI_module.tv_h(citizen_kpis_factors=citizen_kpis_factors, total_primary_energy=total_primary_energy)
    #KPI Equivalent streaming hours
    streaming_h = KPI_module.streaming_h(citizen_kpis_factors=citizen_kpis_factors, total_primary_energy=total_primary_energy)
    #KPI equivalent pizza items
    Pizza_h = KPI_module.pizza_h(citizen_kpis_factors=citizen_kpis_factors, total_primary_energy=total_primary_energy)
    #Equivalent battery usage estimation
    Battery_charges = KPI_module.battery_charges(citizen_kpis_factors=citizen_kpis_factors, total_primary_energy=total_primary_energy)
    #Equivalent electric car charging times
    ElCar_charges = KPI_module.el_car_charges(citizen_kpis_factors=citizen_kpis_factors, total_primary_energy=total_primary_energy)
    #Equivalent trees
    #Trees_number = KPI_module.trees_number(citizen_kpis_factors=citizen_kpis_factors, total_primary_energy=total_primary_energy)
    # Equivalent Streaming impact in emissions
    #streaming_emissionhours = KPI_module.streaming_emission_hours(citizen_kpis_factors=citizen_kpis_factors, total_primary_energy=total_primary_energy)
    #
    #ICV_km = KPI_module.icv_km(citizen_kpis_factors=citizen_kpis_factors, total_primary_energy=total_primary_energy)
    #Equivalent wine bottels produced
    Wine_bottles= KPI_module.wine_bottles(citizen_kpis_factors=citizen_kpis_factors, total_primary_energy=total_primary_energy)
    #All citizen KPIs outputs
    kpis_community = KPI_module.save_to_csv(
        demand_profile=demand_profile, 
        building_consumption_dict=building_consumption_dict,
        total_primary_energy_MWh=total_primary_energy_MWh,
        KPI_peak_heat_demand=KPI_peak_heat_demand,
        KPI_peak_elec_demand=KPI_peak_elec_demand,
        num_members=num_members,
        TV_h=TV_h,
        streaming_h=streaming_h,
        Pizza_h=Pizza_h,
        Battery_charges=Battery_charges,
        ElCar_charges=ElCar_charges,
        #Trees_number=Trees_number,
        #streaming_emissionhours=streaming_emissionhours,
        #ICV_km=ICV_km,
        Wine_bottles=Wine_bottles
    )
    return kpis_community

def test():
    context_object = r'D:\Documents\enpower\data\community_context_updated_2_granada.json'

    import json

    with open(context_object) as f:
        community_context = json.load(f)
    front_data = {
        "goals": 2,
        "country": "ES"
    }
    recommendations_dic = generate_resbased_generator_list_technologies(front_data)
    print('test')
    print()
    new_context=get_new_context(goal=front_data["goals"], community_context=community_context, recommendations_dic=recommendations_dic)

    community_indicators=calculate_indicators(community_context=context_object)