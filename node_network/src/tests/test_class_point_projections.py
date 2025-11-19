from classes import Edge, Network, Vertex, Trip, PointProjection
from configs.config import LAT_BIN_SIZE, LON_BIN_SIZE, LAT_MIN, LON_MIN
from tests.utils_functions import build_graph_with_mock_data, setup_network_and_trip
from utils.functions_misc import haversine
import pytest
import os
import numpy as np

def test_created_point_projection_is_correctly_initialized():
    # Arrange
    network = Network()
    vertex1 = Vertex(network, lat=(LAT_MIN + LAT_BIN_SIZE / 2), lon=(LON_MIN + LON_BIN_SIZE / 2), node_id=1)
    non_vertex_nodes = [
        (LAT_MIN + LAT_BIN_SIZE / 2, LON_MIN + LON_BIN_SIZE * 1.5, 2),
        (LAT_MIN + LAT_BIN_SIZE / 2, LON_MIN + LON_BIN_SIZE * 2.5, 3),
        (LAT_MIN + LAT_BIN_SIZE * 1.5, LON_MIN + LON_BIN_SIZE * 2.5, 4)
    ]
    vertex2 = Vertex(network, lat=(LAT_MIN + LAT_BIN_SIZE * 2.5), lon=(LON_MIN + LON_BIN_SIZE * 2.5), node_id=5)
    edge = Edge(network=network, start_vertex=vertex1, end_vertex=vertex2, 
                non_vertex_nodes=non_vertex_nodes, edge_type="primary", oneway=True)
    trip = Trip(network=network, trip_id=1,
                lats=[],
                lons=[],
                times=[])

    # Act
    point_projection = PointProjection(
        trip=trip,
        parent_edge=edge,
        lat=LAT_MIN + LAT_BIN_SIZE / 2,
        lon=LON_MIN + LON_BIN_SIZE * 2,
        seg_idx=1,
        seg_t=0.5,
    )
    expected_backward_dist = haversine(
        LAT_MIN + LAT_BIN_SIZE / 2,
        LON_MIN + LON_BIN_SIZE * 2,
        vertex1.lat,
        vertex1.lon
    )

    # Assert
    assert point_projection.id == 1
    assert point_projection == trip.get_point_projection_by_id(1)
    assert point_projection.parent_edge == edge
    assert point_projection.backward_vertex == vertex1
    assert point_projection.onward_vertex == vertex2
    assert abs(point_projection.backward_vertex_dist - expected_backward_dist) < 1e-6 

def test_get_distance_between_projections_sharing_edge_throws_error_if_edge_not_shared():
    network, trip = setup_network_and_trip()
    
    point_projection_1 = PointProjection(trip=trip,
                                         parent_edge=network.get_all_edges()[0],
                                         lat=0, lon=0, seg_idx=0, seg_t=0.0)
    point_projection_2 = PointProjection(trip=trip,
                                         parent_edge=network.get_all_edges()[1],
                                         lat=0, lon=0, seg_idx=0, seg_t=0.0)

    with pytest.raises(ValueError) as e:
        point_projection_1.get_distance_between_projections_sharing_edge(point_projection_2)
    assert "Projections do not share the same parent edge." in str(e.value)

def test_get_distance_between_projections_sharing_edge_calculates_correct_distance_with_forward_movement_along_oneway():
    network, trip = setup_network_and_trip()
    
    edge = network.get_all_edges()[0]
    point_projection_1 = PointProjection(trip=trip,
                                         parent_edge=edge,
                                         lat=0, lon=0, seg_idx=0, seg_t=0.25)
    point_projection_2 = PointProjection(trip=trip,
                                         parent_edge=edge,
                                         lat=0, lon=0, seg_idx=0, seg_t=0.75)

    expected_distance = edge.length * (0.75 - 0.25)

    calculated_distance = point_projection_1.get_distance_between_projections_sharing_edge(point_projection_2)

    assert abs(calculated_distance - expected_distance) < 1e-6

def test_get_distance_between_projections_sharing_edge_returns_none_with_backward_movement_along_oneway():
    network, trip = setup_network_and_trip()
    
    edge = network.get_all_edges()[0]
    point_projection_1 = PointProjection(trip=trip,
                                         parent_edge=edge,
                                         lat=0, lon=0, seg_idx=0, seg_t=0.75)
    point_projection_2 = PointProjection(trip=trip,
                                         parent_edge=edge,
                                         lat=0, lon=0, seg_idx=0, seg_t=0.25)

    calculated_distance = point_projection_1.get_distance_between_projections_sharing_edge(point_projection_2)

    assert calculated_distance is None

def test_get_distance_between_projections_sharing_edge_calculates_correct_distance_with_backward_movement_along_non_oneway():
    network, trip = setup_network_and_trip()
    
    edge = network.get_all_edges()[1]
    point_projection_1 = PointProjection(trip=trip,
                                         parent_edge=edge,
                                         lat=0, lon=0, seg_idx=0, seg_t=0.25)
    point_projection_2 = PointProjection(trip=trip,
                                         parent_edge=edge,
                                         lat=0, lon=0, seg_idx=0, seg_t=0.75)

    expected_distance = edge.length * (0.75 - 0.25)

    calculated_distance = point_projection_1.get_distance_between_projections_sharing_edge(point_projection_2)

    assert abs(calculated_distance - expected_distance) < 1e-6

def test_get_distance_to_vertex_returns_correct_distances_to_possible_target():
    network, trip = setup_network_and_trip()
    target_vertex = network.get_vertex_by_id(1003)
    
    edge = network.get_all_edges()[0]
    point_projection = PointProjection(trip=trip,
                                       parent_edge=edge,
                                       lat=0, lon=0, seg_idx=0, seg_t=0.5)

    expected_onward_distance = point_projection.onward_vertex_dist + \
                               network.get_edge_by_id(1).length

    distance_to_vertex = point_projection.get_distance_to_vertex(network, target_vertex)

    assert abs(distance_to_vertex - expected_onward_distance) < 0.01
    
def test_get_distance_to_vertex_returns_int32_max_to_impossible_target():
    network, trip = setup_network_and_trip()
    target_vertex = network.get_vertex_by_id(1001)
    
    edge = network.get_all_edges()[0]
    point_projection = PointProjection(trip=trip,
                                       parent_edge=edge,
                                       lat=0, lon=0, seg_idx=0, seg_t=0.5)

    distance_to_vertex = point_projection.get_distance_to_vertex(network, target_vertex)

    assert distance_to_vertex >= np.iinfo(np.int32).max

def test_get_distance_to_vertex_can_go_backward_along_non_oneway():
    network, trip = setup_network_and_trip()
    target_vertex = network.get_vertex_by_id(1003)
    
    edge = network.get_all_edges()[2]
    point_projection = PointProjection(trip=trip,
                                       parent_edge=edge,
                                       lat=0, lon=0, seg_idx=0, seg_t=0.5)

    distance_to_vertex = point_projection.get_distance_to_vertex(network, target_vertex)
    expected_distance = point_projection.backward_vertex_dist

    assert abs(distance_to_vertex - expected_distance) < 0.01

def test_get_distance_from_vertex_returns_correct_distance_from_possible_source():
    network, trip = setup_network_and_trip()
    source_vertex = network.get_vertex_by_id(1002)
    
    edge = network.get_all_edges()[2]
    point_projection = PointProjection(trip=trip,
                                       parent_edge=edge,
                                       lat=0, lon=0, seg_idx=0, seg_t=0.5)

    distance_from_vertex = point_projection.get_distance_from_vertex(network, source_vertex)
    expected_distance = network.get_edge_by_id(1).length + point_projection.backward_vertex_dist

    assert abs(distance_from_vertex - expected_distance) < 0.01

def test_get_distance_from_vertex_returns_int32_max_from_impossible_source():
    network, trip = setup_network_and_trip()
    source_vertex = network.get_vertex_by_id(2001)
    
    edge = network.get_all_edges()[2]
    point_projection = PointProjection(trip=trip,
                                       parent_edge=edge,
                                       lat=0, lon=0, seg_idx=0, seg_t=0.5)

    distance_from_vertex = point_projection.get_distance_from_vertex(network, source_vertex)

    assert distance_from_vertex >= np.iinfo(np.int32).max

def test_get_distance_between_projections_on_consecutive_edges():
    network, trip = setup_network_and_trip()
    edge_1 = network.get_edge_by_id(1)
    edge_2 = network.get_edge_by_id(2)
    # Edge 2 starts where Edge 1 ends, should be able to go from projection 1 to projection 2
    
    point_projection_1 = PointProjection(trip=trip,
                                         parent_edge=edge_1,
                                         lat=0, lon=0, seg_idx=0, seg_t=0.5)
    point_projection_2 = PointProjection(trip=trip,
                                         parent_edge=edge_2,
                                         lat=0, lon=0, seg_idx=0, seg_t=0.5)
    expected_distance = edge_1.length * 0.5 + edge_2.length * 0.5
    calculated_distance = point_projection_1.get_distance_between_projections(network, point_projection_2)

    assert abs(calculated_distance - expected_distance) < 0.01

def test_get_distance_between_projections_on_impossible_paths_returns_int32_max():
    network, trip = setup_network_and_trip()
    edge_1 = network.get_edge_by_id(1)
    edge_2 = network.get_edge_by_id(0)
    # Edge 1 leads into edge 2, but is oneway and no path exists to its start vertex 
    print(network.get_all_edges())

    for vertex in network.get_all_vertices():
        print(network.get_distance(vertex, network.get_vertex_by_id(1001)))
    print()
    
    point_projection_1 = PointProjection(trip=trip,
                                         parent_edge=edge_1,
                                         lat=0, lon=0, seg_idx=0, seg_t=0.5)
    point_projection_2 = PointProjection(trip=trip,
                                         parent_edge=edge_2,
                                         lat=0, lon=0, seg_idx=0, seg_t=0.5)

    calculated_distance = point_projection_1.get_distance_between_projections(network, point_projection_2)
    print(calculated_distance)

    assert calculated_distance >= np.iinfo(np.int32).max

def test_get_distance_between_projections_on_same_projection_in_forward_direction_returns_correct_distance():
    network, trip = setup_network_and_trip()
    edge_1 = network.get_edge_by_id(1)
    
    point_projection_1 = PointProjection(trip=trip,
                                         parent_edge=edge_1,
                                         lat=0, lon=0, seg_idx=0, seg_t=0.25)
    point_projection_2 = PointProjection(trip=trip,
                                         parent_edge=edge_1,
                                         lat=0, lon=0, seg_idx=0, seg_t=0.75)
    expected_distance = edge_1.length * 0.5
    calculated_distance = point_projection_1.get_distance_between_projections(network, point_projection_2)

    assert abs(calculated_distance - expected_distance) < 0.01

def test_get_distance_between_projections_on_same_projection_in_backward_direction_along_oneway_returns_correct_distance():
    network, trip = setup_network_and_trip()
    edge_1 = network.get_edge_by_id(1)

    print(network.get_all_edges())
    
    # Have one projection be further along an oneway edge, means that we have to circle back around.
    point_projection_1 = PointProjection(trip=trip,
                                         parent_edge=edge_1,
                                         lat=0, lon=0, seg_idx=0, seg_t=0.75)
    point_projection_2 = PointProjection(trip=trip,
                                         parent_edge=edge_1,
                                         lat=0, lon=0, seg_idx=0, seg_t=0.25)
    expected_distance = edge_1.length * (1 - 0.75) + \
                        network.get_edge_by_id(2).length + \
                        network.get_edge_by_id(3).length + \
                        network.get_edge_by_id(7).length + \
                        network.get_edge_by_id(4).length + \
                        network.get_edge_by_id(6).length + \
                        edge_1.length * 0.25
    calculated_distance = point_projection_1.get_distance_between_projections(network, point_projection_2)

    assert abs(calculated_distance - expected_distance) < 0.01