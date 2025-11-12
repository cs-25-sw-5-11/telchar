const std = @import("std");
const geo = @import("../types/geo.zig");
const graph = @import("../types/graph.zig");
const haversine = @import("../utils/haversine.zig");

/// Result of projecting a point onto an edge
pub const ProjectionResult = struct {
    edge_id: graph.EdgeId,
    projected_point: geo.GeoPoint,
    distance_from_start: f64,  // Along edge
    perpendicular_distance: f64, // Error
    segment_index: u32,        // Which segment of edge
    segment_t: f64,            // Parameter [0,1] along segment
};

/// Find all edges within max_distance of a GPS point and project onto them
pub fn projectPoint(
    allocator: std.mem.Allocator,
    gps_point: geo.GeoPoint,
    network: *const graph.Network,
    max_distance_m: f64,
) ![]ProjectionResult {
    var candidates = std.ArrayList(ProjectionResult){};
    errdefer candidates.deinit(allocator);

    // Use spatial index to find nearby edges
    const nearby_edges = try network.findNearbyEdges(allocator, gps_point, max_distance_m);
    defer allocator.free(nearby_edges);

    for (nearby_edges) |edge_id| {
        const edge = network.edges[edge_id];

        if (projectPointOntoEdge(allocator, gps_point, edge, network.vertices)) |result| {
            if (result.perpendicular_distance <= max_distance_m) {
                var proj_with_id = result;
                proj_with_id.edge_id = edge_id;
                try candidates.append(allocator, proj_with_id);
            }
        }
    }

    return try candidates.toOwnedSlice(allocator);
}

/// Project a GPS point onto an edge
/// Returns null if projection fails
pub fn projectPointOntoEdge(
    allocator: std.mem.Allocator,
    gps_point: geo.GeoPoint,
    edge: graph.Edge,
    vertices: []const graph.Vertex,
) ?ProjectionResult {
    // Build polyline: start vertex -> intermediate nodes -> end vertex
    var points = std.ArrayList(geo.GeoPoint){};
    defer points.deinit(allocator);

    // Find vertices
    const start_vertex = findVertex(vertices, edge.start_vertex_id) orelse return null;
    const end_vertex = findVertex(vertices, edge.end_vertex_id) orelse return null;

    points.append(allocator, start_vertex.location) catch return null;
    for (edge.intermediate_nodes) |node| {
        points.append(allocator, node.location) catch return null;
    }
    points.append(allocator, end_vertex.location) catch return null;

    // Find closest point on polyline
    var min_perp_dist: f64 = std.math.inf(f64);
    var best_result: ?ProjectionResult = null;
    var cumulative_dist: f64 = 0.0;

    for (points.items[0 .. points.items.len - 1], 0..) |p1, i| {
        const p2 = points.items[i + 1];
        const segment_length = haversine.distance(p1, p2);

        // Project point onto line segment [p1, p2]
        const proj = projectPointOntoSegment(gps_point, p1, p2);

        if (proj.perpendicular_distance < min_perp_dist) {
            min_perp_dist = proj.perpendicular_distance;
            best_result = ProjectionResult{
                .edge_id = 0, // Will be set by caller
                .projected_point = proj.point,
                .distance_from_start = cumulative_dist + proj.t * segment_length,
                .perpendicular_distance = proj.perpendicular_distance,
                .segment_index = @intCast(i),
                .segment_t = proj.t,
            };
        }

        cumulative_dist += segment_length;
    }

    return best_result;
}

const SegmentProjection = struct {
    point: geo.GeoPoint,
    t: f64, // Parameter [0,1]
    perpendicular_distance: f64,
};

/// Project point onto line segment [p1, p2]
fn projectPointOntoSegment(
    point: geo.GeoPoint,
    p1: geo.GeoPoint,
    p2: geo.GeoPoint,
) SegmentProjection {
    const dx = p2.lon - p1.lon;
    const dy = p2.lat - p1.lat;

    if (dx == 0.0 and dy == 0.0) {
        // Degenerate segment
        return .{
            .point = p1,
            .t = 0.0,
            .perpendicular_distance = haversine.distance(point, p1),
        };
    }

    // Project onto infinite line
    const t_unclamped = ((point.lon - p1.lon) * dx + (point.lat - p1.lat) * dy) /
                        (dx * dx + dy * dy);
    const t = std.math.clamp(t_unclamped, 0.0, 1.0);

    const proj_point = geo.GeoPoint{
        .lat = p1.lat + t * dy,
        .lon = p1.lon + t * dx,
    };

    return .{
        .point = proj_point,
        .t = t,
        .perpendicular_distance = haversine.distance(point, proj_point),
    };
}

fn findVertex(vertices: []const graph.Vertex, id: graph.VertexId) ?graph.Vertex {
    for (vertices) |v| {
        if (v.id == id) return v;
    }
    return null;
}

test "segment projection - perpendicular" {
    const p1 = geo.GeoPoint{ .lat = 0.0, .lon = 0.0 };
    const p2 = geo.GeoPoint{ .lat = 0.0, .lon = 1.0 };
    const point = geo.GeoPoint{ .lat = 0.5, .lon = 0.5 };

    const result = projectPointOntoSegment(point, p1, p2);
    try std.testing.expectApproxEqRel(0.5, result.t, 0.0001);
}

test "segment projection - endpoint clamping" {
    const p1 = geo.GeoPoint{ .lat = 0.0, .lon = 0.0 };
    const p2 = geo.GeoPoint{ .lat = 0.0, .lon = 1.0 };
    const point = geo.GeoPoint{ .lat = 0.0, .lon = 2.0 }; // Beyond p2

    const result = projectPointOntoSegment(point, p1, p2);
    try std.testing.expectEqual(1.0, result.t);
}
