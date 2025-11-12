const std = @import("std");
const trip_types = @import("../types/trip.zig");

pub const GpsPoint = struct {
    trip_id: u32,
    device_id: u32,
    latitude: f64,
    longitude: f64,
    timestamp: f64,
    speed: f32,
};

pub const TripData = struct {
    points: std.ArrayList(GpsPoint),
    allocator: std.mem.Allocator,

    pub fn init(allocator: std.mem.Allocator) TripData {
        return .{
            .points = std.ArrayList(GpsPoint){},
            .allocator = allocator,
        };
    }

    pub fn deinit(self: *TripData) void {
        self.points.deinit(self.allocator);
    }

    /// Group points by trip_id into separate Trip objects
    pub fn groupByTrip(self: *const TripData) !std.AutoHashMap(u32, std.ArrayList(GpsPoint)) {
        var trips = std.AutoHashMap(u32, std.ArrayList(GpsPoint)).init(self.allocator);
        errdefer {
            var iter = trips.valueIterator();
            while (iter.next()) |list| {
                list.deinit(self.allocator);
            }
            trips.deinit();
        }

        for (self.points.items) |point| {
            const entry = try trips.getOrPut(point.trip_id);
            if (!entry.found_existing) {
                entry.value_ptr.* = std.ArrayList(GpsPoint){};
            }
            try entry.value_ptr.append(self.allocator, point);
        }

        return trips;
    }

    /// Convert to Trip objects used by the map matching pipeline
    pub fn toTrips(self: *const TripData) ![]trip_types.Trip {
        var grouped = try self.groupByTrip();
        defer {
            var iter = grouped.valueIterator();
            while (iter.next()) |list| {
                list.deinit(self.allocator);
            }
            grouped.deinit();
        }

        var result = std.ArrayList(trip_types.Trip){};
        errdefer {
            for (result.items) |*trip| {
                trip.deinit();
            }
            result.deinit(self.allocator);
        }

        var trip_iter = grouped.iterator();
        while (trip_iter.next()) |entry| {
            const trip_id = entry.key_ptr.*;
            const gps_points = entry.value_ptr.items;

            // Convert GpsPoint array to trip_types.GpsPoint array
            var trip_points = try std.ArrayList(trip_types.GpsPoint).initCapacity(self.allocator, gps_points.len);
            errdefer trip_points.deinit(self.allocator);

            for (gps_points) |gp| {
                try trip_points.append(self.allocator, .{
                    .location = .{
                        .lat = gp.latitude,
                        .lon = gp.longitude,
                    },
                    .timestamp = @intFromFloat(gp.timestamp),
                });
            }

            const trip = trip_types.Trip{
                .trip_id = trip_id,
                .points = try trip_points.toOwnedSlice(self.allocator),
                .allocator = self.allocator,
            };

            try result.append(self.allocator, trip);
        }

        return try result.toOwnedSlice(self.allocator);
    }
};

/// Parse a single CSV file containing GPS trip data
/// Expected format: trip_id,devid,latitude,longitude,timestamp,speed
pub fn parseTripCsv(allocator: std.mem.Allocator, file_path: []const u8) !TripData {
    const file = try std.fs.cwd().openFile(file_path, .{});
    defer file.close();

    var trip_data = TripData.init(allocator);
    errdefer trip_data.deinit();

    // Buffer for file reading
    var read_buffer: [8192]u8 = undefined;
    var file_reader = file.reader(&read_buffer);
    const reader = &file_reader.interface;

    var line_num: usize = 0;

    // Skip header line
    _ = reader.takeDelimiterExclusive('\n') catch |err| switch (err) {
        error.EndOfStream => return trip_data,
        else => return err,
    };
    line_num += 1;

    // Parse data lines
    while (true) {
        const line = reader.takeDelimiterExclusive('\n') catch |err| switch (err) {
            error.EndOfStream => break,
            else => return err,
        };

        line_num += 1;

        // Skip empty lines
        if (line.len == 0) continue;

        // Remove trailing \r if present (Windows line endings)
        const trimmed_line = if (line.len > 0 and line[line.len - 1] == '\r')
            line[0 .. line.len - 1]
        else
            line;

        if (trimmed_line.len == 0) continue;

        const point = parseGpsPointLine(trimmed_line) catch |err| {
            std.debug.print("Warning: Failed to parse line {}: {}\n", .{ line_num, err });
            continue;
        };

        try trip_data.points.append(allocator, point);
    }

    return trip_data;
}

/// Parse a single line of CSV into a GpsPoint
/// Format: trip_id,devid,latitude,longitude,timestamp,speed
fn parseGpsPointLine(line: []const u8) !GpsPoint {
    var iter = std.mem.tokenizeScalar(u8, line, ',');

    const trip_id_str = iter.next() orelse return error.MissingTripId;
    const device_id_str = iter.next() orelse return error.MissingDeviceId;
    const lat_str = iter.next() orelse return error.MissingLatitude;
    const lon_str = iter.next() orelse return error.MissingLongitude;
    const timestamp_str = iter.next() orelse return error.MissingTimestamp;
    const speed_str = iter.next() orelse return error.MissingSpeed;

    return GpsPoint{
        .trip_id = try std.fmt.parseInt(u32, trip_id_str, 10),
        .device_id = try std.fmt.parseInt(u32, device_id_str, 10),
        .latitude = try std.fmt.parseFloat(f64, lat_str),
        .longitude = try std.fmt.parseFloat(f64, lon_str),
        .timestamp = try std.fmt.parseFloat(f64, timestamp_str),
        .speed = try std.fmt.parseFloat(f32, speed_str),
    };
}

/// Parse multiple CSV files from a directory
pub fn parseTripCsvDirectory(allocator: std.mem.Allocator, dir_path: []const u8) !TripData {
    var combined_data = TripData.init(allocator);
    errdefer combined_data.deinit();

    var dir = try std.fs.cwd().openDir(dir_path, .{ .iterate = true });
    defer dir.close();

    var iter = dir.iterate();
    var file_count: usize = 0;

    while (try iter.next()) |entry| {
        // Only process CSV files starting with "trips_"
        if (entry.kind != .file) continue;
        if (!std.mem.endsWith(u8, entry.name, ".csv")) continue;
        if (!std.mem.startsWith(u8, entry.name, "trips_")) continue;

        const file_path = try std.fs.path.join(allocator, &[_][]const u8{ dir_path, entry.name });
        defer allocator.free(file_path);

        std.debug.print("  Loading {s}...\n", .{entry.name});

        var file_data = try parseTripCsv(allocator, file_path);
        defer file_data.deinit();

        // Append all points from this file
        try combined_data.points.appendSlice(allocator, file_data.points.items);
        file_count += 1;

        std.debug.print("    + {} points (total: {})\n", .{ file_data.points.items.len, combined_data.points.items.len });
    }

    if (file_count == 0) {
        std.debug.print("  Warning: No trip CSV files found in {s}\n", .{dir_path});
    }

    return combined_data;
}

test "parse single GPS point line" {
    const line = "1,100301526,45.745636,126.68968999999998,1420243200.0,227";
    const point = try parseGpsPointLine(line);

    try std.testing.expectEqual(@as(u32, 1), point.trip_id);
    try std.testing.expectEqual(@as(u32, 100301526), point.device_id);
    try std.testing.expectApproxEqAbs(@as(f64, 45.745636), point.latitude, 0.000001);
    try std.testing.expectApproxEqAbs(@as(f64, 126.689690), point.longitude, 0.000001);
    try std.testing.expectApproxEqAbs(@as(f64, 1420243200.0), point.timestamp, 0.1);
    try std.testing.expectApproxEqAbs(@as(f32, 227.0), point.speed, 0.1);
}

test "parse GPS point line - invalid format" {
    const line = "1,100301526,45.745636";
    const result = parseGpsPointLine(line);
    try std.testing.expectError(error.MissingLongitude, result);
}

test "group points by trip" {
    const allocator = std.testing.allocator;

    var trip_data = TripData.init(allocator);
    defer trip_data.deinit();

    // Add points from two different trips
    try trip_data.points.append(.{
        .trip_id = 1,
        .device_id = 100,
        .latitude = 45.7,
        .longitude = 126.6,
        .timestamp = 1000.0,
        .speed = 50.0,
    });

    try trip_data.points.append(.{
        .trip_id = 1,
        .device_id = 100,
        .latitude = 45.71,
        .longitude = 126.61,
        .timestamp = 1030.0,
        .speed = 55.0,
    });

    try trip_data.points.append(.{
        .trip_id = 2,
        .device_id = 101,
        .latitude = 45.8,
        .longitude = 126.7,
        .timestamp = 2000.0,
        .speed = 60.0,
    });

    var grouped = try trip_data.groupByTrip();
    defer {
        var iter = grouped.valueIterator();
        while (iter.next()) |list| {
            list.deinit();
        }
        grouped.deinit();
    }

    try std.testing.expectEqual(@as(usize, 2), grouped.count());
    try std.testing.expectEqual(@as(usize, 2), grouped.get(1).?.items.len);
    try std.testing.expectEqual(@as(usize, 1), grouped.get(2).?.items.len);
}
