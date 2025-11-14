const std = @import("std");
const graph = @import("../types/graph.zig");
const trip_types = @import("../types/trip.zig");
const haversine = @import("../utils/haversine.zig");

/// Write vertex.csv file
/// Format: node_id,longitude,latitude
pub fn writeVertexCsv(
    allocator: std.mem.Allocator,
    network: *const graph.Network,
    output_path: []const u8,
) !void {
    _ = allocator;
    const file = try std.fs.cwd().createFile(output_path, .{});
    defer file.close();

    var write_buffer: [8192]u8 = undefined;
    var file_writer = file.writer(&write_buffer);
    const writer = &file_writer.interface;

    // Write header
    try writer.writeAll("node_id,longitude,latitude\n");

    // Write each vertex
    for (network.vertices, 0..) |vertex, i| {
        try writer.print("{},{d:.7},{d:.7}\n", .{
            i,
            vertex.location.lon,
            vertex.location.lat,
        });
    }
}

/// Write edge_connections.csv file
/// Format: edge_id,vertex_start_id,vertex_end_id
pub fn writeEdgeConnectionsCsv(
    allocator: std.mem.Allocator,
    network: *const graph.Network,
    output_path: []const u8,
) !void {
    _ = allocator;
    const file = try std.fs.cwd().createFile(output_path, .{});
    defer file.close();

    var write_buffer: [8192]u8 = undefined;
    var file_writer = file.writer(&write_buffer);
    const writer = &file_writer.interface;

    // Write header
    try writer.writeAll("edge_id,vertex_start_id,vertex_end_id\n");

    // Write each edge, converting OSM IDs to array indices
    var edge_id: u32 = 0;
    for (network.edges) |edge| {
        const start_idx = network.vertex_index.get(edge.start_vertex_id) orelse continue;
        const end_idx = network.vertex_index.get(edge.end_vertex_id) orelse continue;

        try writer.print("{},{},{}\n", .{
            edge_id,
            start_idx,
            end_idx,
        });
        edge_id += 1;
    }
}

/// Write edge_data.csv file with traversal times
/// Format: timestamp,edge1_traversal_time_seconds,edge2_traversal_time_seconds,...
pub fn writeEdgeDataCsv(
    allocator: std.mem.Allocator,
    network: *const graph.Network,
    matched_trips: []const trip_types.MatchedTrip,
    num_edges: u32,
    time_interval_sec: u16,
    output_path: []const u8,
) !void {
    const file = try std.fs.cwd().createFile(output_path, .{});
    defer file.close();

    var write_buffer: [8192]u8 = undefined;
    var file_writer = file.writer(&write_buffer);
    const writer = &file_writer.interface;

    // Calculate number of time bins per day (288 for 5-minute intervals)
    const seconds_per_day: u32 = 86400;
    const time_bins_per_day: u16 = @intCast(seconds_per_day / time_interval_sec);

    // Pre-calculate edge lengths for speed validation
    var edge_lengths = try allocator.alloc(f64, num_edges);
    defer allocator.free(edge_lengths);

    for (network.edges, 0..) |edge, idx| {
        const start_vertex = network.vertices[network.vertex_index.get(edge.start_vertex_id).?];
        const end_vertex = network.vertices[network.vertex_index.get(edge.end_vertex_id).?];
        edge_lengths[idx] = haversine.distance(start_vertex.location, end_vertex.location);
    }

    // Build a map of (time_bin, edge_id) -> list of traversal times
    var traversal_map = std.AutoHashMap(TimeEdgeKey, std.ArrayList(f64)).init(allocator);
    defer {
        var iter = traversal_map.iterator();
        while (iter.next()) |entry| {
            entry.value_ptr.*.deinit(allocator);
        }
        traversal_map.deinit();
    }

    // First pass: collect all traversal times per edge to calculate statistics
    var edge_all_times = std.AutoHashMap(u32, std.ArrayList(f64)).init(allocator);
    defer {
        var iter = edge_all_times.iterator();
        while (iter.next()) |entry| {
            entry.value_ptr.*.deinit(allocator);
        }
        edge_all_times.deinit();
    }

    // Extract traversal times from matched trips
    // Use the edge path and calculate traversal time for each edge traversal
    for (matched_trips) |matched_trip| {
        const projections = matched_trip.projections;
        const original_trip = matched_trip.original_trip;

        if (projections.len < 2) continue;

        // Find edge transitions in projections
        var i: usize = 0;
        while (i < projections.len) {
            const start_idx = i;
            const edge_id = projections[i].edge_id;

            // Find where this edge ends (next different edge or end of trip)
            var end_idx = i;
            while (end_idx < projections.len and projections[end_idx].edge_id == edge_id) {
                end_idx += 1;
            }

            // We now have projections[start_idx..end_idx-1] all on the same edge
            if (end_idx > start_idx) {
                const first_proj = projections[start_idx];
                const last_proj = projections[end_idx - 1];

                const gps_start = original_trip.points[first_proj.gps_index];
                const gps_end = original_trip.points[last_proj.gps_index];

                const time_diff = gps_end.timestamp - gps_start.timestamp;

                // Only record if we have sufficient time between GPS readings
                // Require at least 10 seconds to avoid GPS sampling noise
                // (mean GPS interval is ~38 seconds)
                if (time_diff >= 10) {
                    const traversal_time_sec = @as(f64, @floatFromInt(time_diff));

                    // Validate implied speed is realistic using pre-calculated edge length
                    const edge_length_m = edge_lengths[edge_id];

                    // Calculate implied speed: (meters / seconds) * 3.6 = km/h
                    const implied_speed_kmh = (edge_length_m / traversal_time_sec) * 3.6;

                    // Only record if speed is realistic (0-150 km/h)
                    if (implied_speed_kmh >= 0 and implied_speed_kmh <= 150.0) {
                        // Store for first pass to calculate per-edge statistics
                        const edge_entry = try edge_all_times.getOrPut(edge_id);
                        if (!edge_entry.found_existing) {
                            edge_entry.value_ptr.* = std.ArrayList(f64){};
                        }
                        try edge_entry.value_ptr.append(allocator, traversal_time_sec);

                        // Calculate time bin from the start time
                        const seconds_in_day = @mod(gps_start.timestamp, seconds_per_day);
                        const time_index: u16 = @intCast(@divFloor(seconds_in_day, time_interval_sec));

                        const key = TimeEdgeKey{
                            .time_bin = time_index,
                            .edge_id = edge_id,
                        };

                        const entry = try traversal_map.getOrPut(key);
                        if (!entry.found_existing) {
                            entry.value_ptr.* = std.ArrayList(f64){};
                        }
                        try entry.value_ptr.append(allocator, traversal_time_sec);
                    }
                }
            }

            i = end_idx;
            if (i == projections.len - 1) i += 1; // Move past last projection
        }
    }

    // Calculate outlier thresholds for each edge (median-based filtering)
    var edge_max_allowed = std.AutoHashMap(u32, f64).init(allocator);
    defer edge_max_allowed.deinit();

    var edge_iter = edge_all_times.iterator();
    while (edge_iter.next()) |entry| {
        const edge_id_val = entry.key_ptr.*;
        const times = entry.value_ptr.items;

        if (times.len >= 5) {  // Need enough samples to calculate median
            // Sort to find median
            const sorted_times = try allocator.dupe(f64, times);
            defer allocator.free(sorted_times);
            std.mem.sort(f64, sorted_times, {}, comptime std.sort.asc(f64));

            const median = sorted_times[sorted_times.len / 2];

            // Outlier threshold: 2x median speed (speeds are inversely proportional to time)
            // If median time is T, then max allowed time corresponds to speed > median_speed/2
            // So min allowed time = median_time / 2 (to prevent speeds > 2x median)
            const edge_length_m = edge_lengths[edge_id_val];
            const median_speed_kmh = (edge_length_m / median) * 3.6;
            const max_allowed_speed_kmh = median_speed_kmh * 2.0;  // Allow 2x median speed

            // Convert back to minimum allowed time
            const min_allowed_time = edge_length_m / (max_allowed_speed_kmh / 3.6);

            try edge_max_allowed.put(edge_id_val, min_allowed_time);
        }
    }

    // Filter outliers from traversal_map
    var total_filtered: usize = 0;
    var traversal_iter = traversal_map.iterator();
    while (traversal_iter.next()) |entry| {
        const edge_id_val = entry.key_ptr.edge_id;
        const times_list = entry.value_ptr;  // Get pointer, not copy

        if (edge_max_allowed.get(edge_id_val)) |min_time| {
            const original_len = times_list.items.len;
            // Remove times that are too short (implying too-high speeds)
            var filtered_idx: usize = 0;
            for (times_list.items) |time| {
                if (time >= min_time) {
                    times_list.items[filtered_idx] = time;
                    filtered_idx += 1;
                }
            }
            times_list.items.len = filtered_idx;
            total_filtered += (original_len - filtered_idx);
        }
    }

    std.debug.print("  Outlier filter removed {} observations (2x median speed threshold)\n", .{total_filtered});

    // Write header: timestamp,edge0_traversal_time_seconds,edge1_traversal_time_seconds,...
    try writer.writeAll("timestamp");
    var edge_id: u32 = 0;
    while (edge_id < num_edges) : (edge_id += 1) {
        try writer.print(",edge{}_traversal_time_seconds", .{edge_id});
    }
    try writer.writeAll("\n");

    // Write each time bin
    var time_bin: u16 = 0;
    while (time_bin < time_bins_per_day) : (time_bin += 1) {
        // Convert time bin to HH:MM format
        const seconds_in_day: u32 = @as(u32, time_bin) * @as(u32, time_interval_sec);
        const hour = seconds_in_day / 3600;
        const minute = (seconds_in_day % 3600) / 60;
        try writer.print("{d:0>2}:{d:0>2}", .{ hour, minute });

        // Write traversal time for each edge
        edge_id = 0;
        while (edge_id < num_edges) : (edge_id += 1) {
            const key = TimeEdgeKey{
                .time_bin = time_bin,
                .edge_id = edge_id,
            };

            if (traversal_map.get(key)) |times| {
                // Calculate median traversal time
                if (times.items.len > 0) {
                    const median = calculateMedian(times.items);
                    try writer.print(",{d:.1}", .{median});
                } else {
                    try writer.writeAll(",-1");
                }
            } else {
                // No data for this edge at this time
                try writer.writeAll(",-1");
            }
        }

        try writer.writeAll("\n");
    }
}

/// Key for traversal map: (time_bin, edge_id)
const TimeEdgeKey = struct {
    time_bin: u16,
    edge_id: u32,

    pub fn hash(self: TimeEdgeKey) u64 {
        return @as(u64, self.time_bin) << 32 | @as(u64, self.edge_id);
    }

    pub fn eql(self: TimeEdgeKey, other: TimeEdgeKey) bool {
        return self.time_bin == other.time_bin and self.edge_id == other.edge_id;
    }
};

/// Write edge_data_speed.csv file with speeds in km/h
/// Format: timestamp,edge1_speed_kmh,edge2_speed_kmh,...
pub fn writeEdgeSpeedCsv(
    allocator: std.mem.Allocator,
    matched_trips: []const trip_types.MatchedTrip,
    num_edges: u32,
    time_interval_sec: u16,
    output_path: []const u8,
) !void {
    const file = try std.fs.cwd().createFile(output_path, .{});
    defer file.close();

    var write_buffer: [8192]u8 = undefined;
    var file_writer = file.writer(&write_buffer);
    const writer = &file_writer.interface;

    // Calculate number of time bins per day (288 for 5-minute intervals)
    const seconds_per_day: u32 = 86400;
    const time_bins_per_day: u16 = @intCast(seconds_per_day / time_interval_sec);

    // Build a map of (time_bin, edge_id) -> list of speeds (km/h)
    var speed_map = std.AutoHashMap(TimeEdgeKey, std.ArrayList(f64)).init(allocator);
    defer {
        var iter = speed_map.iterator();
        while (iter.next()) |entry| {
            entry.value_ptr.deinit(allocator);
        }
        speed_map.deinit();
    }

    // Extract speeds from matched trips
    for (matched_trips) |matched_trip| {
        const projections = matched_trip.projections;
        const original_trip = matched_trip.original_trip;

        if (projections.len < 2) continue;

        // Find edge transitions in projections
        var i: usize = 0;
        while (i < projections.len) {
            const start_idx = i;
            const edge_id = projections[i].edge_id;

            // Find where this edge ends
            var end_idx = i;
            while (end_idx < projections.len and projections[end_idx].edge_id == edge_id) {
                end_idx += 1;
            }

            // Calculate speed for this edge traversal
            if (end_idx > start_idx) {
                const first_proj = projections[start_idx];
                const last_proj = projections[end_idx - 1];

                const gps_start = original_trip.points[first_proj.gps_index];
                const gps_end = original_trip.points[last_proj.gps_index];

                const time_diff = gps_end.timestamp - gps_start.timestamp;

                // Only record if we have positive time (match edge_data.csv logic exactly)
                if (time_diff > 0) {
                    const distance_traveled_m = last_proj.distance_from_start - first_proj.distance_from_start;

                    // Convert to km/h: (meters / seconds) * 3.6
                    const speed_kmh = (distance_traveled_m / @as(f64, @floatFromInt(time_diff))) * 3.6;

                    // Calculate time bin from the start time
                    const seconds_in_day = @mod(gps_start.timestamp, seconds_per_day);
                    const time_index: u16 = @intCast(@divFloor(seconds_in_day, time_interval_sec));

                    const key = TimeEdgeKey{
                        .time_bin = time_index,
                        .edge_id = edge_id,
                    };

                    const entry = try speed_map.getOrPut(key);
                    if (!entry.found_existing) {
                        entry.value_ptr.* = std.ArrayList(f64){};
                    }
                    try entry.value_ptr.append(allocator, speed_kmh);
                }
            }

            i = end_idx;
            if (i == projections.len - 1) i += 1;
        }
    }

    // Write header
    try writer.writeAll("timestamp");
    var edge_id: u32 = 0;
    while (edge_id < num_edges) : (edge_id += 1) {
        try writer.print(",edge{}_speed_kmh", .{edge_id});
    }
    try writer.writeAll("\n");

    // Write each time bin
    var time_bin: u16 = 0;
    while (time_bin < time_bins_per_day) : (time_bin += 1) {
        // Convert time bin to HH:MM format
        const seconds_in_day: u32 = @as(u32, time_bin) * @as(u32, time_interval_sec);
        const hour = seconds_in_day / 3600;
        const minute = (seconds_in_day % 3600) / 60;
        try writer.print("{d:0>2}:{d:0>2}", .{ hour, minute });

        // Write speed for each edge
        edge_id = 0;
        while (edge_id < num_edges) : (edge_id += 1) {
            const key = TimeEdgeKey{
                .time_bin = time_bin,
                .edge_id = edge_id,
            };

            if (speed_map.get(key)) |speeds| {
                // Calculate median speed
                if (speeds.items.len > 0) {
                    const median = calculateMedian(speeds.items);
                    try writer.print(",{d:.1}", .{median});
                } else {
                    try writer.writeAll(",-1");
                }
            } else {
                // No data for this edge at this time
                try writer.writeAll(",-1");
            }
        }

        try writer.writeAll("\n");
    }
}

/// Calculate median of an array of values
fn calculateMedian(values: []f64) f64 {
    if (values.len == 0) return 0.0;
    if (values.len == 1) return values[0];

    // Create a copy to sort
    const sorted = std.heap.page_allocator.dupe(f64, values) catch return values[0];
    defer std.heap.page_allocator.free(sorted);

    std.mem.sort(f64, sorted, {}, comptime std.sort.asc(f64));

    const mid = sorted.len / 2;
    if (sorted.len % 2 == 0) {
        return (sorted[mid - 1] + sorted[mid]) / 2.0;
    } else {
        return sorted[mid];
    }
}

/// Write all three CSV files
pub fn writeAllCsvFiles(
    allocator: std.mem.Allocator,
    network: *const graph.Network,
    matched_trips: []const trip_types.MatchedTrip,
    time_interval_sec: u16,
    output_dir: []const u8,
) !void {
    std.debug.print("Writing CSV output files to {s}/...\n", .{output_dir});

    // Ensure output directory exists
    std.fs.cwd().makeDir(output_dir) catch |err| {
        if (err != error.PathAlreadyExists) return err;
    };

    // Write vertex.csv
    const vertex_path = try std.fs.path.join(allocator, &[_][]const u8{ output_dir, "vertex.csv" });
    defer allocator.free(vertex_path);
    try writeVertexCsv(allocator, network, vertex_path);
    std.debug.print("  ✓ vertex.csv ({} vertices)\n", .{network.vertices.len});

    // Write edge_connections.csv
    const edge_conn_path = try std.fs.path.join(allocator, &[_][]const u8{ output_dir, "edge_connections.csv" });
    defer allocator.free(edge_conn_path);
    try writeEdgeConnectionsCsv(allocator, network, edge_conn_path);
    std.debug.print("  ✓ edge_connections.csv ({} edges)\n", .{network.edges.len});

    // Write edge_data.csv
    const edge_data_path = try std.fs.path.join(allocator, &[_][]const u8{ output_dir, "edge_data.csv" });
    defer allocator.free(edge_data_path);
    try writeEdgeDataCsv(allocator, network, matched_trips, @intCast(network.edges.len), time_interval_sec, edge_data_path);
    std.debug.print("  ✓ edge_data.csv (traversal times by time bin)\n", .{});

    // Write edge_data_speed.csv
    const edge_speed_path = try std.fs.path.join(allocator, &[_][]const u8{ output_dir, "edge_data_speed.csv" });
    defer allocator.free(edge_speed_path);
    try writeEdgeSpeedCsv(allocator, matched_trips, @intCast(network.edges.len), time_interval_sec, edge_speed_path);
    std.debug.print("  ✓ edge_data_speed.csv (speeds in km/h by time bin)\n", .{});
}
