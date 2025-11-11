const std = @import("std");
const geo = @import("geo.zig");

/// Unique identifier for vertices (use OSM node IDs)
pub const VertexId = u64;

/// Unique identifier for edges (sequential assignment)
pub const EdgeId = u32;

/// Road network vertex (intersection or endpoint)
pub const Vertex = struct {
    id: VertexId,
    location: geo.GeoPoint,
};

/// Intermediate point along an edge (not a vertex)
pub const EdgeNode = struct {
    location: geo.GeoPoint,
    osm_node_id: u64,
};

/// Road type classification
pub const RoadType = enum {
    motorway,
    trunk,
    primary,
    secondary,
    tertiary,
    residential,
    unclassified,
    service,

    pub fn fromString(s: []const u8) ?RoadType {
        const map = std.ComptimeStringMap(RoadType, .{
            .{ "motorway", .motorway },
            .{ "trunk", .trunk },
            .{ "primary", .primary },
            .{ "secondary", .secondary },
            .{ "tertiary", .tertiary },
            .{ "residential", .residential },
            .{ "unclassified", .unclassified },
            .{ "service", .service },
        });
        return map.get(s);
    }
};

/// Directed edge in the road network
pub const Edge = struct {
    id: EdgeId,
    start_vertex_id: VertexId,
    end_vertex_id: VertexId,
    intermediate_nodes: []const EdgeNode, // Owned by Network
    road_type: RoadType,
    oneway: bool,
    length_meters: f64, // Pre-computed for efficiency
};

/// Complete road network (immutable after construction)
pub const Network = struct {
    vertices: []const Vertex,      // Owned
    edges: []const Edge,            // Owned
    vertex_index: VertexIndex,      // Quick lookup
    edge_index: EdgeIndex,          // Quick lookup
    spatial_index: SpatialIndex,    // Geographic lookup
    allocator: std.mem.Allocator,

    /// Lookup table: VertexId -> array index
    pub const VertexIndex = std.AutoHashMap(VertexId, u32);

    /// Lookup table: EdgeId -> array index
    pub const EdgeIndex = std.AutoHashMap(EdgeId, u32);

    /// Spatial bin -> list of edge indices
    pub const SpatialIndex = std.AutoHashMap(geo.BinIndex, []const u32);

    pub fn deinit(self: *Network) void {
        self.allocator.free(self.vertices);
        for (self.edges) |edge| {
            self.allocator.free(edge.intermediate_nodes);
        }
        self.allocator.free(self.edges);

        var spatial_iter = self.spatial_index.valueIterator();
        while (spatial_iter.next()) |edge_indices| {
            self.allocator.free(edge_indices.*);
        }

        self.vertex_index.deinit();
        self.edge_index.deinit();
        self.spatial_index.deinit();
    }
};

/// Adjacency list representation (for pathfinding algorithms)
pub const AdjacencyList = struct {
    /// Each vertex maps to a list of (neighbor_id, edge_id, distance)
    outgoing: std.AutoHashMap(VertexId, []const Connection),
    allocator: std.mem.Allocator,

    pub const Connection = struct {
        neighbor_id: VertexId,
        edge_id: EdgeId,
        distance_meters: f64,
    };

    pub fn deinit(self: *AdjacencyList) void {
        var iter = self.outgoing.valueIterator();
        while (iter.next()) |connections| {
            self.allocator.free(connections.*);
        }
        self.outgoing.deinit();
    }
};
