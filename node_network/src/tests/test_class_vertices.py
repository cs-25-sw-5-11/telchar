from classes import Vertex, Network, Edge
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
    assert (vertex1001.lat, vertex1001.lon) == (45.7015, 126.5505)
    assert vertex1001.get_backward_vertices() == []
    assert len(vertex1001.get_outward_vertices()) == 1
    assert vertex1001.get_outward_vertices()[0].id == 1002
    assert network.get_vertex_by_id(2003) is None

def test_delete_vertex_deletes_vertex():
    network = Network()
    vertex1 = Vertex(network, lat=45.0, lon=126.0, node_id=1)
    
    vertex1.delete_vertex()

    assert vertex1 not in network.get_all_vertices()

def test_get_outward_edges_returns_correct_edges():
    network = build_graph_with_mock_data()
    vertex1002 = network.get_vertex_by_id(1002)
    expected_outward_edge = [network.get_edge_by_id(1)] # Edge from 1002 to 1003

    outward_edges = vertex1002.get_outward_edges()

    assert len(outward_edges) == 1
    assert outward_edges == expected_outward_edge

def test_get_backward_edges_returns_correct_edges():
    network = build_graph_with_mock_data()
    vertex1002 = network.get_vertex_by_id(1002)
    expected_backward_edge = [network.get_edge_by_id(0),  # Edge from 1001 to 1002
                              network.get_edge_by_id(6)]  # Edge from 2002 to 1002

    backward_edges = vertex1002.get_backward_edges()

    assert len(backward_edges) == 2
    assert backward_edges == expected_backward_edge

def test_get_outward_vertices_returns_correct_vertices():
    network = build_graph_with_mock_data()
    vertex1002 = network.get_vertex_by_id(1002)
    expected_outward_vertex = [network.get_vertex_by_id(1003)]

    outward_vertices = vertex1002.get_outward_vertices()

    assert len(outward_vertices) == 1
    assert outward_vertices == expected_outward_vertex

def test_get_backward_vertices_returns_correct_vertices():
    network = build_graph_with_mock_data()
    vertex1002 = network.get_vertex_by_id(1002)
    expected_backward_vertex = [network.get_vertex_by_id(1001),
                                network.get_vertex_by_id(2002)]

    backward_vertices = vertex1002.get_backward_vertices()

    assert len(backward_vertices) == 2
    assert backward_vertices == expected_backward_vertex