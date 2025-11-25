from classes import Edge, Network, Vertex, Trip, PointProjection
from configs.config import LAT_BIN_SIZE, LON_BIN_SIZE, LAT_MIN, LON_MIN
from tests.utils_functions import build_graph_with_mock_data, setup_network_and_trip
from utils.functions_misc import haversine
import pytest
import numpy as np

def test_network_is_initialized_correctly():
    # Arrange
    network, trip = setup_network_and_trip()
    
    # Act

    # Assert
    assert isinstance(network, Network)
    assert len(network.get_all_vertices()) == 8
    assert len(network.get_all_edges()) == 8
    assert network.get_max_edge_id() == 7

def test_get_edges_near_coordinate_returns_correct_edges():
    network, trip = setup_network_and_trip()
    
    lat, lon = 45.702, 126.550
    nearby_edges = network.get_edges_near_coordinate(lat, lon)
    expected_edges = [network.get_edge_by_id(0),
                      network.get_edge_by_id(1), 
                      network.get_edge_by_id(2), 
                      network.get_edge_by_id(6)]
    
    assert list(nearby_edges) == expected_edges

def test_get_edges_near_coordinate_with_no_edges():
    network, trip = setup_network_and_trip()
    
    lat, lon = 45.6570, 126.500  # Coordinates far from any edges
    nearby_edges = network.get_edges_near_coordinate(lat, lon)
    
    assert list(nearby_edges) == []

def test_get_distance_throws_error_if_all_pairs_shortest_paths_not_computed():
    network = Network()
    vertex1 = Vertex(network, lat=45.0, lon=126.0, node_id=1)
    vertex2 = Vertex(network, lat=46.0, lon=126.0, node_id=2)

    with pytest.raises(RuntimeError):
        network.get_distance(vertex1, vertex2)

def test_get_distance_returns_correct_value():
    network, trip = setup_network_and_trip()
    vertex1 = network.get_vertex_by_id(1001)
    vertex2 = network.get_vertex_by_id(1002)
    vertex3 = network.get_vertex_by_id(1003)

    network.compute_all_pairs_shortest_paths()

    distances = [network.get_distance(vertex1, vertex2), 
                 network.get_distance(vertex2, vertex1),
                 network.get_distance(vertex1, vertex1),
                 network.get_distance(vertex1, vertex3)]
    expected_distances = [haversine(vertex1.lat, vertex1.lon, vertex2.lat, vertex2.lon), 
                          np.iinfo(np.int32).max,
                          0.0,
                          haversine(vertex1.lat, vertex1.lon, vertex2.lat, vertex2.lon) +
                          haversine(vertex2.lat, vertex2.lon, vertex3.lat, vertex3.lon)]

    for distance, expected_distance in zip(distances, expected_distances):
        assert abs(distance - expected_distance) < 0.01

def test_compute_all_pairs_shortest_paths_truncates_to_two_decimal_places():
    network, trip = setup_network_and_trip()
    network.compute_all_pairs_shortest_paths()
    
    for i in range(len(network.get_all_vertices())):
        for j in range(len(network.get_all_vertices())):
            distance = network._distance_matrix[i, j]
            if distance != np.iinfo(np.int32).max:
                # Check that the distance is truncated to two decimal places
                assert round(distance, 2) == distance

def test_compute_all_pairs_shortest_paths_with_single_vertex_network():
    network = Network()
    vertex = Vertex(network, lat=45.0, lon=126.0, node_id=1)
    
    network.compute_all_pairs_shortest_paths()
    
    assert network._distance_matrix.shape == (1, 1)
    assert network.get_distance(vertex, vertex) == 0.0

def test_compute_all_pairs_shortest_paths_with_single_bidirectional_edge():
    network = Network()
    vertex1 = Vertex(network, lat=45.0, lon=126.0, node_id=1)
    vertex2 = Vertex(network, lat=45.001, lon=126.0, node_id=2)
    edge = Edge(network, start_vertex=vertex1, end_vertex=vertex2,
                non_vertex_nodes=[], edge_type='primary', oneway=False)
    
    network.compute_all_pairs_shortest_paths()
    
    assert network._distance_matrix.shape == (2, 2)
    assert network.get_distance(vertex1, vertex1) == 0.0
    assert network.get_distance(vertex2, vertex2) == 0.0
    assert network.get_distance(vertex1, vertex2) == network.get_distance(vertex2, vertex1)

def test_compute_all_pairs_shortest_paths_with_single_oneway_edge():
    network = Network()
    vertex1 = Vertex(network, lat=45.0, lon=126.0, node_id=1)
    vertex2 = Vertex(network, lat=45.001, lon=126.0, node_id=2)
    edge = Edge(network, start_vertex=vertex1, end_vertex=vertex2,
                non_vertex_nodes=[], edge_type='primary', oneway=True)
    
    network.compute_all_pairs_shortest_paths()
    
    assert network._distance_matrix.shape == (2, 2)
    assert network.get_distance(vertex1, vertex1) == 0.0
    assert network.get_distance(vertex2, vertex2) == 0.0
    assert abs(network.get_distance(vertex1, vertex2) - edge.length) < 0.01
    assert network.get_distance(vertex2, vertex1) == np.iinfo(np.int32).max

def test_compute_all_pairs_shortest_paths_with_disconnected_vertices():
    network = Network()
    vertex1 = Vertex(network, lat=45.0, lon=126.0, node_id=1)
    vertex2 = Vertex(network, lat=46.0, lon=127.0, node_id=2)
    
    network.compute_all_pairs_shortest_paths()
    
    assert network._distance_matrix.shape == (2, 2)
    assert network.get_distance(vertex1, vertex1) == 0.0
    assert network.get_distance(vertex2, vertex2) == 0.0
    assert network.get_distance(vertex1, vertex2) == np.iinfo(np.int32).max
    assert network.get_distance(vertex2, vertex1) == np.iinfo(np.int32).max

def test_compute_all_pairs_shortest_paths_with_three_bidirectionally_connected_vertices():
    network = Network()
    vertex1 = Vertex(network, lat=45.0, lon=126.0, node_id=1)
    vertex2 = Vertex(network, lat=46.0, lon=126.0, node_id=2)
    vertex3 = Vertex(network, lat=46.0, lon=127.0, node_id=3)
    edge1 = Edge(network, start_vertex=vertex1, end_vertex=vertex2,
                 non_vertex_nodes=[], edge_type='primary', oneway=False)
    edge2 = Edge(network, start_vertex=vertex2, end_vertex=vertex3,
                 non_vertex_nodes=[], edge_type='primary', oneway=False)

    network.compute_all_pairs_shortest_paths()

    assert network._distance_matrix.shape == (3, 3)
    assert network.get_distance(vertex1, vertex1) == network.get_distance(vertex2, vertex2) == network.get_distance(vertex3, vertex3) == 0.0
    assert     network.get_distance(vertex1, vertex2) == network.get_distance(vertex2, vertex1) 
    assert abs(network.get_distance(vertex1, vertex2) - edge1.length) < 0.01
    assert     network.get_distance(vertex2, vertex3) == network.get_distance(vertex3, vertex2)
    assert abs(network.get_distance(vertex2, vertex3) - edge2.length) < 0.01
    assert     network.get_distance(vertex1, vertex3) == network.get_distance(vertex3, vertex1) 
    assert abs(network.get_distance(vertex1, vertex3) - (edge1.length + edge2.length)) < 0.02

def test_compute_all_pairs_shortest_paths_with_three_omnidirectionally_connected_vertices():
    network = Network()
    vertex1 = Vertex(network, lat=45.0, lon=126.0, node_id=1)
    vertex2 = Vertex(network, lat=46.0, lon=126.0, node_id=2)
    vertex3 = Vertex(network, lat=46.0, lon=127.0, node_id=3)
    edge1 = Edge(network, start_vertex=vertex1, end_vertex=vertex2,
                 non_vertex_nodes=[], edge_type='primary', oneway=True)
    edge2 = Edge(network, start_vertex=vertex2, end_vertex=vertex3,
                 non_vertex_nodes=[], edge_type='primary', oneway=True)

    network.compute_all_pairs_shortest_paths()

    assert network._distance_matrix.shape == (3, 3)
    assert network.get_distance(vertex1, vertex1) == network.get_distance(vertex2, vertex2) == network.get_distance(vertex3, vertex3) == 0.0
    assert abs(network.get_distance(vertex1, vertex2) - edge1.length) < 0.01
    assert network.get_distance(vertex2, vertex1) == np.iinfo(np.int32).max
    assert abs(network.get_distance(vertex2, vertex3) - edge2.length) < 0.01
    assert network.get_distance(vertex3, vertex2) == np.iinfo(np.int32).max
    assert abs(network.get_distance(vertex1, vertex3) - (edge1.length + edge2.length)) < 0.02
    assert network.get_distance(vertex3, vertex1) == np.iinfo(np.int32).max

def test_compute_all_pairs_shortest_paths_returns_shortest_distance_with_multiple_valid_paths():
    network = Network()
    vertex1 = Vertex(network, lat=45.0, lon=126.0, node_id=1)
    vertex2 = Vertex(network, lat=46.0, lon=126.0, node_id=2)
    vertex3 = Vertex(network, lat=46.0, lon=127.0, node_id=3)
    vertex4 = Vertex(network, lat=45.0, lon=127.0, node_id=4)
    edge1 = Edge(network, start_vertex=vertex1, end_vertex=vertex2,
                 non_vertex_nodes=[], edge_type='primary', oneway=False)
    edge2 = Edge(network, start_vertex=vertex2, end_vertex=vertex3,
                 non_vertex_nodes=[], edge_type='primary', oneway=False)
    edge3 = Edge(network, start_vertex=vertex3, end_vertex=vertex4,
                 non_vertex_nodes=[], edge_type='primary', oneway=False)
    edge4 = Edge(network, start_vertex=vertex1, end_vertex=vertex4,
                 non_vertex_nodes=[], edge_type='primary', oneway=False)

    network.compute_all_pairs_shortest_paths()

    direct_distance = network.get_distance(vertex1, vertex4)
    other_distance = network.get_distance(vertex1, vertex2) + network.get_distance(vertex2, vertex3) + network.get_distance(vertex3, vertex4)

    assert abs(direct_distance - edge4.length) < 0.01
    assert abs(other_distance - (edge1.length + edge2.length + edge3.length)) < 0.03
    assert direct_distance <= other_distance

def test_compute_all_pairs_shortest_paths_index_mapping_is_correct():
    network = Network()
    vertex_ids = [10, 20, 30]
    vertices = [Vertex(network, lat=45.0 + i, lon=126.0 + i, node_id=vid) for i, vid in enumerate(vertex_ids)]

    network.compute_all_pairs_shortest_paths()

    for idx, vid in enumerate(vertex_ids):
        assert network._vertex_id_to_index[vid] == idx
        assert network._index_to_vertex_id[idx] == vid

def test_compute_all_pairs_shortest_paths_is_unchanged_on_repeated_calls():
    network, trip = setup_network_and_trip()
    
    network.compute_all_pairs_shortest_paths()
    first_distance_matrix = network._distance_matrix.copy()
    
    network.compute_all_pairs_shortest_paths()
    second_distance_matrix = network._distance_matrix.copy()
    
    np.testing.assert_array_equal(first_distance_matrix, second_distance_matrix)

def test_get_all_distances_from_throws_error_if_all_pairs_shortest_paths_not_computed():
    network = Network()
    vertex = Vertex(network, lat=45.0, lon=126.0, node_id=1)

    with pytest.raises(RuntimeError):
        network.get_all_distances_from(vertex)

def test_get_all_distances_from_returns_correct_distances():
    network, trip = setup_network_and_trip()
    source_vertex = network.get_vertex_by_id(1002)

    network.compute_all_pairs_shortest_paths()
    distances_from_vertex1 = network.get_all_distances_from(source_vertex)
    expected_distances = {
        network.get_vertex_by_id(1001).id: np.iinfo(np.int32).max,
        network.get_vertex_by_id(1002).id: 0.0,
        network.get_vertex_by_id(1003).id: network.get_edge_by_id(1).length,
        network.get_vertex_by_id(1004).id: network.get_edge_by_id(1).length + network.get_edge_by_id(2).length,
    }

    for vid, expected_distance in expected_distances.items():
        assert abs(distances_from_vertex1[vid] - expected_distance) < 0.01

def test_get_all_distances_from_with_vertex_not_in_network():
    network, trip = setup_network_and_trip()
    network.compute_all_pairs_shortest_paths()
    non_network_vertex = Vertex(network, lat=50.0, lon=130.0, node_id=9999)

    with pytest.raises(RuntimeError):
        network.get_all_distances_from(non_network_vertex)