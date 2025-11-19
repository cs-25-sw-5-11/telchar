from classes import Vertex, Network
from utils.functions_misc import get_bin_indices
from .utils_functions import build_graph_with_mock_data

def test_created_vertex_is_assigned_to_network():
    # Arrange
    network = Network()
    
    # Act
    vertex = Vertex(network, lat=45.0, lon=126.0, node_id=1)

    # Assert
    assert vertex.network == network
    assert network.get_vertex_by_id(1) == vertex
    assert vertex in network.get_all_vertices()

def test_duplicate_vertex_returns_existing_instance():
    network = Network()
    vertex1 = Vertex(network, lat=45.0, lon=126.0, node_id=1)
    
    vertex2 = Vertex(network, lat=45.0, lon=126.0, node_id=1)

    assert vertex1 is vertex2
    assert len(network.get_all_vertices()) == 1

def test_vertex_is_in_correct_bin():
    network = Network()
    lat, lon = 45.123456, 126.654321
    expected_bin = get_bin_indices(lat, lon)
    
    vertex = Vertex(network, lat=lat, lon=lon, node_id=1)

    assert vertex.bin_coords == expected_bin

def test_delete_vertex_removes_it_from_network():
    network = Network()
    vertex = Vertex(network, lat=45.0, lon=126.0, node_id=1)
    
    vertex.delete_vertex()

    assert network.get_vertex_by_id(1) is None
    assert vertex not in network.get_all_vertices()

def test_build_graph_creates_appropriate_vertices_with_mock_data():
    network = build_graph_with_mock_data()

    vertex1001 = network.get_vertex_by_id(1001)

    assert len(network.get_all_vertices()) == 8
    assert vertex1001 is not None
    assert (vertex1001.lat, vertex1001.lon) == (45.001, 126.001)
    assert vertex1001.get_backward_vertices() == []
    assert len(vertex1001.get_outward_vertices()) == 1
    assert vertex1001.get_outward_vertices()[0].id == 1002
    assert network.get_vertex_by_id(2003) is None