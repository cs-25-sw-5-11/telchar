const std = @import("std");

/// Geographic coordinate in WGS84 (latitude, longitude)
pub const GeoPoint = struct {
    lat: f64,
    lon: f64,

    pub fn equals(self: GeoPoint, other: GeoPoint, tolerance: f64) bool {
        return @abs(self.lat - other.lat) < tolerance and
               @abs(self.lon - other.lon) < tolerance;
    }
};

/// Bounding box for geographic region
pub const BoundingBox = struct {
    lat_min: f64,
    lat_max: f64,
    lon_min: f64,
    lon_max: f64,

    pub fn contains(self: BoundingBox, point: GeoPoint) bool {
        return point.lat >= self.lat_min and
               point.lat <= self.lat_max and
               point.lon >= self.lon_min and
               point.lon <= self.lon_max;
    }
};

/// 2D bin index for spatial indexing
pub const BinIndex = struct {
    x: i32,
    y: i32,

    pub fn hash(self: BinIndex) u64 {
        const h1 = @as(u64, @bitCast(@as(i64, self.x)));
        const h2 = @as(u64, @bitCast(@as(i64, self.y)));
        return h1 ^ (h2 << 32);
    }

    pub fn eql(self: BinIndex, other: BinIndex) bool {
        return self.x == other.x and self.y == other.y;
    }
};

/// Configuration for spatial binning
pub const BinConfig = struct {
    lat_min: f64,
    lon_min: f64,
    bin_size: f64, // degrees per bin (e.g., 0.001)

    pub fn getBinIndex(self: BinConfig, point: GeoPoint) BinIndex {
        return .{
            .x = @intFromFloat(@floor((point.lon - self.lon_min) / self.bin_size)),
            .y = @intFromFloat(@floor((point.lat - self.lat_min) / self.bin_size)),
        };
    }
};

test "GeoPoint equality" {
    const p1 = GeoPoint{ .lat = 45.5, .lon = 126.6 };
    const p2 = GeoPoint{ .lat = 45.500001, .lon = 126.600001 };
    try std.testing.expect(p1.equals(p2, 0.0001));
}

test "BoundingBox containment" {
    const bbox = BoundingBox{
        .lat_min = 45.0,
        .lat_max = 46.0,
        .lon_min = 126.0,
        .lon_max = 127.0,
    };
    const inside = GeoPoint{ .lat = 45.5, .lon = 126.5 };
    const outside = GeoPoint{ .lat = 47.0, .lon = 126.5 };
    try std.testing.expect(bbox.contains(inside));
    try std.testing.expect(!bbox.contains(outside));
}
