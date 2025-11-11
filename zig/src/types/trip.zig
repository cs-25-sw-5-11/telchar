const std = @import("std");
const geo = @import("geo.zig");

/// Raw GPS measurement
pub const GpsPoint = struct {
    location: geo.GeoPoint,
    timestamp: i64, // Unix timestamp in seconds
};

/// Complete GPS trajectory
pub const Trip = struct {
    trip_id: u64,
    points: []const GpsPoint, // Owned
    allocator: std.mem.Allocator,

    pub fn deinit(self: *Trip) void {
        self.allocator.free(self.points);
    }
};

/// GPS point projected onto an edge
pub const Projection = struct {
    gps_index: u32,              // Which GPS point in the trip
    edge_id: u32,                // Which edge it projects to
    location: geo.GeoPoint,      // Projected coordinates
    distance_from_start: f64,    // Distance along edge from start vertex
    projection_error: f64,       // Perpendicular distance from GPS to edge
};

/// Complete map-matching result for one trip
pub const MatchedTrip = struct {
    trip_id: u64,
    projections: []const Projection,  // One per GPS point
    path: []const u32,                 // Edge IDs in traversal order
    allocator: std.mem.Allocator,

    pub fn deinit(self: *MatchedTrip) void {
        self.allocator.free(self.projections);
        self.allocator.free(self.path);
    }
};
