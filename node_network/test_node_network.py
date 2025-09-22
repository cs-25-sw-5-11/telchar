import unittest
from classes import Vertex, Edge, haversine
import functions_analysis as fa
import functions_building as fb
import functions_mapping as fm
import functions_plotting as fp
import math

class TestNodeNetwork(unittest.TestCase):
    def test_integration_projection_and_network_distances(self):
        from config import LAT_MIN, LON_MIN, LAT_BIN_SIZE, LON_BIN_SIZE
        # Create a simple network: v1 -- e1 -- v2 -- e2 -- v3
        v1 = Vertex(None, LAT_MIN + 0.1 * LAT_BIN_SIZE, LON_MIN + 0.1 * LON_BIN_SIZE)
        v2 = Vertex(None, LAT_MIN + 0.5 * LAT_BIN_SIZE, LON_MIN + 0.5 * LON_BIN_SIZE)
        v3 = Vertex(None, LAT_MIN + 0.9 * LAT_BIN_SIZE, LON_MIN + 0.9 * LON_BIN_SIZE)
        e1 = Edge(v1, v2, [])
        e2 = Edge(v2, v3, [])
        v1.neighbors[e1] = v2
        v2.neighbors[e1] = v1
        v2.neighbors[e2] = v3
        v3.neighbors[e2] = v2
        # Bin matrix for projection
        matrix = [[[] for _ in range(2)] for _ in range(2)]
        idx1 = fa.get_bin_indices(v1.lat, v1.lon)
        idx2 = fa.get_bin_indices(v2.lat, v2.lon)
        idx3 = fa.get_bin_indices(v3.lat, v3.lon)
        matrix[idx1[0]][idx1[1]].append(v1)
        matrix[idx2[0]][idx2[1]].append(v2)
        matrix[idx3[0]][idx3[1]].append(v3)
        # Project onto e1 and e2 at their midpoints
        proj1 = (e1, (v1.lat + v2.lat)/2, (v1.lon + v2.lon)/2, 0, 0)
        proj2 = (e2, (v2.lat + v3.lat)/2, (v2.lon + v3.lon)/2, 0, 0)
        changes, layer1 = fm.project_and_split_edges_with_reversibility(matrix, [proj1], tolerance=1e-9)
        _, layer2 = fm.project_and_split_edges_with_reversibility(matrix, [proj2], tolerance=1e-9)
        # Now compute all-pairs network distances between the two layers
        dists = fm.all_pairs_network_distances_between_layers(layer1, layer2)
        # There should be a path from the projected vertex on e1 to the projected vertex on e2
        for v_from in layer1:
            for v_to in layer2:
                self.assertTrue(math.isfinite(dists[v_from][v_to]))
                self.assertGreaterEqual(dists[v_from][v_to], 0)
    def setUp(self):
        # Reset class-level dicts and counters
        Vertex.vertex_dict.clear()
        Vertex._id_counter = 1
        Edge.edge_dict.clear()
        Edge._id_counter = 0

    def test_vertex_and_edge_creation(self):
        v1 = Vertex(None, 10, 20)
        v2 = Vertex(None, 11, 21)
        e = Edge(v1, v2, [])
        self.assertEqual(v1.lat, 10)
        self.assertEqual(v2.lon, 21)
        self.assertEqual(e.start, v1)
        self.assertEqual(e.end, v2)
        self.assertTrue(e.id in Edge.edge_dict)

    def test_haversine(self):
        d = haversine(0, 0, 0, 1)
        self.assertTrue(110000 < d < 112000)  # ~111km per degree

    def test_bin_indices(self):
        from config import LAT_MIN, LON_MIN, LAT_BIN_SIZE, LON_BIN_SIZE
        lat, lon = LAT_MIN + 0.5 * LAT_BIN_SIZE, LON_MIN + 0.5 * LON_BIN_SIZE
        idx = fa.get_bin_indices(lat, lon)
        self.assertIsNotNone(idx)

    def test_bin_edges_by_lat_lon(self):
        from config import LAT_MIN, LON_MIN, LAT_BIN_SIZE, LON_BIN_SIZE
        v1 = Vertex(None, LAT_MIN + 0.1 * LAT_BIN_SIZE, LON_MIN + 0.1 * LON_BIN_SIZE)
        v2 = Vertex(None, LAT_MIN + 0.9 * LAT_BIN_SIZE, LON_MIN + 0.9 * LON_BIN_SIZE)
        e = Edge(v1, v2, [(LAT_MIN + 0.5 * LAT_BIN_SIZE, LON_MIN + 0.5 * LON_BIN_SIZE)])
        matrix = fa.bin_edges_by_lat_lon()
        found = False
        for row in matrix:
            for cell in row:
                if e in cell:
                    found = True
        self.assertTrue(found)

    def test_project_point(self):
        v1 = Vertex(None, 0, 0)
        v2 = Vertex(None, 0, 1)
        e = Edge(v1, v2, [])
        proj = e.project_coordinates_onto_edge(0, 0.5)
        self.assertAlmostEqual(proj[0], 0, places=6)
        self.assertAlmostEqual(proj[1], 0.5, places=6)
        self.assertAlmostEqual(proj[2], 0, places=2)

    def test_find_or_create_vertex_at_projection(self):
        from config import LAT_MIN, LON_MIN, LAT_BIN_SIZE, LON_BIN_SIZE
        # Create a 2x2 bin matrix
        matrix = [[[] for _ in range(2)] for _ in range(2)]
        v1 = Vertex(None, LAT_MIN + 0.1 * LAT_BIN_SIZE, LON_MIN + 0.1 * LON_BIN_SIZE)
        v2 = Vertex(None, LAT_MIN + 1.1 * LAT_BIN_SIZE, LON_MIN + 1.1 * LON_BIN_SIZE)
        idx1 = fa.get_bin_indices(v1.lat, v1.lon)
        idx2 = fa.get_bin_indices(v2.lat, v2.lon)
        matrix[idx1[0]][idx1[1]].append(v1)
        matrix[idx2[0]][idx2[1]].append(v2)
        v, created = fm.find_or_create_vertex_at_projection(v1.lat, v1.lon, matrix, tolerance=1e-9)
        self.assertFalse(created)
        # Try a new coordinate in a different bin
        lat_new = LAT_MIN + 1.5 * LAT_BIN_SIZE
        lon_new = LON_MIN + 1.5 * LON_BIN_SIZE
        v, created = fm.find_or_create_vertex_at_projection(lat_new, lon_new, matrix, tolerance=1e-9)
        self.assertTrue(created)

    def test_project_and_split_edges_with_reversibility(self):
        from config import LAT_MIN, LON_MIN, LAT_BIN_SIZE, LON_BIN_SIZE
        v1 = Vertex(None, LAT_MIN + 0.1 * LAT_BIN_SIZE, LON_MIN + 0.1 * LON_BIN_SIZE)
        v2 = Vertex(None, LAT_MIN + 0.9 * LAT_BIN_SIZE, LON_MIN + 0.9 * LON_BIN_SIZE)
        e = Edge(v1, v2, [])
        v1.neighbors[e] = v2
        v2.neighbors[e] = v1
        # 2x2 bin matrix
        matrix = [[[] for _ in range(2)] for _ in range(2)]
        idx1 = fa.get_bin_indices(v1.lat, v1.lon)
        idx2 = fa.get_bin_indices(v2.lat, v2.lon)
        matrix[idx1[0]][idx1[1]].append(v1)
        matrix[idx2[0]][idx2[1]].append(v2)
        proj = [(e, LAT_MIN + 0.5 * LAT_BIN_SIZE, LON_MIN + 0.5 * LON_BIN_SIZE, 0, 0)]
        changes, layer = fm.project_and_split_edges_with_reversibility(matrix, proj, tolerance=1e-9)
        self.assertEqual(len(changes['new_vertices']), 1)
        self.assertEqual(len(changes['new_edges']), 2)
        self.assertEqual(len(changes['removed_edges']), 1)
        # Undo
        fm.undo_project_and_split_changes(changes)
        self.assertNotIn(layer[0].id, Vertex.vertex_dict)

    def test_all_pairs_network_distances_between_layers(self):
        v1 = Vertex(None, 0, 0)
        v2 = Vertex(None, 0, 1)
        v3 = Vertex(None, 0, 2)
        e1 = Edge(v1, v2, [])
        e2 = Edge(v2, v3, [])
        v1.neighbors[e1] = v2
        v2.neighbors[e2] = v3
        layer1 = [v1]
        layer2 = [v2, v3]
        dists = fm.all_pairs_network_distances_between_layers(layer1, layer2)
        self.assertAlmostEqual(dists[v1][v2], e1.length, places=6)
        self.assertAlmostEqual(dists[v1][v3], e1.length + e2.length, places=6)

if __name__ == '__main__':
    unittest.main()
