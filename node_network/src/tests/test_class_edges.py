from classes import Vertex, Edge, Network
from utils.functions_misc import get_bin_indices, haversine
from .utils_functions import build_graph_with_mock_data
from configs.config import LAT_BIN_SIZE, LON_BIN_SIZE, LAT_MIN, LON_MIN

def test_created_vertex_is_assigned_to_network():
    # Arrange
    network = Network()
    vertex1 = Vertex(network, lat=45.0, lon=126.0, node_id=1)
    vertex2 = Vertex(network, lat=46.0, lon=127.0, node_id=5)

    # Act
    edge = Edge(network=network, start_vertex=vertex1, end_vertex=vertex2, 
                non_vertex_nodes=[], edge_type="primary", oneway=True)
    
    # Assert
    assert edge.network == network
    assert edge in network.get_all_edges()

def test_edge_connects_start_and_end_vertices():
    network = Network()
    vertex1 = Vertex(network, lat=45.0, lon=126.0, node_id=1)
    vertex2 = Vertex(network, lat=46.0, lon=127.0, node_id=5)

    edge = Edge(network=network, start_vertex=vertex1, end_vertex=vertex2, 
                non_vertex_nodes=[], edge_type="primary", oneway=True)

    assert edge in vertex1.get_outward_edges()
    assert edge not in vertex1.get_backward_edges()
    assert edge in vertex2.get_backward_edges()
    assert edge not in vertex2.get_outward_edges()
    assert vertex2 in vertex1.get_outward_vertices()
    assert vertex2 not in vertex1.get_backward_vertices()
    assert vertex1 in vertex2.get_backward_vertices()
    assert vertex1 not in vertex2.get_outward_vertices()

def test_created_edge_is_in_appropriate_bins():
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
    bins_covered = [
        get_bin_indices(LAT_MIN + LAT_BIN_SIZE / 2, LON_MIN + LON_BIN_SIZE / 2),
        get_bin_indices(LAT_MIN + LAT_BIN_SIZE / 2, LON_MIN + LON_BIN_SIZE * 1.5),
        get_bin_indices(LAT_MIN + LAT_BIN_SIZE / 2, LON_MIN + LON_BIN_SIZE * 2.5),
        get_bin_indices(LAT_MIN + LAT_BIN_SIZE * 1.5, LON_MIN + LON_BIN_SIZE * 2.5),
        get_bin_indices(LAT_MIN + LAT_BIN_SIZE * 2.5, LON_MIN + LON_BIN_SIZE * 2.5)
    ]
    bins_covered_set = set(bins_covered)

    assert edge.bins_covered == bins_covered_set
    assert network.get_edges_in_bin(bins_covered[0][0], bins_covered[0][1]) == [edge]
    assert network.get_edges_in_bin(bins_covered[1][0], bins_covered[1][1]) == [edge]
    assert network.get_edges_in_bin(bins_covered[2][0], bins_covered[2][1]) == [edge]
    assert network.get_edges_in_bin(bins_covered[3][0], bins_covered[3][1]) == [edge]
    assert network.get_edges_in_bin(bins_covered[4][0], bins_covered[4][1]) == [edge]
    assert network.get_edges_in_bin(9999, 9999) == []

def test_delete_edge_removes_it_from_network():
    network = Network()
    vertex1 = Vertex(network, lat=45.0, lon=126.0, node_id=1)
    vertex2 = Vertex(network, lat=46.0, lon=127.0, node_id=5)
    
    edge = Edge(network=network, start_vertex=vertex1, end_vertex=vertex2, 
                non_vertex_nodes=[], edge_type="primary", oneway=True)
    edge.delete_edge()

    assert edge not in network.get_all_edges()
    assert edge not in vertex1.get_outward_edges()
    assert edge not in vertex2.get_backward_edges()

def test_delete_vertex_also_deletes_connected_edges():
    network = Network()
    vertex1 = Vertex(network, lat=45.0, lon=126.0, node_id=1)
    vertex2 = Vertex(network, lat=46.0, lon=127.0, node_id=5)
    
    edge = Edge(network=network, start_vertex=vertex1, end_vertex=vertex2, 
                non_vertex_nodes=[], edge_type="primary", oneway=True)
    vertex1.delete_vertex()

    assert edge not in network.get_all_edges()
    assert vertex1 not in network.get_all_vertices()
    assert vertex2 in network.get_all_vertices()
    assert edge not in vertex2.get_backward_edges()

def test_edge_has_correct_length():
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
    distance = haversine(vertex1.lat, vertex1.lon, non_vertex_nodes[1][0], non_vertex_nodes[1][1]) + \
               haversine(non_vertex_nodes[1][0], non_vertex_nodes[1][1], vertex2.lat, vertex2.lon)
    
    assert abs(edge.length - distance) < 0.1  # Allow small floating point error

def test_traversal_data_is_correctly_updated():
    network = Network()
    vertex1 = Vertex(network, lat=45.0, lon=126.0, node_id=1)
    vertex2 = Vertex(network, lat=46.0, lon=127.0, node_id=5)

    edge = Edge(network=network, start_vertex=vertex1, end_vertex=vertex2, 
                non_vertex_nodes=[], edge_type="primary", oneway=True)
    initial_traversal_data = edge.traversals_data.copy()
    edge.traversals_data_update(0, 10)
    edge.traversals_data_update(0, 30)

    assert initial_traversal_data == {}
    assert abs(edge.traversals_data[0][0] - 2000) < 0.1 # cm/s rather than m/s, allow small floating point error
    assert edge.traversals_data[0][2] == 2

def test_project_coordinates_onto_edge_returns_correct_results():
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
    proj_lat = LAT_MIN
    proj_lon = LON_MIN + LON_BIN_SIZE * 2
    lat, lon, min_dist, seg_idx, seg_t = edge.project_coordinates_onto_edge(proj_lat, proj_lon)

    # Allowing small floating point errors.
    assert abs(lat - (LAT_MIN + LAT_BIN_SIZE / 2) ) < 0.000001
    assert abs(lon - (LON_MIN + LON_BIN_SIZE * 2) ) < 0.000001
    assert seg_idx == 1 # Second segment, between the first and second non-vertex-nodes.
    assert abs(seg_t - 0.5) < 0.000001 # Halfway along the segment.
    assert abs(min_dist - haversine(proj_lat, proj_lon, lat, lon)) < 0.1

def test_get_projection_distance_from_start_returns_correct_distance():
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
    
    # Projected point on second segment, halfway along.
    proj_lat = LAT_MIN + LAT_BIN_SIZE / 2
    proj_lon = LON_MIN + LON_BIN_SIZE * 2
    distance_from_start = edge.get_projection_distance_from_start(1, 0.5)

    expected_distance = haversine(vertex1.lat, vertex1.lon, non_vertex_nodes[0][0], non_vertex_nodes[0][1]) + \
                        haversine(non_vertex_nodes[0][0], non_vertex_nodes[0][1], proj_lat, proj_lon)
    
    assert abs(distance_from_start - expected_distance) < 0.1  # Allow small floating point error