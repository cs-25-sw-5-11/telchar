const std = @import("std");
const graph = @import("../types/graph.zig");
const trip_types = @import("../types/trip.zig");
const stats_types = @import("../types/statistics.zig");
const projection = @import("projection.zig");
const hmm_prob = @import("hmm_probabilities.zig");
const viterbi_module = @import("viterbi.zig");
const haversine = @import("../utils/haversine.zig");
const routing = @import("../stage4_distances/routing.zig");

pub const MatchingConfig = struct {
    /// Maximum distance for GPS point projection onto edges (meters)
    max_projection_distance_m: f64 = 100.0,

    /// GPS error standard deviation (meters) - σ_z in HMM
    gps_sigma_m: f64 = 4.07,

    /// Transition probability decay parameter - β in HMM
    transition_beta: f64 = 3.0,

    /// Maximum speed for speed validation (m/s)
    max_speed_mps: f64 = 41.67, // 150 km/h

    /// Speed validation multiplier (reject routes requiring >multiplier × max_speed)
    speed_multiplier: f64 = 2.0,

    /// Time gap threshold for splitting traces (seconds)
    max_time_gap_sec: i64 = 100,

    /// Maximum routing distance for A* (meters)
    /// If projections are farther apart than this, use great-circle distance
    max_routing_distance_m: f64 = 2000.0,

    /// Enable actual routing (requires adjacency list)
    /// If false, uses great-circle distance approximation
    use_routing: bool = false,
};

pub const MatchingResult = struct {
    /// Successfully matched trips
    matched_trips: []trip_types.MatchedTrip,

    /// Statistics: number of points that failed to match
    unmatched_points: usize,

    /// Statistics: number of trips that failed completely
    failed_trips: usize,

    allocator: std.mem.Allocator,

    pub fn deinit(self: *MatchingResult) void {
        for (self.matched_trips) |*trip| {
            trip.deinit();
        }
        self.allocator.free(self.matched_trips);
    }
};

/// Match a single trip to the road network using HMM+Viterbi
pub fn matchTrip(
    allocator: std.mem.Allocator,
    trip: trip_types.Trip,
    trip_ptr: *const trip_types.Trip,  // Stable pointer for MatchedTrip reference
    network: *const graph.Network,
    adjacency: ?*const graph.AdjacencyList,
    config: MatchingConfig,
) !?trip_types.MatchedTrip {
    if (trip.points.len < 2) return null;

    // Split trip at large time gaps
    const subtours = try splitTripByTimeGaps(allocator, trip, config.max_time_gap_sec);
    defer {
        for (subtours) |subtour| {
            allocator.free(subtour);
        }
        allocator.free(subtours);
    }

    // Match each subtour independently
    var all_projections = std.ArrayList(trip_types.Projection){};
    defer all_projections.deinit(allocator);

    for (subtours) |subtour| {
        if (subtour.len < 2) continue;

        // Match this subtour
        const matched_subtour = try matchSubtour(
            allocator,
            subtour,
            network,
            adjacency,
            config,
        ) orelse continue;

        defer allocator.free(matched_subtour);

        // Append to results
        for (matched_subtour) |proj| {
            try all_projections.append(allocator, proj);
        }
    }

    if (all_projections.items.len == 0) return null;

    // Extract unique edge sequence from projections
    var edge_sequence = std.ArrayList(u32){};
    defer edge_sequence.deinit(allocator);

    var last_edge_id: ?u32 = null;
    for (all_projections.items) |proj| {
        if (last_edge_id == null or last_edge_id.? != proj.edge_id) {
            try edge_sequence.append(allocator, proj.edge_id);
            last_edge_id = proj.edge_id;
        }
    }

    return trip_types.MatchedTrip{
        .trip_id = trip.trip_id,
        .projections = try all_projections.toOwnedSlice(allocator),
        .path = try edge_sequence.toOwnedSlice(allocator),
        .original_trip = trip_ptr,
        .allocator = allocator,
    };
}

/// Split trip into subtours at time gaps
fn splitTripByTimeGaps(
    allocator: std.mem.Allocator,
    trip: trip_types.Trip,
    max_gap_sec: i64,
) ![][]const trip_types.GpsPoint {
    var subtours = std.ArrayList([]const trip_types.GpsPoint){};
    defer subtours.deinit(allocator);

    var current_subtour = std.ArrayList(trip_types.GpsPoint){};
    defer current_subtour.deinit(allocator);

    try current_subtour.append(allocator, trip.points[0]);

    for (trip.points[1..]) |point| {
        const prev_point = current_subtour.items[current_subtour.items.len - 1];
        const time_diff = point.timestamp - prev_point.timestamp;

        if (time_diff > max_gap_sec) {
            // Save current subtour and start new one
            if (current_subtour.items.len >= 2) {
                try subtours.append(allocator, try current_subtour.toOwnedSlice(allocator));
            } else {
                // Clear the current subtour if it's too short
                current_subtour.clearRetainingCapacity();
            }
            // No need to create new ArrayList - clearRetainingCapacity or toOwnedSlice already reset it
        }

        try current_subtour.append(allocator, point);
    }

    // Save final subtour
    if (current_subtour.items.len >= 2) {
        try subtours.append(allocator, try current_subtour.toOwnedSlice(allocator));
    }

    return try subtours.toOwnedSlice(allocator);
}

/// Match a continuous subtour (no time gaps) using HMM+Viterbi
fn matchSubtour(
    allocator: std.mem.Allocator,
    points: []const trip_types.GpsPoint,
    network: *const graph.Network,
    adjacency: ?*const graph.AdjacencyList,
    config: MatchingConfig,
) !?[]trip_types.Projection {
    if (points.len < 2) return null;

    // Create HMM parameters from config
    const hmm_params = hmm_prob.HmmParams{
        .sigma_z = config.gps_sigma_m,
        .beta = config.transition_beta,
        .max_speed_mps = config.max_speed_mps,
    };

    // Step 1: Generate candidate projections for each GPS point
    var candidates = std.ArrayList([]projection.ProjectionResult){};
    defer {
        for (candidates.items) |layer_candidates| {
            allocator.free(layer_candidates);
        }
        candidates.deinit(allocator);
    }

    // Build list of valid point indices and their candidates
    var valid_point_indices = std.ArrayList(usize){};
    defer valid_point_indices.deinit(allocator);

    for (points, 0..) |gps_point, point_idx| {
        const point_candidates = try projection.projectPoint(
            allocator,
            gps_point.location,
            network,
            config.max_projection_distance_m,
        );

        if (point_candidates.len == 0) {
            // Skip this GPS point - continue with remaining points
            allocator.free(point_candidates);
            continue;
        }

        try candidates.append(allocator, point_candidates);
        try valid_point_indices.append(allocator, point_idx);
    }

    // Need at least 2 valid points to do matching
    if (candidates.items.len < 2) {
        return null;
    }

    // Step 2: Build Viterbi layers (state = projection ID)
    const V = viterbi_module.Viterbi(u32, f64);
    var layers = std.ArrayList(V.Layer){};
    defer {
        for (layers.items) |*layer| {
            layer.deinit();
        }
        layers.deinit(allocator);
    }

    // Create projection ID map
    var proj_id_to_proj = std.AutoHashMap(u32, projection.ProjectionResult).init(allocator);
    defer proj_id_to_proj.deinit();

    var next_proj_id: u32 = 0;

    for (candidates.items) |layer_candidates| {
        var layer_states = std.ArrayList(u32){};
        defer layer_states.deinit(allocator);

        for (layer_candidates) |proj| {
            try layer_states.append(allocator, next_proj_id);
            try proj_id_to_proj.put(next_proj_id, proj);
            next_proj_id += 1;
        }

        try layers.append(allocator, V.Layer{
            .states = try layer_states.toOwnedSlice(allocator),
            .allocator = allocator,
        });
    }

    // Step 3: Compute HMM transition costs
    var transitions = std.ArrayList([]V.Transition){};
    defer {
        for (transitions.items) |trans_layer| {
            allocator.free(trans_layer);
        }
        transitions.deinit(allocator);
    }

    for (0..layers.items.len - 1) |t| {
        const from_layer = layers.items[t];
        const to_layer = layers.items[t + 1];

        var trans_list = std.ArrayList(V.Transition){};
        defer trans_list.deinit(allocator);

        // Use valid point indices for time differences
        const from_point_idx = valid_point_indices.items[t];
        const to_point_idx = valid_point_indices.items[t + 1];
        const time_diff = points[to_point_idx].timestamp - points[from_point_idx].timestamp;

        for (from_layer.states) |from_id| {
            for (to_layer.states) |to_id| {
                const to_proj = proj_id_to_proj.get(to_id).?;

                // Compute emission probability for target projection
                const emission_cost = -@log(
                    hmm_prob.computeEmissionProbability(to_proj.perpendicular_distance, hmm_params)
                );

                // Compute transition probability
                const great_circle_dist = haversine.distance(
                    points[from_point_idx].location,
                    points[to_point_idx].location,
                );

                // Compute actual route distance if routing is enabled
                var route_dist = great_circle_dist;
                if (config.use_routing and adjacency != null) {
                    const from_proj = proj_id_to_proj.get(from_id).?;

                    // Get the end vertex of the from_edge and start vertex of to_edge
                    const from_edge = network.edges[from_proj.edge_id];
                    const to_edge = network.edges[to_proj.edge_id];

                    // If within reasonable routing distance, use A*
                    if (great_circle_dist <= config.max_routing_distance_m) {
                        if (routing.findShortestPath(
                            allocator,
                            network,
                            adjacency.?,
                            from_edge.end_vertex_id,
                            to_edge.start_vertex_id,
                            config.max_routing_distance_m,
                        )) |maybe_route| {
                            if (maybe_route) |route| {
                                defer {
                                    var mut_route = route;
                                    mut_route.deinit();
                                }
                                // Add the partial distances on the edges themselves
                                const from_edge_remaining = from_edge.length_meters - from_proj.distance_from_start;
                                const to_edge_partial = to_proj.distance_from_start;
                                route_dist = from_edge_remaining + route.total_distance_m + to_edge_partial;
                            }
                        } else |_| {
                            // Routing failed, fall back to great circle
                            route_dist = great_circle_dist;
                        }
                    }
                }

                const transition_prob = hmm_prob.computeTransitionProbability(
                    route_dist,
                    great_circle_dist,
                    time_diff,
                    hmm_params,
                );

                if (transition_prob <= 0.0) {
                    // Speed validation failed - skip this transition
                    continue;
                }

                const transition_cost = -@log(transition_prob);

                const total_cost = emission_cost + transition_cost;

                try trans_list.append(allocator, V.Transition{
                    .from_state = from_id,
                    .to_state = to_id,
                    .cost = total_cost,
                });
            }
        }

        try transitions.append(allocator, try trans_list.toOwnedSlice(allocator));
    }

    // Step 4: Run Viterbi algorithm
    var viterbi_result = try V.run(
        allocator,
        layers.items,
        transitions.items,
    ) orelse return null;
    defer viterbi_result.deinit();

    // Step 5: Extract projections from optimal path
    var result_projections = std.ArrayList(trip_types.Projection){};
    defer result_projections.deinit(allocator);

    for (viterbi_result.states, 0..) |proj_id, valid_idx| {
        const proj_result = proj_id_to_proj.get(proj_id).?;
        const original_gps_idx = valid_point_indices.items[valid_idx];

        // Convert ProjectionResult to Projection
        const proj = trip_types.Projection{
            .gps_index = @intCast(original_gps_idx),
            .edge_id = proj_result.edge_id,
            .location = proj_result.projected_point,
            .distance_from_start = proj_result.distance_from_start,
            .projection_error = proj_result.perpendicular_distance,
        };

        try result_projections.append(allocator, proj);
    }

    return try result_projections.toOwnedSlice(allocator);
}

/// Batch match multiple trips
pub fn matchTrips(
    allocator: std.mem.Allocator,
    trips: []const trip_types.Trip,
    network: *const graph.Network,
    config: MatchingConfig,
) !MatchingResult {
    var matched = std.ArrayList(trip_types.MatchedTrip){};
    defer matched.deinit(allocator);

    var unmatched_points: usize = 0;
    var failed_trips: usize = 0;

    for (trips) |trip| {
        if (try matchTrip(allocator, trip, network, config)) |matched_trip| {
            try matched.append(allocator, matched_trip);

            // Count unmatched points
            if (matched_trip.projections.len < trip.points.len) {
                unmatched_points += trip.points.len - matched_trip.projections.len;
            }
        } else {
            failed_trips += 1;
            unmatched_points += trip.points.len;
        }
    }

    return MatchingResult{
        .matched_trips = try matched.toOwnedSlice(allocator),
        .unmatched_points = unmatched_points,
        .failed_trips = failed_trips,
        .allocator = allocator,
    };
}

test "split trip by time gaps" {
    const allocator = std.testing.allocator;

    const points = [_]trip_types.GpsPoint{
        .{ .location = .{ .lat = 45.0, .lon = 126.0 }, .timestamp = 1000 },
        .{ .location = .{ .lat = 45.001, .lon = 126.001 }, .timestamp = 1010 },
        .{ .location = .{ .lat = 45.002, .lon = 126.002 }, .timestamp = 1020 },
        .{ .location = .{ .lat = 45.003, .lon = 126.003 }, .timestamp = 1200 }, // Gap
        .{ .location = .{ .lat = 45.004, .lon = 126.004 }, .timestamp = 1210 },
        .{ .location = .{ .lat = 45.005, .lon = 126.005 }, .timestamp = 1220 },
    };

    const trip = trip_types.Trip{
        .trip_id = 1,
        .points = &points,
        .allocator = allocator,
    };

    const subtours = try splitTripByTimeGaps(allocator, trip, 100);
    defer {
        for (subtours) |subtour| {
            allocator.free(subtour);
        }
        allocator.free(subtours);
    }

    // Should split into 2 subtours
    try std.testing.expectEqual(@as(usize, 2), subtours.len);
    try std.testing.expectEqual(@as(usize, 3), subtours[0].len);
    try std.testing.expectEqual(@as(usize, 3), subtours[1].len);
}
