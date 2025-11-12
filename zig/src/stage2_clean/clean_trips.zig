const std = @import("std");
const trip_types = @import("../types/trip.zig");
const geo = @import("../types/geo.zig");
const haversine = @import("../utils/haversine.zig");

// Re-export CSV parser functionality
const csv_parser = @import("csv_parser.zig");
pub const parseTripCsv = csv_parser.parseTripCsv;
pub const parseTripCsvDirectory = csv_parser.parseTripCsvDirectory;
pub const TripData = csv_parser.TripData;
pub const GpsPoint = csv_parser.GpsPoint;

pub const CleaningConfig = struct {
    max_speed_mps: f64 = 41.67, // 150 km/h
    min_points: usize = 5,
    max_time_gap_sec: i64 = 300, // 5 minutes
    bounding_box: geo.BoundingBox,
};

pub const CleaningResult = struct {
    valid_trips: []const trip_types.Trip, // Owned
    invalid_count: usize,
    allocator: std.mem.Allocator,

    pub fn deinit(self: *CleaningResult) void {
        for (self.valid_trips) |*trip| {
            var mutable_trip = trip.*;
            mutable_trip.deinit();
        }
        self.allocator.free(self.valid_trips);
    }
};

/// Clean a batch of trips, filtering out invalid ones
/// Takes ownership of raw_trips and will free invalid ones
pub fn cleanTrips(
    allocator: std.mem.Allocator,
    raw_trips: []trip_types.Trip,
    config: CleaningConfig,
) !CleaningResult {
    var valid_trips = std.ArrayList(trip_types.Trip){};
    defer valid_trips.deinit(allocator);

    var invalid_count: usize = 0;

    for (raw_trips) |*trip| {
        if (try isValidTrip(trip.*, config)) {
            try valid_trips.append(allocator, trip.*);
        } else {
            // Free invalid trip data
            var mutable_trip = trip.*;
            mutable_trip.deinit();
            invalid_count += 1;
        }
    }

    return CleaningResult{
        .valid_trips = try valid_trips.toOwnedSlice(allocator),
        .invalid_count = invalid_count,
        .allocator = allocator,
    };
}

/// Check if a trip passes validation criteria
fn isValidTrip(trip: trip_types.Trip, config: CleaningConfig) !bool {
    // Check minimum points
    if (trip.points.len < config.min_points) {
        return false;
    }

    // Check all points within bounding box
    for (trip.points) |point| {
        if (!config.bounding_box.contains(point.location)) {
            return false;
        }
    }

    // Check for time gaps and excessive speeds
    for (trip.points[0 .. trip.points.len - 1], trip.points[1..]) |p1, p2| {
        const time_diff = p2.timestamp - p1.timestamp;

        // Check time gap
        if (time_diff > config.max_time_gap_sec or time_diff <= 0) {
            return false;
        }

        // Check speed
        const distance = haversine.distance(p1.location, p2.location);
        const speed_mps = distance / @as(f64, @floatFromInt(time_diff));

        if (speed_mps > config.max_speed_mps) {
            return false;
        }
    }

    return true;
}

test "trip validation - too few points" {
    const allocator = std.testing.allocator;

    const points = [_]trip_types.GpsPoint{
        .{ .location = .{ .lat = 45.0, .lon = 126.0 }, .timestamp = 1000 },
        .{ .location = .{ .lat = 45.001, .lon = 126.001 }, .timestamp = 1010 },
    };

    const trip = trip_types.Trip{
        .trip_id = 1,
        .points = &points,
        .allocator = allocator,
    };

    const config = CleaningConfig{
        .min_points = 5,
        .bounding_box = .{
            .lat_min = 44.0,
            .lat_max = 46.0,
            .lon_min = 125.0,
            .lon_max = 127.0,
        },
    };

    try std.testing.expect(!try isValidTrip(trip, config));
}

test "trip validation - excessive speed" {
    const allocator = std.testing.allocator;

    // Two points 1km apart in 1 second = 1000 m/s (way too fast)
    const points = [_]trip_types.GpsPoint{
        .{ .location = .{ .lat = 45.0, .lon = 126.0 }, .timestamp = 1000 },
        .{ .location = .{ .lat = 45.01, .lon = 126.0 }, .timestamp = 1001 },
        .{ .location = .{ .lat = 45.02, .lon = 126.0 }, .timestamp = 1002 },
        .{ .location = .{ .lat = 45.03, .lon = 126.0 }, .timestamp = 1003 },
        .{ .location = .{ .lat = 45.04, .lon = 126.0 }, .timestamp = 1004 },
    };

    const trip = trip_types.Trip{
        .trip_id = 1,
        .points = &points,
        .allocator = allocator,
    };

    const config = CleaningConfig{
        .max_speed_mps = 41.67,
        .min_points = 5,
        .bounding_box = .{
            .lat_min = 44.0,
            .lat_max = 46.0,
            .lon_min = 125.0,
            .lon_max = 127.0,
        },
    };

    try std.testing.expect(!try isValidTrip(trip, config));
}

test "trip validation - valid trip" {
    const allocator = std.testing.allocator;

    // Valid trip with reasonable speeds
    const points = [_]trip_types.GpsPoint{
        .{ .location = .{ .lat = 45.0, .lon = 126.0 }, .timestamp = 1000 },
        .{ .location = .{ .lat = 45.001, .lon = 126.0 }, .timestamp = 1010 },
        .{ .location = .{ .lat = 45.002, .lon = 126.0 }, .timestamp = 1020 },
        .{ .location = .{ .lat = 45.003, .lon = 126.0 }, .timestamp = 1030 },
        .{ .location = .{ .lat = 45.004, .lon = 126.0 }, .timestamp = 1040 },
    };

    const trip = trip_types.Trip{
        .trip_id = 1,
        .points = &points,
        .allocator = allocator,
    };

    const config = CleaningConfig{
        .max_speed_mps = 41.67,
        .min_points = 5,
        .bounding_box = .{
            .lat_min = 44.0,
            .lat_max = 46.0,
            .lon_min = 125.0,
            .lon_max = 127.0,
        },
    };

    try std.testing.expect(try isValidTrip(trip, config));
}
