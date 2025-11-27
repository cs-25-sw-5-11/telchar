from classes import Edge, Network, Vertex, Trip, PointProjection
from configs.config import LAT_BIN_SIZE, LON_BIN_SIZE, LAT_MIN, LON_MIN
from src.classes import network
from tests.utils_functions import build_graph_with_mock_data, setup_network_and_trip
from utils.functions_misc import haversine
import pytest
import numpy as np
import os

def test_trip_is_initialized_correctly():
    # Arrange
    network = Network()
    trip = Trip(network=network, trip_id=1,
                lats=[],
                lons=[],
                times=[])

    # Act & Assert
    assert trip.network == network
    assert trip.trip_id == 1
    assert trip.get_max_trip_id() == 0

def test_added_point_projection_can_be_accessed():
    network, trip = setup_network_and_trip()
    edge = network.get_edge_by_id(1)

    pp1 = PointProjection(trip=trip, parent_edge=edge, lat=45.0, lon=126.0, seg_idx=0, seg_t=0.25)
    pp2 = PointProjection(trip=trip, parent_edge=edge, lat=46.0, lon=127.0, seg_idx=0, seg_t=0.75) 

    assert trip.get_point_projection_by_id(pp1.id) == pp1
    assert trip.get_point_projection_by_id(pp2.id) == pp2
    assert trip.get_max_trip_id() == 2

def test_layer_is_as_expected_when_projecting_trip_onto_network():
    # The trip in the setup function has no points, so a new one is made here.
    network, _ = setup_network_and_trip()
    # Single point slightly offset from vertex 1002.
    trip = Trip(network=network, trip_id=1,
                lats=[45.7024],
                lons=[126.5506],
                times=[0])
    
    trip._project_trip_onto_network(max_dist=100)
    trip_projection_layer = list(trip._projection_layers[0])
    trip_projection_layer_vertices = [item for item in trip_projection_layer if isinstance(item, Vertex)]
    trip_projection_layer_pps = [item for item in trip_projection_layer if isinstance(item, PointProjection)]

    # Expected projections along edge from 1001 to 1002 and 2002 to 1002,
    # and the vertex 1002 being added, since it should be the closest point
    # along the edge from 1002 to 1003. All of these should be in a single
    # projection layer.
    assert len(trip._projection_layers) == 1
    assert len(trip._projection_layers[0]) == 3
    assert trip.get_max_trip_id() == 2
    assert len(trip_projection_layer_vertices) == 1
    assert trip_projection_layer_vertices == [network.get_vertex_by_id(1002)]
    # Check that there are two point_projections that are along different edges,
    # and that one edge is along edge 0 and the other along edge 6.
    assert len(trip_projection_layer_pps) == 2
    assert trip_projection_layer_pps[0].parent_edge != trip_projection_layer_pps[1].parent_edge
    assert trip_projection_layer_pps[0].parent_edge in [network.get_edge_by_id(0), network.get_edge_by_id(6)]
    assert trip_projection_layer_pps[1].parent_edge in [network.get_edge_by_id(0), network.get_edge_by_id(6)]

def test_empty_layer_if_no_nearby_edges_when_using_project_trip_onto_network():
    # The trip in the setup function has no points, so a new one is made here.
    network, _ = setup_network_and_trip()
    # Furthest possible permitted point within the config max and min.
    trip = Trip(network=network, trip_id=1,
                lats=[45.8310],
                lons=[126.780],
                times=[0])
    
    trip._project_trip_onto_network(max_dist=100)

    assert len(trip._projection_layers) == 1
    assert len(trip._projection_layers[0]) == 0

def test_no_duplicates_are_created_for_identical_trip_points_when_using_project_trip_onto_network():
    # The trip in the setup function has no points, so a new one is made here.
    network, _ = setup_network_and_trip()
    # Single point slightly offset from vertex 1002, and a duplicate.
    trip = Trip(network=network, trip_id=1,
                lats=[45.7024, 45.7024],
                lons=[126.5506, 126.5506],
                times=[0, 30])
    
    trip._project_trip_onto_network(max_dist=100)


    # Expectation: layers are identical, only 2 point projections are created,
    # with each layer containing that plus a vertex.
    assert len(trip._projection_layers) == 2
    assert len(trip._projection_layers[0]) == 3
    assert len(trip._projection_layers[1]) == 3
    assert trip.get_max_trip_id() == 2
    assert trip._projection_layers[0] == trip._projection_layers[1]

def test_compute_layer_distances_gives_expected_results_for_duplicate_trip_points():
    # The trip in the setup function has no points, so a new one is made here.
    network, _ = setup_network_and_trip()
    # Single point slightly offset from vertex 1002, and a duplicate.
    trip = Trip(network=network, trip_id=1,
                lats=[45.7024, 45.7024],
                lons=[126.5506, 126.5506],
                times=[0, 30])
    
    result_dict = trip.compute_layer_distances(max_dist=100)
    point_projection_1 = trip.get_point_projection_by_id(1)
    point_projection_2 = trip.get_point_projection_by_id(2)
    if point_projection_1.parent_edge == network.get_edge_by_id(0):
        point_projection_along_edge_0 = point_projection_1
        point_projection_along_edge_6 = point_projection_2
    else:
        point_projection_along_edge_0 = point_projection_2
        point_projection_along_edge_6 = point_projection_1
    vertex_in_layer = network.get_vertex_by_id(1002)
    expected_dist_from_edge_0_pp_to_vertex = haversine(
        lat1=45.7024, lon1=126.5505,
        lat2=vertex_in_layer.lat, lon2=vertex_in_layer.lon
    )
    expected_dist_from_edge_6_pp_to_vertex = haversine(
        point_projection_along_edge_6.lat, point_projection_along_edge_6.lon,
        lat2=vertex_in_layer.lat, lon2=vertex_in_layer.lon
    )
    expected_dist_from_edge_vertex_to_edge_6_pp = sum([network.get_edge_by_id(1).length,
                                                       network.get_edge_by_id(2).length,
                                                       network.get_edge_by_id(3).length,
                                                       network.get_edge_by_id(7).length,
                                                       network.get_edge_by_id(4).length,
                                                       network.get_edge_by_id(6).length,
                                                       -expected_dist_from_edge_6_pp_to_vertex])
    expected_dist_from_edge_0_pp_to_edge_6_pp = sum([expected_dist_from_edge_0_pp_to_vertex, 
                                                     expected_dist_from_edge_vertex_to_edge_6_pp])


    assert result_dict[0][point_projection_along_edge_0.id][point_projection_along_edge_0.id] == 0.0
    assert result_dict[0][point_projection_along_edge_0.id][point_projection_along_edge_6.id] == pytest.approx(expected_dist_from_edge_0_pp_to_edge_6_pp, abs=0.1)
    assert result_dict[0][point_projection_along_edge_0.id][vertex_in_layer.id] == pytest.approx(expected_dist_from_edge_0_pp_to_vertex, abs=0.1)
    assert result_dict[0][point_projection_along_edge_6.id][point_projection_along_edge_6.id] == 0.0
    assert result_dict[0][point_projection_along_edge_6.id][point_projection_along_edge_0.id] >= np.iinfo(np.int32).max
    assert result_dict[0][point_projection_along_edge_6.id][vertex_in_layer.id] == pytest.approx(expected_dist_from_edge_6_pp_to_vertex, abs=0.1)
    assert result_dict[0][vertex_in_layer.id][vertex_in_layer.id] == 0.0
    assert result_dict[0][vertex_in_layer.id][point_projection_along_edge_0.id] >= np.iinfo(np.int32).max
    assert result_dict[0][vertex_in_layer.id][point_projection_along_edge_6.id] == pytest.approx(expected_dist_from_edge_vertex_to_edge_6_pp, abs=0.1)

def test_apply_speed_to_edges_updates_edge_speeds_correctly():
    network, trip = setup_network_and_trip()
    edge_0 = network.get_edge_by_id(0)
    edge_1 = network.get_edge_by_id(1)

    trip.apply_speed_to_edges(edges=[edge_0, edge_1],
                              time_index=0,
                              speed=20)
    trip.apply_speed_to_edges(edges=[edge_0],
                              time_index=0,
                              speed=40)
    for i in range(1, 10):
        trip.apply_speed_to_edges(edges=[edge_0],
                                  time_index=1,
                                  speed=i*10)

    # m/s converted to cm/s and rounded 
    assert edge_0.traversals_data[0][0] == (3000)
    assert edge_0.traversals_data[0][2] == (2)
    assert edge_1.traversals_data[0][0] == (2000)
    assert edge_1.traversals_data[0][2] == (1)
    assert edge_0.traversals_data[1][0] == (5000)
    assert edge_0.traversals_data[1][2] == (9)
    with pytest.raises(KeyError) as e:
        edge_1.traversals_data[1]

def test_find_shortest_edge_path_match_expected_values_going_to_vertex():
    network, trip = setup_network_and_trip()
    network.compute_all_pairs_shortest_paths()
    edge_0 = network.get_edge_by_id(0)
    vertex_2002 = network.get_vertex_by_id(2002)

    pp_0 = PointProjection(trip=trip, parent_edge=edge_0,
                           lat=45.0, lon=126.0, seg_idx=0, seg_t=0.5)
    expected_distance = edge_0.length * (1 - 0.5) + network.get_distance(edge_0.end, vertex_2002)
    expected_paths = [edge_0,
                      network.get_edge_by_id(1),
                      network.get_edge_by_id(2),
                      network.get_edge_by_id(3),
                      network.get_edge_by_id(7),
                      network.get_edge_by_id(4)]

    print(network.get_all_edges())

    computed_distance, edge_path = trip.find_shortest_edge_path(pp_0.id, vertex_2002.id)


    assert computed_distance == pytest.approx(expected_distance, abs=0.1)
    assert edge_path == expected_paths

def test_find_shortest_edge_path_match_expected_values_going_to_point_projection():
    network, trip = setup_network_and_trip()
    network.compute_all_pairs_shortest_paths()
    edge_0 = network.get_edge_by_id(0)
    edge_6 = network.get_edge_by_id(6)

    # Lat, lon doesn't matter here, as seg_idx and seg_t determine position along edge.
    pp_0 = PointProjection(trip=trip, parent_edge=edge_0,
                           lat=-1, lon=-1, seg_idx=0, seg_t=0.5)
    pp_1 = PointProjection(trip=trip, parent_edge=edge_6,
                           lat=-1, lon=-1, seg_idx=0, seg_t=0.5)
    expected_distance = edge_0.length * 0.5 + network.get_distance(edge_0.end, edge_6.start) + edge_6.length * 0.5
    expected_paths = [edge_0,
                      network.get_edge_by_id(1),
                      network.get_edge_by_id(2),
                      network.get_edge_by_id(3),
                      network.get_edge_by_id(7),
                      network.get_edge_by_id(4),
                      edge_6]

    computed_distance, edge_path = trip.find_shortest_edge_path(pp_0.id, pp_1.id)


    assert computed_distance == pytest.approx(expected_distance, abs=0.1)
    assert edge_path == expected_paths

def test_find_shortest_path_takes_shortest_path_even_when_projections_share_an_edge():
    # Set up a scenario where two point projections are on the same edge,
    # but the shortest path between them goes the other way around the network.
    network = Network()
    vertex_1 = Vertex(network=network, lat=45.6570, lon=126.500, node_id=1001)
    non_vertex_node_1 = (45.8310, 126.500, 1002)
    non_vertex_node_1 = (45.8310, 126.510, 1002)
    vertex_2 = Vertex(network=network, lat=45.6570, lon=126.510, node_id=1004)
    edge_1 = Edge(network=network, start_vertex=vertex_1, end_vertex=vertex_2,
                  non_vertex_nodes=[non_vertex_node_1, non_vertex_node_1], oneway=False, edge_type='primary')
    edge_2 = Edge(network=network, start_vertex=vertex_2, end_vertex=vertex_1,
                  non_vertex_nodes=[], oneway=False, edge_type='primary')
    network.compute_all_pairs_shortest_paths()
    trip = Trip(network=network, trip_id=1, lats=[], lons=[], times=[])
    pp_0 = PointProjection(trip=trip, parent_edge=edge_1,
                           lat=-1, lon=-1, seg_idx=0, seg_t=0.05)
    pp_1 = PointProjection(trip=trip, parent_edge=edge_1,
                           lat=-1, lon=-1, seg_idx=2, seg_t=0.95)
    
    expected_distance = pp_0.backward_vertex_dist + edge_2.length + pp_1.onward_vertex_dist
    expected_paths = [edge_1,
                      edge_2,
                      edge_1]
    computed_distance, edge_path = trip.find_shortest_edge_path(pp_0.id, pp_1.id)

    assert computed_distance == pytest.approx(expected_distance, abs=0.1)
    assert edge_path == expected_paths

def test_find_shortest_edge_path_returns_0_when_input_arguments_are_identical():
    network, trip = setup_network_and_trip()
    network.compute_all_pairs_shortest_paths()
    edge_0 = network.get_edge_by_id(0)

    pp_0 = PointProjection(trip=trip, parent_edge=edge_0,
                           lat=45.0, lon=126.0, seg_idx=0, seg_t=0.5)

    computed_distance, edge_path = trip.find_shortest_edge_path(pp_0.id, pp_0.id)

    assert computed_distance == 0.0
    assert edge_path == []