const std = @import("std");
const stats_types = @import("../types/statistics.zig");
const trip_types = @import("../types/trip.zig");
const variance = @import("variance.zig");

/// Extract traversals from matched trips
/// Note: This is a simplified version that extracts edge traversals from the path
/// For accurate speed calculations, we need the original GPS trip data with timestamps
pub fn extractTraversals(
    allocator: std.mem.Allocator,
    matched_trips: []const trip_types.MatchedTrip,
    time_interval_sec: u16,
) ![]stats_types.Traversal {
    var traversals = std.ArrayList(stats_types.Traversal){};
    defer traversals.deinit(allocator);

    const seconds_per_day: u32 = 86400;
    const time_bins_per_day: u16 = @intCast(seconds_per_day / time_interval_sec);

    _ = time_bins_per_day; // Will be used when we have timestamps

    for (matched_trips) |matched_trip| {
        // Extract traversals from consecutive projections
        const projections = matched_trip.projections;
        const original_trip = matched_trip.original_trip;

        if (projections.len < 2) continue; // Need at least 2 points for speed

        var i: usize = 0;
        while (i < projections.len - 1) : (i += 1) {
            const proj1 = projections[i];
            const proj2 = projections[i + 1];

            // Skip if not consecutive on same edge
            if (proj1.edge_id != proj2.edge_id) continue;

            // Get timestamps from original GPS data
            const gps1 = original_trip.points[proj1.gps_index];
            const gps2 = original_trip.points[proj2.gps_index];

            // Calculate time difference and distance
            const time_diff = gps2.timestamp - gps1.timestamp;
            if (time_diff <= 0) continue; // Skip invalid time differences

            const distance_m = proj2.distance_from_start - proj1.distance_from_start;
            if (distance_m <= 0) continue; // Skip invalid distances

            // Calculate speed
            const speed_mps = distance_m / @as(f64, @floatFromInt(time_diff));

            // Calculate time bin (based on start time)
            const seconds_in_day = @mod(gps1.timestamp, seconds_per_day);
            const time_index: u16 = @intCast(@divFloor(seconds_in_day, time_interval_sec));

            try traversals.append(allocator, .{
                .edge_id = proj1.edge_id,
                .time_index = time_index,
                .speed_mps = speed_mps,
            });
        }
    }

    return try traversals.toOwnedSlice(allocator);
}

/// Aggregate traversals into network statistics
pub fn aggregateNetworkStats(
    allocator: std.mem.Allocator,
    matched_trips: []const trip_types.MatchedTrip,
    num_edges: u32,
    time_interval_sec: u16,
) !stats_types.NetworkStats {
    // Extract traversals from matched trips
    const traversals = try extractTraversals(allocator, matched_trips, time_interval_sec);
    defer allocator.free(traversals);

    // Calculate time bins per day
    const seconds_per_day: u32 = 86400;
    const time_bins_per_day: u16 = @intCast(seconds_per_day / time_interval_sec);

    // Use variance module to aggregate
    return try variance.aggregateTraversals(
        allocator,
        traversals,
        num_edges,
        time_bins_per_day,
    );
}

/// Write network statistics to JSON
/// Format: { "edges": [ { "edge_id": 1, "time_bins": [ { "time_index": 0, "mean_kmh": 50.0, "std_dev_kmh": 10.0, "count": 100 }, ... ] }, ... ] }
pub fn writeStatsToJson(
    allocator: std.mem.Allocator,
    network_stats: stats_types.NetworkStats,
    output_path: []const u8,
) !void {
    // Build JSON as string
    var json_str = std.ArrayList(u8){};
    defer json_str.deinit(allocator);

    try json_str.appendSlice(allocator, "{\n  \"edges\": [\n");

    var edge_iter = network_stats.edge_stats.iterator();
    var is_first_edge = true;

    while (edge_iter.next()) |entry| {
        const edge_id = entry.key_ptr.*;
        const stats_array = entry.value_ptr.*;

        // Count non-empty time bins
        var non_empty_count: usize = 0;
        for (stats_array) |stats| {
            if (stats.count > 0) non_empty_count += 1;
        }

        // Skip edges with no data
        if (non_empty_count == 0) continue;

        // Write comma separator between edges
        if (!is_first_edge) {
            try json_str.appendSlice(allocator, ",\n");
        }
        is_first_edge = false;

        // Write edge object
        try json_str.writer(allocator).print("    {{\n      \"edge_id\": {d},\n      \"time_bins\": [\n", .{edge_id});

        var is_first_bin = true;
        for (stats_array, 0..) |stats, time_idx| {
            if (stats.count == 0) continue;

            // Write comma separator between bins
            if (!is_first_bin) {
                try json_str.appendSlice(allocator, ",\n");
            }
            is_first_bin = false;

            // Write time bin statistics
            try json_str.writer(allocator).print("        {{\n" ++
                "          \"time_index\": {d},\n" ++
                "          \"mean_kmh\": {d:.2},\n" ++
                "          \"std_dev_kmh\": {d:.2},\n" ++
                "          \"count\": {d}\n" ++
                "        }}", .{
                time_idx,
                stats.meanKmh(),
                stats.stdDevKmh(),
                stats.count,
            });
        }

        try json_str.appendSlice(allocator, "\n      ]\n    }");
    }

    // Write closing
    try json_str.appendSlice(allocator, "\n  ]\n}\n");

    // Write to file
    try std.fs.cwd().writeFile(.{ .sub_path = output_path, .data = json_str.items });
}

/// Write network statistics to JSON with compact format (for large datasets)
pub fn writeStatsToJsonCompact(
    allocator: std.mem.Allocator,
    network_stats: stats_types.NetworkStats,
    output_path: []const u8,
) !void {
    _ = allocator;
    const file = try std.fs.cwd().createFile(output_path, .{});
    defer file.close();

    const writer = file.writer();

    // Write opening
    try writer.writeAll("{\"edges\":[");

    var edge_iter = network_stats.edge_stats.iterator();
    var is_first_edge = true;

    while (edge_iter.next()) |entry| {
        const edge_id = entry.key_ptr.*;
        const stats_array = entry.value_ptr.*;

        // Count non-empty time bins
        var non_empty_count: usize = 0;
        for (stats_array) |stats| {
            if (stats.count > 0) non_empty_count += 1;
        }

        // Skip edges with no data
        if (non_empty_count == 0) continue;

        // Write comma separator between edges
        if (!is_first_edge) {
            try writer.writeAll(",");
        }
        is_first_edge = false;

        // Write edge object (compact)
        try writer.print("{{\"id\":{},\"bins\":[", .{edge_id});

        var is_first_bin = true;
        for (stats_array, 0..) |stats, time_idx| {
            if (stats.count == 0) continue;

            if (!is_first_bin) {
                try writer.writeAll(",");
            }
            is_first_bin = false;

            // Compact format: [time_index, mean_kmh, std_dev_kmh, count]
            try writer.print("[{},{d:.2},{d:.2},{}]", .{
                time_idx,
                stats.meanKmh(),
                stats.stdDevKmh(),
                stats.count,
            });
        }

        try writer.writeAll("]}");
    }

    // Write closing
    try writer.writeAll("]}\n");
}

test "extract traversals from matched trips" {
    const allocator = std.testing.allocator;

    // Create test matched trip with simple path
    const projections = [_]trip_types.Projection{
        .{
            .gps_index = 0,
            .edge_id = 1,
            .location = .{ .lat = 45.0, .lon = 126.0 },
            .distance_from_start = 0.0,
            .projection_error = 5.0,
        },
        .{
            .gps_index = 1,
            .edge_id = 1,
            .location = .{ .lat = 45.001, .lon = 126.001 },
            .distance_from_start = 100.0,
            .projection_error = 3.0,
        },
        .{
            .gps_index = 2,
            .edge_id = 2,
            .location = .{ .lat = 45.002, .lon = 126.002 },
            .distance_from_start = 0.0,
            .projection_error = 2.0,
        },
    };

    const path = [_]u32{ 1, 2 };

    // Create original trip with GPS points
    const gps_points = [_]trip_types.GpsPoint{
        .{ .location = .{ .lat = 45.0, .lon = 126.0 }, .timestamp = 1000 },
        .{ .location = .{ .lat = 45.001, .lon = 126.001 }, .timestamp = 1010 },
        .{ .location = .{ .lat = 45.002, .lon = 126.002 }, .timestamp = 1020 },
    };

    const original_trip = trip_types.Trip{
        .trip_id = 1,
        .points = &gps_points,
        .allocator = allocator,
    };

    const matched_trip = trip_types.MatchedTrip{
        .trip_id = 1,
        .projections = &projections,
        .path = &path,
        .original_trip = &original_trip,
        .allocator = allocator,
    };

    const matched_trips = [_]trip_types.MatchedTrip{matched_trip};

    const traversals = try extractTraversals(allocator, &matched_trips, 300);
    defer allocator.free(traversals);

    // Should extract at least one traversal from consecutive projections on edge 1
    try std.testing.expect(traversals.len >= 1);

    // Check that we have a traversal for edge 1 (projections 0->1)
    var found_edge_1 = false;
    for (traversals) |trav| {
        if (trav.edge_id == 1) {
            found_edge_1 = true;
            // Verify speed calculation: 100m / 10s = 10 m/s
            try std.testing.expectApproxEqRel(@as(f64, 10.0), trav.speed_mps, 0.01);
        }
    }
    try std.testing.expect(found_edge_1);
}
