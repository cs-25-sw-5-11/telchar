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

pub const InvalidationReason = enum {
    too_few_points,
    outside_bounding_box,
    time_gap_too_large,
    excessive_speed,
};

pub const CleaningResult = struct {
    valid_trips: []const trip_types.Trip, // Owned
    invalid_count: usize,
    allocator: std.mem.Allocator,

    // Diagnostic statistics
    rejection_stats: struct {
        too_few_points: usize = 0,
        outside_bounding_box: usize = 0,
        time_gap_too_large: usize = 0,
        excessive_speed: usize = 0,
    } = .{},

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
    var too_few_points: usize = 0;
    var outside_bounding_box: usize = 0;
    var time_gap_too_large: usize = 0;
    var excessive_speed: usize = 0;

    for (raw_trips) |*trip| {
        // First, try to clean and split the trip
        const cleaned_subtrips = try cleanAndSplitTrip(allocator, trip.*, config) orelse {
            // Trip completely failed cleaning - track why and free it
            const validation_result = try validateTrip(trip.*, config);
            if (validation_result) |reason| {
                switch (reason) {
                    .too_few_points => too_few_points += 1,
                    .outside_bounding_box => outside_bounding_box += 1,
                    .time_gap_too_large => time_gap_too_large += 1,
                    .excessive_speed => excessive_speed += 1,
                }
            }
            var mutable_trip = trip.*;
            mutable_trip.deinit();
            invalid_count += 1;
            continue;
        };

        defer allocator.free(cleaned_subtrips);

        // Add all valid subtrips
        for (cleaned_subtrips) |subtrip| {
            try valid_trips.append(allocator, subtrip);
        }
    }

    return CleaningResult{
        .valid_trips = try valid_trips.toOwnedSlice(allocator),
        .invalid_count = invalid_count,
        .rejection_stats = .{
            .too_few_points = too_few_points,
            .outside_bounding_box = outside_bounding_box,
            .time_gap_too_large = time_gap_too_large,
            .excessive_speed = excessive_speed,
        },
        .allocator = allocator,
    };
}

/// Clean and split a trip into valid subtrips
/// Splits at time gaps and filters out bad points (excessive speed, outside bbox)
/// Returns null if no valid subtrips can be created
fn cleanAndSplitTrip(
    allocator: std.mem.Allocator,
    trip: trip_types.Trip,
    config: CleaningConfig,
) !?[]trip_types.Trip {
    if (trip.points.len < config.min_points) {
        return null;
    }

    var subtrips = std.ArrayList(trip_types.Trip){};
    errdefer {
        for (subtrips.items) |*subtrip| {
            var mut_subtrip = subtrip.*;
            mut_subtrip.deinit();
        }
        subtrips.deinit(allocator);
    }

    var current_points = std.ArrayList(trip_types.GpsPoint){};
    defer current_points.deinit(allocator);

    var next_trip_id = trip.trip_id;

    for (trip.points) |point| {
        // Check if point is within bounding box
        if (!config.bounding_box.contains(point.location)) {
            // Skip this point - it's outside the area of interest
            continue;
        }

        // If we have a previous point, check time gap and speed
        if (current_points.items.len > 0) {
            const prev_point = current_points.items[current_points.items.len - 1];
            const time_diff = point.timestamp - prev_point.timestamp;

            // Check for invalid time difference
            if (time_diff <= 0) {
                continue; // Skip points with non-positive time diff
            }

            // Check if time gap is too large - split here
            if (time_diff > config.max_time_gap_sec) {
                // Save current subtrip if it has enough points
                if (current_points.items.len >= config.min_points) {
                    const points_owned = try current_points.toOwnedSlice(allocator);
                    try subtrips.append(allocator, trip_types.Trip{
                        .trip_id = next_trip_id,
                        .points = points_owned,
                        .allocator = allocator,
                    });
                    next_trip_id += 1;
                } else {
                    // Not enough points, clear and start over
                    current_points.clearRetainingCapacity();
                }
                // Start new subtrip with current point
                try current_points.append(allocator, point);
                continue;
            }

            // Check speed
            const distance = haversine.distance(prev_point.location, point.location);
            const speed_mps = distance / @as(f64, @floatFromInt(time_diff));

            if (speed_mps > config.max_speed_mps) {
                // Skip this point - excessive speed indicates GPS error
                continue;
            }
        }

        // Add valid point to current subtrip
        try current_points.append(allocator, point);
    }

    // Save final subtrip
    if (current_points.items.len >= config.min_points) {
        const points_owned = try current_points.toOwnedSlice(allocator);
        try subtrips.append(allocator, trip_types.Trip{
            .trip_id = next_trip_id,
            .points = points_owned,
            .allocator = allocator,
        });
    }

    if (subtrips.items.len == 0) {
        return null;
    }

    return try subtrips.toOwnedSlice(allocator);
}

/// Validate a trip and return rejection reason (null if valid)
fn validateTrip(trip: trip_types.Trip, config: CleaningConfig) !?InvalidationReason {
    // Check minimum points
    if (trip.points.len < config.min_points) {
        return .too_few_points;
    }

    // Check all points within bounding box
    for (trip.points) |point| {
        if (!config.bounding_box.contains(point.location)) {
            return .outside_bounding_box;
        }
    }

    // Check for time gaps and excessive speeds
    for (trip.points[0 .. trip.points.len - 1], trip.points[1..]) |p1, p2| {
        const time_diff = p2.timestamp - p1.timestamp;

        // Check time gap
        if (time_diff > config.max_time_gap_sec or time_diff <= 0) {
            return .time_gap_too_large;
        }

        // Check speed
        const distance = haversine.distance(p1.location, p2.location);
        const speed_mps = distance / @as(f64, @floatFromInt(time_diff));

        if (speed_mps > config.max_speed_mps) {
            return .excessive_speed;
        }
    }

    return null; // Valid
}

/// Check if a trip passes validation criteria (kept for backward compatibility)
fn isValidTrip(trip: trip_types.Trip, config: CleaningConfig) !bool {
    return (try validateTrip(trip, config)) == null;
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
