const std = @import("std");
const geo = @import("../types/geo.zig");
const graph = @import("../types/graph.zig");
const haversine = @import("../utils/haversine.zig");

/// HMM parameters for map matching
pub const HmmParams = struct {
    /// GPS measurement error standard deviation (meters)
    /// Typical: 4-10m for consumer GPS
    /// Estimate from data using MAD (Median Absolute Deviation)
    sigma_z: f64 = 4.07,

    /// Transition probability scale parameter
    /// Urban: 3-5, Rural: 5-10
    beta: f64 = 3.0,

    /// Speed limit for validation (m/s)
    /// Reject routes requiring >1.5× this speed
    max_speed_mps: f64 = 41.67, // 150 km/h
};

/// Compute emission probability: p(z_t|r_i)
/// Gaussian distribution based on perpendicular distance from GPS point to edge
/// Formula: p(z_t|r_i) = (1/√(2π·σ_z²)) · exp(-0.5·(d/σ_z)²)
pub fn computeEmissionProbability(
    perpendicular_distance_m: f64,
    params: HmmParams,
) f64 {
    const d = perpendicular_distance_m;
    const sigma = params.sigma_z;

    // Gaussian PDF
    const coefficient = 1.0 / @sqrt(2.0 * std.math.pi * sigma * sigma);
    const exponent = -0.5 * (d * d) / (sigma * sigma);

    return coefficient * @exp(exponent);
}

/// Compute transition probability: p(r_i→r_j)
/// Exponential distribution based on difference between route distance and great-circle distance
/// Formula: p(d_t) = (1/β)·exp(-d_t/β) where d_t = |route_distance - great_circle_distance|
pub fn computeTransitionProbability(
    route_distance_m: f64,
    great_circle_distance_m: f64,
    time_gap_sec: i64,
    params: HmmParams,
) f64 {
    // Speed validation: reject if required speed > 2.0× speed_limit
    // Relaxed from 1.5× to account for GPS noise and timing errors
    const required_speed = route_distance_m / @as(f64, @floatFromInt(time_gap_sec));
    if (required_speed > 2.0 * params.max_speed_mps) {
        return 0.0; // Physically impossible
    }

    // Exponential distribution on route-vs-great-circle difference
    const d_t = @abs(route_distance_m - great_circle_distance_m);
    const beta = params.beta;

    return (1.0 / beta) * @exp(-d_t / beta);
}

/// Compute combined HMM cost (negative log probability)
/// Lower cost = higher probability
pub fn computeHmmCost(
    emission_prob: f64,
    transition_prob: f64,
) f64 {
    // Use negative log probability as cost for Viterbi
    // Handle zero probabilities
    const eps = 1e-10;
    const emission_cost = -@log(@max(emission_prob, eps));
    const transition_cost = -@log(@max(transition_prob, eps));

    return emission_cost + transition_cost;
}

/// Estimate σ_z from GPS data using MAD (Median Absolute Deviation)
/// More robust than standard deviation for data with outliers
pub fn estimateSigmaZ(
    allocator: std.mem.Allocator,
    projection_errors: []const f64,
) !f64 {
    if (projection_errors.len == 0) return 4.07; // Default

    // Copy and sort errors
    const sorted = try allocator.dupe(f64, projection_errors);
    defer allocator.free(sorted);
    std.sort.heap(f64, sorted, {}, comptime std.sort.asc(f64));

    // Compute median
    const median = if (sorted.len % 2 == 0)
        (sorted[sorted.len / 2 - 1] + sorted[sorted.len / 2]) / 2.0
    else
        sorted[sorted.len / 2];

    // Compute absolute deviations from median
    var deviations = try allocator.alloc(f64, sorted.len);
    defer allocator.free(deviations);

    for (sorted, 0..) |err, i| {
        deviations[i] = @abs(err - median);
    }

    std.sort.heap(f64, deviations, {}, comptime std.sort.asc(f64));

    // MAD (median of absolute deviations)
    const mad = if (deviations.len % 2 == 0)
        (deviations[deviations.len / 2 - 1] + deviations[deviations.len / 2]) / 2.0
    else
        deviations[deviations.len / 2];

    // Convert MAD to standard deviation estimate
    // For Gaussian distribution: σ ≈ 1.4826 × MAD
    return 1.4826 * mad;
}

test "emission probability" {
    const params = HmmParams{ .sigma_z = 4.07 };

    // At distance 0, probability should be maximum
    const prob_0 = computeEmissionProbability(0.0, params);
    const prob_10 = computeEmissionProbability(10.0, params);

    try std.testing.expect(prob_0 > prob_10);
}

test "transition probability with speed validation" {
    const params = HmmParams{
        .beta = 3.0,
        .max_speed_mps = 41.67, // 150 km/h
    };

    // Normal case: route ≈ great-circle, reasonable speed
    const prob_normal = computeTransitionProbability(100.0, 95.0, 10, params);
    try std.testing.expect(prob_normal > 0.0);

    // Impossible case: requires 200 m/s (720 km/h)
    const prob_impossible = computeTransitionProbability(2000.0, 1000.0, 10, params);
    try std.testing.expectEqual(0.0, prob_impossible);
}

test "MAD estimation" {
    const allocator = std.testing.allocator;

    // Known data with σ ≈ 5
    const errors = [_]f64{ 0.0, 3.0, 5.0, 7.0, 10.0 };
    const sigma = try estimateSigmaZ(allocator, &errors);

    // Should be in reasonable range
    try std.testing.expect(sigma > 2.0 and sigma < 10.0);
}
