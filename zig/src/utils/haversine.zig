const std = @import("std");
const geo = @import("../types/geo.zig");

/// Earth radius in meters (mean radius)
const EARTH_RADIUS_M: f64 = 6371000.0;

/// Compute great-circle distance between two points using Haversine formula
/// Returns distance in meters
pub fn distance(p1: geo.GeoPoint, p2: geo.GeoPoint) f64 {
    const lat1_rad = std.math.degreesToRadians(p1.lat);
    const lat2_rad = std.math.degreesToRadians(p2.lat);
    const delta_lat = std.math.degreesToRadians(p2.lat - p1.lat);
    const delta_lon = std.math.degreesToRadians(p2.lon - p1.lon);

    const a = std.math.sin(delta_lat / 2.0) * std.math.sin(delta_lat / 2.0) +
        std.math.cos(lat1_rad) * std.math.cos(lat2_rad) *
        std.math.sin(delta_lon / 2.0) * std.math.sin(delta_lon / 2.0);

    const c = 2.0 * std.math.atan2(@sqrt(a), @sqrt(1.0 - a));

    return EARTH_RADIUS_M * c;
}

/// Compute distance along a polyline (sequence of points)
pub fn polylineLength(points: []const geo.GeoPoint) f64 {
    if (points.len < 2) return 0.0;

    var total: f64 = 0.0;
    for (points[0 .. points.len - 1], points[1..]) |p1, p2| {
        total += distance(p1, p2);
    }
    return total;
}

test "haversine distance" {
    // Test known distance: London to Paris ~344km
    const london = geo.GeoPoint{ .lat = 51.5074, .lon = -0.1278 };
    const paris = geo.GeoPoint{ .lat = 48.8566, .lon = 2.3522 };
    const dist = distance(london, paris);

    // Should be approximately 344,000 meters (±1%)
    try std.testing.expectApproxEqRel(344000.0, dist, 0.01);
}

test "polyline length" {
    const points = [_]geo.GeoPoint{
        .{ .lat = 0.0, .lon = 0.0 },
        .{ .lat = 0.0, .lon = 0.001 },
        .{ .lat = 0.001, .lon = 0.001 },
    };
    const length = polylineLength(&points);
    try std.testing.expect(length > 0.0);
}
