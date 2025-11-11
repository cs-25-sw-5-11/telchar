const std = @import("std");
const stats_types = @import("../types/statistics.zig");

/// Update speed statistics using Welford's online algorithm
/// This is numerically stable and allows incremental updates
pub fn updateStats(
    current: stats_types.SpeedStats,
    new_speed_mps: f64,
) stats_types.SpeedStats {
    // Clamp extreme speeds (0-200 m/s = 0-720 km/h)
    const clamped_speed = std.math.clamp(new_speed_mps, 0.0, 200.0);

    // Convert to cm/s for storage
    const speed_cms = clamped_speed * 100.0;

    if (current.count == 0) {
        // First observation
        return .{
            .mean_speed_cms = @intFromFloat(@round(speed_cms)),
            .variance_sq = 0,
            .count = 1,
        };
    }

    // Use float arithmetic for accuracy
    const existing_mean_f64 = @as(f64, @floatFromInt(current.mean_speed_cms));
    const existing_variance_f64 = @as(f64, @floatFromInt(current.variance_sq));
    const new_count = current.count + 1;

    // Welford's algorithm
    const delta = speed_cms - existing_mean_f64;
    const new_mean = existing_mean_f64 + delta / @as(f64, @floatFromInt(new_count));
    const delta2 = speed_cms - new_mean;

    // M2 is the sum of squared deviations
    const M2 = existing_variance_f64 * @as(f64, @floatFromInt(current.count)) + delta * delta2;
    const new_variance = M2 / @as(f64, @floatFromInt(new_count));

    // Cap variance to prevent explosion
    // Max variance: 40000 (cm/s)^2 = std_dev 200 cm/s = 7.2 km/h
    const capped_variance = @min(new_variance, 40000.0);

    return .{
        .mean_speed_cms = @intFromFloat(@round(new_mean)),
        .variance_sq = @intFromFloat(@round(capped_variance)),
        .count = new_count,
    };
}

/// Batch update statistics from multiple traversals
pub fn aggregateTraversals(
    allocator: std.mem.Allocator,
    traversals: []const stats_types.Traversal,
    num_edges: u32,
    time_bins_per_day: u16,
) !stats_types.NetworkStats {
    var network_stats = try stats_types.NetworkStats.init(allocator, num_edges, time_bins_per_day);

    for (traversals) |traversal| {
        // Get or create stats array for this edge
        const entry = try network_stats.edge_stats.getOrPut(traversal.edge_id);
        if (!entry.found_existing) {
            const stats_array = try allocator.alloc(stats_types.SpeedStats, time_bins_per_day);
            for (stats_array) |*stat| {
                stat.* = stats_types.SpeedStats.empty();
            }
            entry.value_ptr.* = stats_array;
        }

        // Update stats for this time bin
        const current_stats = entry.value_ptr.*[traversal.time_index];
        entry.value_ptr.*[traversal.time_index] = updateStats(current_stats, traversal.speed_mps);
    }

    return network_stats;
}

test "welford single update" {
    const initial = stats_types.SpeedStats.empty();
    const updated = updateStats(initial, 10.0); // 10 m/s = 1000 cm/s

    try std.testing.expectEqual(@as(u32, 1), updated.count);
    try std.testing.expectEqual(@as(i32, 1000), updated.mean_speed_cms);
    try std.testing.expectEqual(@as(i32, 0), updated.variance_sq);
}

test "welford multiple updates" {
    var stats = stats_types.SpeedStats.empty();

    // Add speeds: 10 m/s, 12 m/s, 8 m/s
    stats = updateStats(stats, 10.0);
    stats = updateStats(stats, 12.0);
    stats = updateStats(stats, 8.0);

    try std.testing.expectEqual(@as(u32, 3), stats.count);

    // Mean should be 10 m/s = 1000 cm/s
    try std.testing.expectEqual(@as(i32, 1000), stats.mean_speed_cms);

    // Variance = E[(X - mean)^2] = E[(±200)^2] = 40000
    try std.testing.expectApproxEqRel(40000.0, @as(f64, @floatFromInt(stats.variance_sq)), 0.01);
}

test "variance capping" {
    var stats = stats_types.SpeedStats.empty();

    // Add extreme outlier to trigger cap
    stats = updateStats(stats, 10.0);
    stats = updateStats(stats, 100.0); // Very different

    // Variance should be capped at 40000
    try std.testing.expect(stats.variance_sq <= 40000);
}
