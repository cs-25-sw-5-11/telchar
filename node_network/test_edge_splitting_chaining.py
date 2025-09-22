import unittest
from classes import Vertex, Edge
from functions_mapping import project_and_split_edges_with_reversibility

class TestEdgeSplittingChaining(unittest.TestCase):
    def setUp(self):
        # Reset class-level dicts and counters
        Vertex.vertex_dict.clear()
        Edge.edge_dict.clear()
        Vertex._id_counter = 1
        Edge._id_counter = 0
        # Create v1 -- e -- v2
        self.v1 = Vertex(None, 0.0, 0.0)
        self.v2 = Vertex(None, 0.0, 2.0)
        self.e = Edge(self.v1, self.v2, [(0.0, 1.0)])
        self.v1.neighbors[self.e] = self.v2
        self.v2.neighbors[self.e] = self.v1
        # Set up a dummy vertices_binned_matrix (1 bin)
        self.vertices_binned_matrix = [[ [self.v1, self.v2] ]]

    def test_chained_splitting(self):
        # Projections: two points between v1 and v2
        # First at (0.0, 0.5), seg_idx=0; second at (0.0, 1.5), seg_idx=1
        projections = [
            (self.e, 0.0, 0.5, 0.5, 0),
            (self.e, 0.0, 1.5, 0.5, 1)
        ]
        changes, vertex_layer = project_and_split_edges_with_reversibility(self.vertices_binned_matrix, projections)
        # There should be 2 new vertices, and none should be None
        self.assertEqual(len(changes['new_vertices']), 2)
        v3, v4 = changes['new_vertices']
        self.assertIsNotNone(v3)
        self.assertIsNotNone(v4)
        # There should be 3 new edges
        self.assertEqual(len(changes['new_edges']), 3)
        # The chain should be: v1 -- e1 -- v3 -- e2 -- v4 -- e3 -- v2
        # Check edge connections
        edge_connections = []
        for edge in changes['new_edges']:
            edge_connections.append((edge.start.id, edge.end.id))
        # Should be [(v1,v3), (v3,v4), (v4,v2)]
        ids = [self.v1.id, v3.id, v4.id, self.v2.id]
        expected = [(ids[0], ids[1]), (ids[1], ids[2]), (ids[2], ids[3])]
        self.assertEqual(edge_connections, expected)
        # Check neighbor relationships
        for edge in changes['new_edges']:
            self.assertIn(edge, edge.start.neighbors)
            self.assertIn(edge, edge.end.neighbors)
        # The original edge should be removed
        self.assertNotIn(self.e.id, Edge.edge_dict)

if __name__ == "__main__":
    unittest.main()
