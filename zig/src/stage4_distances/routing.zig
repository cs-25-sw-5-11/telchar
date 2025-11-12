const std = @import("std");
const graph = @import("../types/graph.zig");
const geo = @import("../types/geo.zig");
const haversine = @import("../utils/haversine.zig");

/// Route query result
pub const Route = struct {
    edge_ids: []const u32, // Edges traversed in order
    total_distance_m: f64, // Total route distance
    allocator: std.mem.Allocator,

    pub fn deinit(self: *Route) void {
        self.allocator.free(self.edge_ids);
    }
};

/// Bounded A* search for short-distance routing
/// Returns null if no path exists within max_distance
pub fn findShortestPath(
    allocator: std.mem.Allocator,
    network: *const graph.Network,
    adjacency: *const graph.AdjacencyList,
    start_vertex_id: graph.VertexId,
    end_vertex_id: graph.VertexId,
    max_distance_m: f64,
) !?Route {
    if (start_vertex_id == end_vertex_id) {
        return Route{
            .edge_ids = try allocator.alloc(u32, 0),
            .total_distance_m = 0.0,
            .allocator = allocator,
        };
    }

    // Get start and end vertex locations for heuristic
    const start_idx = network.vertex_index.get(start_vertex_id) orelse return null;
    const end_idx = network.vertex_index.get(end_vertex_id) orelse return null;
    const start_vertex = network.vertices[start_idx];
    const end_vertex = network.vertices[end_idx];

    // Priority queue: (f_score, vertex_id)
    var open_set = std.PriorityQueue(AStarNode, void, compareNodes).init(allocator, {});
    defer open_set.deinit();

    // Best known distance to each vertex
    var g_scores = std.AutoHashMap(graph.VertexId, f64).init(allocator);
    defer g_scores.deinit();

    // Parent pointers for path reconstruction
    var came_from = std.AutoHashMap(graph.VertexId, PathParent).init(allocator);
    defer came_from.deinit();

    // Initialize
    try g_scores.put(start_vertex_id, 0.0);
    const h_start = haversine.distance(start_vertex.location, end_vertex.location);
    try open_set.add(.{
        .vertex_id = start_vertex_id,
        .f_score = h_start,
        .g_score = 0.0,
    });

    while (open_set.removeOrNull()) |current| {
        // Check if reached goal
        if (current.vertex_id == end_vertex_id) {
            return try reconstructPath(allocator, &came_from, start_vertex_id, end_vertex_id, current.g_score);
        }

        // Check distance bound
        if (current.g_score > max_distance_m) continue;

        // Explore neighbors
        if (adjacency.outgoing.get(current.vertex_id)) |connections| {
            for (connections) |conn| {
                const tentative_g = current.g_score + conn.distance_meters;
                const existing_g = g_scores.get(conn.neighbor_id) orelse std.math.inf(f64);

                if (tentative_g < existing_g and tentative_g <= max_distance_m) {
                    try g_scores.put(conn.neighbor_id, tentative_g);
                    try came_from.put(conn.neighbor_id, .{
                        .parent_id = current.vertex_id,
                        .edge_id = conn.edge_id,
                    });

                    // Heuristic: great-circle distance to goal
                    const neighbor_idx = network.vertex_index.get(conn.neighbor_id) orelse continue;
                    const neighbor_vertex = network.vertices[neighbor_idx];
                    const h_score = haversine.distance(neighbor_vertex.location, end_vertex.location);

                    try open_set.add(.{
                        .vertex_id = conn.neighbor_id,
                        .f_score = tentative_g + h_score,
                        .g_score = tentative_g,
                    });
                }
            }
        }
    }

    // No path found within distance bound
    return null;
}

const AStarNode = struct {
    vertex_id: graph.VertexId,
    f_score: f64, // g + h (priority)
    g_score: f64, // Distance from start
};

const PathParent = struct {
    parent_id: graph.VertexId,
    edge_id: u32,
};

fn compareNodes(context: void, a: AStarNode, b: AStarNode) std.math.Order {
    _ = context;
    return std.math.order(a.f_score, b.f_score);
}

fn reconstructPath(
    allocator: std.mem.Allocator,
    came_from: *const std.AutoHashMap(graph.VertexId, PathParent),
    start_id: graph.VertexId,
    end_id: graph.VertexId,
    total_distance: f64,
) !Route {
    var path_edges = std.ArrayList(u32){};
    defer path_edges.deinit(allocator);

    var current_id = end_id;
    while (current_id != start_id) {
        const parent = came_from.get(current_id) orelse break;
        try path_edges.append(allocator, parent.edge_id);
        current_id = parent.parent_id;
    }

    // Reverse path (we built it backwards)
    std.mem.reverse(u32, path_edges.items);

    return Route{
        .edge_ids = try path_edges.toOwnedSlice(allocator),
        .total_distance_m = total_distance,
        .allocator = allocator,
    };
}

/// Alternative: Upper Bounded Origin-Destination Table (UBODT)
/// Precomputes shortest paths between nearby edges (FMM approach)
/// For static networks in offline batch processing: 100-200× speedup
pub const UBODT = struct {
    /// Map: (source_edge_id, target_edge_id) -> Route
    paths: std.AutoHashMap(EdgePair, StoredRoute),
    allocator: std.mem.Allocator,

    pub const EdgePair = struct {
        source: u32,
        target: u32,

        pub fn hash(self: EdgePair) u64 {
            const h1 = @as(u64, self.source);
            const h2 = @as(u64, self.target);
            return h1 ^ (h2 << 32);
        }

        pub fn eql(a: EdgePair, b: EdgePair) bool {
            return a.source == b.source and a.target == b.target;
        }
    };

    pub const StoredRoute = struct {
        edge_ids: []const u32,
        distance_m: f64,
    };

    pub fn init(allocator: std.mem.Allocator) UBODT {
        return .{
            .paths = std.AutoHashMap(EdgePair, StoredRoute).init(allocator),
            .allocator = allocator,
        };
    }

    pub fn deinit(self: *UBODT) void {
        var iter = self.paths.valueIterator();
        while (iter.next()) |route| {
            self.allocator.free(route.edge_ids);
        }
        self.paths.deinit();
    }

    /// Precompute all paths between edges within threshold distance
    pub fn precompute(
        allocator: std.mem.Allocator,
        network: *const graph.Network,
        adjacency: *const graph.AdjacencyList,
        max_distance_m: f64,
    ) !UBODT {
        var table = UBODT.init(allocator);

        // For each edge, compute paths to all reachable edges
        for (network.edges) |source_edge| {
            for (network.edges) |target_edge| {
                if (source_edge.id == target_edge.id) continue;

                // Try to find path
                if (try findShortestPath(
                    allocator,
                    network,
                    adjacency,
                    source_edge.end_vertex_id,
                    target_edge.start_vertex_id,
                    max_distance_m,
                )) |route| {
                    defer {
                        var mut_route = route;
                        mut_route.deinit();
                    }

                    try table.paths.put(
                        .{ .source = source_edge.id, .target = target_edge.id },
                        .{
                            .edge_ids = try allocator.dupe(u32, route.edge_ids),
                            .distance_m = route.total_distance_m,
                        },
                    );
                }
            }
        }

        return table;
    }

    /// Query precomputed path (microsecond lookup)
    pub fn query(self: *const UBODT, source_edge_id: u32, target_edge_id: u32) ?StoredRoute {
        return self.paths.get(.{ .source = source_edge_id, .target = target_edge_id });
    }
};

/// Build adjacency list from network (helper function)
pub fn buildAdjacencyList(
    allocator: std.mem.Allocator,
    network: *const graph.Network,
) !graph.AdjacencyList {
    var outgoing = std.AutoHashMap(graph.VertexId, std.ArrayList(graph.AdjacencyList.Connection)).init(allocator);
    defer {
        var iter = outgoing.valueIterator();
        while (iter.next()) |list| {
            list.deinit(allocator);
        }
        outgoing.deinit();
    }

    // Build temporary map
    for (network.edges) |edge| {
        // Forward direction
        {
            const entry = try outgoing.getOrPut(edge.start_vertex_id);
            if (!entry.found_existing) {
                entry.value_ptr.* = std.ArrayList(graph.AdjacencyList.Connection){};
            }
            try entry.value_ptr.append(allocator, .{
                .neighbor_id = edge.end_vertex_id,
                .edge_id = edge.id,
                .distance_meters = edge.length_meters,
            });
        }

        // Backward direction (if not oneway)
        if (!edge.oneway) {
            const entry = try outgoing.getOrPut(edge.end_vertex_id);
            if (!entry.found_existing) {
                entry.value_ptr.* = std.ArrayList(graph.AdjacencyList.Connection){};
            }
            try entry.value_ptr.append(allocator, .{
                .neighbor_id = edge.start_vertex_id,
                .edge_id = edge.id,
                .distance_meters = edge.length_meters,
            });
        }
    }

    // Convert to owned slices
    var result = graph.AdjacencyList{
        .outgoing = std.AutoHashMap(graph.VertexId, []const graph.AdjacencyList.Connection).init(allocator),
        .allocator = allocator,
    };

    var iter = outgoing.iterator();
    while (iter.next()) |entry| {
        try result.outgoing.put(entry.key_ptr.*, try entry.value_ptr.toOwnedSlice(allocator));
    }

    return result;
}

test "A* basic routing" {
    const allocator = std.testing.allocator;

    // Create simple test network
    const vertices = [_]graph.Vertex{
        .{ .id = 1, .location = .{ .lat = 45.0, .lon = 126.0 }, .osm_node_id = 1 },
        .{ .id = 2, .location = .{ .lat = 45.01, .lon = 126.0 }, .osm_node_id = 2 },
        .{ .id = 3, .location = .{ .lat = 45.02, .lon = 126.0 }, .osm_node_id = 3 },
    };

    const edges = [_]graph.Edge{
        .{
            .id = 1,
            .start_vertex_id = 1,
            .end_vertex_id = 2,
            .intermediate_nodes = &[_]graph.EdgeNode{},
            .road_type = .primary,
            .oneway = false,
            .length_meters = 1000.0,
        },
        .{
            .id = 2,
            .start_vertex_id = 2,
            .end_vertex_id = 3,
            .intermediate_nodes = &[_]graph.EdgeNode{},
            .road_type = .primary,
            .oneway = false,
            .length_meters = 1000.0,
        },
    };

    var vertex_index = std.AutoHashMap(graph.VertexId, usize).init(allocator);
    defer vertex_index.deinit();

    for (vertices, 0..) |v, i| {
        try vertex_index.put(v.id, i);
    }

    var edge_index = std.AutoHashMap(u32, usize).init(allocator);
    defer edge_index.deinit();

    for (edges, 0..) |e, i| {
        try edge_index.put(e.id, i);
    }

    const network = graph.Network{
        .vertices = &vertices,
        .edges = &edges,
        .vertex_index = vertex_index,
        .edge_index = edge_index,
        .spatial_index = graph.Network.SpatialIndex.init(allocator),
        .bin_config = .{ .lat_min = 45.0, .lon_min = 126.0, .bin_size = 0.001 },
        .allocator = allocator,
    };

    var adjacency = try buildAdjacencyList(allocator, &network);
    defer adjacency.deinit();

    // Test routing from vertex 1 to 3
    var route = try findShortestPath(
        allocator,
        &network,
        &adjacency,
        1,
        3,
        5000.0,
    ) orelse {
        try std.testing.expect(false); // Should find a path
        return;
    };
    defer route.deinit();

    // Should find path through edge 1 and edge 2
    try std.testing.expectEqual(@as(usize, 2), route.edge_ids.len);
    try std.testing.expectApproxEqRel(2000.0, route.total_distance_m, 0.1);
}
