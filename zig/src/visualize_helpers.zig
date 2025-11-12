const std = @import("std");

pub const TraversalData = struct {
    times: [][]f32,
    num_time_bins: u32,
    num_edges: u32,
    allocator: std.mem.Allocator,

    pub fn deinit(self: *@This()) void {
        for (self.times) |time_bin| {
            self.allocator.free(time_bin);
        }
        self.allocator.free(self.times);
    }
};

pub const TimeBinStats = struct {
    min_time: f32,
    max_time: f32,
};

pub fn loadTraversalData(allocator: std.mem.Allocator, output_dir: []const u8, num_edges: u32) !TraversalData {
    const path = try std.fs.path.join(allocator, &[_][]const u8{ output_dir, "edge_data.csv" });
    defer allocator.free(path);

    const file = try std.fs.cwd().openFile(path, .{});
    defer file.close();

    // Read entire file into memory
    const file_size = (try file.stat()).size;
    const contents = try allocator.alloc(u8, file_size);
    defer allocator.free(contents);
    _ = try file.readAll(contents);

    // Parse line by line
    var lines_iter = std.mem.splitScalar(u8, contents, '\n');

    // Skip header
    _ = lines_iter.next() orelse return error.InvalidFormat;

    // Read all time bins
    var time_bins = std.ArrayList([]f32){};
    errdefer {
        for (time_bins.items) |bin| allocator.free(bin);
        time_bins.deinit(allocator);
    }

    var time_bin_count: u32 = 0;
    while (lines_iter.next()) |line| {
        if (line.len == 0) continue; // Skip empty lines
        time_bin_count += 1;
        if (time_bin_count <= 3) {
            std.debug.print("  Parsing line {}, length: {} bytes\n", .{ time_bin_count, line.len });
        }

        var line_iter = std.mem.splitScalar(u8, line, ',');
        _ = line_iter.next(); // Skip timestamp

        var times_for_bin = try allocator.alloc(f32, num_edges);
        errdefer allocator.free(times_for_bin);
        @memset(times_for_bin, -1.0);

        var edge_idx: u32 = 0;
        var parsed_count: u32 = 0;
        while (line_iter.next()) |val_str| : (edge_idx += 1) {
            if (edge_idx >= num_edges) break;

            const time = std.fmt.parseFloat(f32, val_str) catch -1.0;
            times_for_bin[edge_idx] = time;
            parsed_count += 1;
        }

        if (time_bin_count <= 2) {
            std.debug.print("  Parsed {} edge values\n", .{parsed_count});
        }

        try time_bins.append(allocator, times_for_bin);
    }

    std.debug.print("  Total time bins collected: {}\n", .{time_bins.items.len});

    const num_time_bins = time_bins.items.len;
    const owned_times = try time_bins.toOwnedSlice(allocator);

    return .{
        .times = owned_times,
        .num_time_bins = @intCast(num_time_bins),
        .num_edges = num_edges,
        .allocator = allocator,
    };
}

/// Calculate min/max for a specific time bin (ignoring -1 values)
pub fn getTimeBinStats(time_data: []const f32) TimeBinStats {
    var min_time: f32 = std.math.inf(f32);
    var max_time: f32 = -std.math.inf(f32);

    for (time_data) |time| {
        if (time >= 0) {
            min_time = @min(min_time, time);
            max_time = @max(max_time, time);
        }
    }

    // Handle case where no valid data
    if (std.math.isInf(min_time)) {
        min_time = 0;
        max_time = 60;
    }

    // Ensure min != max for color scaling
    if (min_time == max_time) {
        max_time = min_time + 1.0;
    }

    return .{
        .min_time = min_time,
        .max_time = max_time,
    };
}

pub fn getColorForTime(time: f32, min_time: f32, max_time: f32) struct { r: u8, g: u8, b: u8 } {
    // Grey for missing data
    if (time < 0) return .{ .r = 100, .g = 100, .b = 100 };

    // Apply logarithmic scaling for better visualization of clustered data
    // Add small offset to avoid log(0)
    const log_min = @log(min_time + 1.0);
    const log_max = @log(max_time + 1.0);
    const log_time = @log(time + 1.0);

    const log_range = log_max - log_min;
    const normalized = if (log_range > 0)
        @min(1.0, @max(0.0, (log_time - log_min) / log_range))
    else
        0.5;

    // Use perceptually better color scheme: Blue -> Cyan -> Yellow -> Red
    // This provides better contrast and is more colorblind-friendly
    var r: u8 = 0;
    var g: u8 = 0;
    var b: u8 = 0;

    if (normalized < 0.33) {
        // Blue to Cyan (0.0 to 0.33)
        const t = normalized / 0.33;
        r = 0;
        g = @intFromFloat(t * 255.0);
        b = 255;
    } else if (normalized < 0.66) {
        // Cyan to Yellow (0.33 to 0.66)
        const t = (normalized - 0.33) / 0.33;
        r = @intFromFloat(t * 255.0);
        g = 255;
        b = @intFromFloat((1.0 - t) * 255.0);
    } else {
        // Yellow to Red (0.66 to 1.0)
        const t = (normalized - 0.66) / 0.34;
        r = 255;
        g = @intFromFloat((1.0 - t) * 255.0);
        b = 0;
    }

    return .{ .r = r, .g = g, .b = b };
}
