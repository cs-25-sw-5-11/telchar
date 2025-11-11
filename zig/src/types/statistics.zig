const std = @import("std");

/// Time-of-day index (e.g., 5-minute bins in a day: 0-287)
pub const TimeIndex = u16;

/// Speed in cm/s (stored as integer to save memory)
pub const SpeedCmPerSec = i32;

/// Variance in (cm/s)^2
pub const VarianceSq = i32;

/// Traversal count
pub const Count = u32;

/// Speed statistics for one edge at one time-of-day
pub const SpeedStats = struct {
    mean_speed_cms: SpeedCmPerSec,
    variance_sq: VarianceSq,
    count: Count,

    pub fn empty() SpeedStats {
        return .{
            .mean_speed_cms = 0,
            .variance_sq = 0,
            .count = 0,
        };
    }

    /// Convert mean to km/h for human readability
    pub fn meanKmh(self: SpeedStats) f64 {
        return (@as(f64, @floatFromInt(self.mean_speed_cms)) / 100.0) * 3.6;
    }

    /// Standard deviation in km/h
    pub fn stdDevKmh(self: SpeedStats) f64 {
        const variance_f64 = @as(f64, @floatFromInt(self.variance_sq));
        const std_dev_cms = @sqrt(variance_f64);
        return (std_dev_cms / 100.0) * 3.6;
    }
};

/// Complete speed statistics for the network
/// Structure: edge_id -> (time_index -> SpeedStats)
pub const NetworkStats = struct {
    /// Map from EdgeId to time-indexed statistics array
    /// Array length = number of time bins in 24 hours
    edge_stats: std.AutoHashMap(u32, []SpeedStats),
    time_bins_per_day: u16,
    allocator: std.mem.Allocator,

    pub fn init(allocator: std.mem.Allocator, num_edges: u32, time_bins: u16) !NetworkStats {
        var edge_stats = std.AutoHashMap(u32, []SpeedStats).init(allocator);
        try edge_stats.ensureTotalCapacity(num_edges);

        return NetworkStats{
            .edge_stats = edge_stats,
            .time_bins_per_day = time_bins,
            .allocator = allocator,
        };
    }

    pub fn deinit(self: *NetworkStats) void {
        var iter = self.edge_stats.valueIterator();
        while (iter.next()) |stats_array| {
            self.allocator.free(stats_array.*);
        }
        self.edge_stats.deinit();
    }
};

/// Single traversal observation (input to aggregation)
pub const Traversal = struct {
    edge_id: u32,
    time_index: TimeIndex,
    speed_mps: f64, // meters per second
};
