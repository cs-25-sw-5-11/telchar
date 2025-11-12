const std = @import("std");

/// Generic Viterbi implementation
/// StateId: Type of state identifiers (e.g., u32 for projection IDs)
/// Cost: Type of cost values (e.g., f64)
pub fn Viterbi(comptime StateId: type, comptime Cost: type) type {
    return struct {
        pub const Transition = struct {
            from_state: StateId,
            to_state: StateId,
            cost: Cost,
        };

        pub const Layer = struct {
            states: []const StateId,
            allocator: std.mem.Allocator,

            pub fn deinit(self: *Layer) void {
                self.allocator.free(self.states);
            }
        };

        pub const Path = struct {
            states: []const StateId, // Sequence of states
            total_cost: Cost,
            allocator: std.mem.Allocator,

            pub fn deinit(self: *Path) void {
                self.allocator.free(self.states);
            }
        };

        /// Run Viterbi algorithm
        /// layers: states at each time step
        /// transitions: costs for transitions between consecutive layers
        pub fn run(
            allocator: std.mem.Allocator,
            layers: []const Layer,
            transitions: []const []const Transition,
        ) !?Path {
            if (layers.len == 0) return null;
            if (layers.len == 1) {
                if (layers[0].states.len == 0) return null;
                var path_states = try allocator.alloc(StateId, 1);
                path_states[0] = layers[0].states[0];
                return Path{
                    .states = path_states,
                    .total_cost = 0,
                    .allocator = allocator,
                };
            }

            // Dynamic programming tables
            // costs[t][state] = minimum cost to reach state at time t
            const CostMap = std.AutoHashMap(StateId, Cost);
            var costs = std.ArrayList(CostMap){};
            defer {
                for (costs.items) |*map| {
                    map.deinit();
                }
                costs.deinit(allocator);
            }

            // backpointers[t][state] = previous state in optimal path
            const BackPointerMap = std.AutoHashMap(StateId, StateId);
            var backpointers = std.ArrayList(BackPointerMap){};
            defer {
                for (backpointers.items) |*map| {
                    map.deinit();
                }
                backpointers.deinit(allocator);
            }

            // Initialize first layer
            try costs.append(allocator, CostMap.init(allocator));
            try backpointers.append(allocator, BackPointerMap.init(allocator));

            for (layers[0].states) |state| {
                try costs.items[0].put(state, 0);
            }

            // Forward pass
            for (1..layers.len) |t| {
                try costs.append(allocator, CostMap.init(allocator));
                try backpointers.append(allocator, BackPointerMap.init(allocator));

                // Build transition map for this layer
                const TransList = std.ArrayList(Transition);
                var trans_map = std.AutoHashMap(StateId, TransList).init(allocator);
                defer {
                    var iter = trans_map.valueIterator();
                    while (iter.next()) |list| {
                        list.deinit(allocator);
                    }
                    trans_map.deinit();
                }

                for (transitions[t - 1]) |trans| {
                    const entry = try trans_map.getOrPut(trans.to_state);
                    if (!entry.found_existing) {
                        entry.value_ptr.* = TransList{};
                    }
                    try entry.value_ptr.append(allocator, trans);
                }

                // For each state in current layer
                for (layers[t].states) |to_state| {
                    var min_cost: ?Cost = null;
                    var best_prev_state: ?StateId = null;

                    if (trans_map.get(to_state)) |trans_list| {
                        for (trans_list.items) |trans| {
                            const prev_cost = costs.items[t - 1].get(trans.from_state) orelse continue;
                            const total_cost = prev_cost + trans.cost;

                            if (min_cost == null or total_cost < min_cost.?) {
                                min_cost = total_cost;
                                best_prev_state = trans.from_state;
                            }
                        }
                    }

                    if (min_cost != null) {
                        try costs.items[t].put(to_state, min_cost.?);
                        try backpointers.items[t].put(to_state, best_prev_state.?);
                    }
                }

                // If no states reachable at this layer, path finding failed
                if (costs.items[t].count() == 0) {
                    return null;
                }
            }

            // Backward pass: find minimum cost final state
            const final_layer = costs.items[costs.items.len - 1];
            var min_final_cost: ?Cost = null;
            var best_final_state: ?StateId = null;

            var iter = final_layer.iterator();
            while (iter.next()) |entry| {
                if (min_final_cost == null or entry.value_ptr.* < min_final_cost.?) {
                    min_final_cost = entry.value_ptr.*;
                    best_final_state = entry.key_ptr.*;
                }
            }

            if (best_final_state == null) return null;

            // Reconstruct path
            var path_states = try std.ArrayList(StateId).initCapacity(allocator, layers.len);
            defer path_states.deinit(allocator);

            var current_state = best_final_state.?;
            var t = layers.len - 1;

            while (true) {
                try path_states.append(allocator, current_state);
                if (t == 0) break;
                current_state = backpointers.items[t].get(current_state) orelse break;
                t -= 1;
            }

            // Reverse path (we built it backwards)
            std.mem.reverse(StateId, path_states.items);

            return Path{
                .states = try path_states.toOwnedSlice(allocator),
                .total_cost = min_final_cost.?,
                .allocator = allocator,
            };
        }
    };
}

test "viterbi simple path" {
    const allocator = std.testing.allocator;
    const V = Viterbi(u32, f64);

    // Three layers with states: [0,1] -> [2,3] -> [4,5]
    const layer0 = V.Layer{
        .states = &[_]u32{ 0, 1 },
        .allocator = allocator,
    };
    const layer1 = V.Layer{
        .states = &[_]u32{ 2, 3 },
        .allocator = allocator,
    };
    const layer2 = V.Layer{
        .states = &[_]u32{ 4, 5 },
        .allocator = allocator,
    };

    const layers = [_]V.Layer{ layer0, layer1, layer2 };

    // Transitions layer 0 -> 1
    const trans0 = [_]V.Transition{
        .{ .from_state = 0, .to_state = 2, .cost = 1.0 },
        .{ .from_state = 0, .to_state = 3, .cost = 5.0 },
        .{ .from_state = 1, .to_state = 2, .cost = 10.0 },
        .{ .from_state = 1, .to_state = 3, .cost = 2.0 },
    };

    // Transitions layer 1 -> 2
    const trans1 = [_]V.Transition{
        .{ .from_state = 2, .to_state = 4, .cost = 1.0 },
        .{ .from_state = 2, .to_state = 5, .cost = 3.0 },
        .{ .from_state = 3, .to_state = 4, .cost = 2.0 },
        .{ .from_state = 3, .to_state = 5, .cost = 1.0 },
    };

    const transitions = [_][]const V.Transition{ &trans0, &trans1 };

    var result = try V.run(allocator, &layers, &transitions);
    defer if (result) |*path| path.deinit();

    try std.testing.expect(result != null);
    const path = result.?;

    // Optimal path should be 0 -> 2 -> 4 with cost 2.0
    try std.testing.expectEqual(@as(usize, 3), path.states.len);
    try std.testing.expectEqual(@as(u32, 0), path.states[0]);
    try std.testing.expectEqual(@as(u32, 2), path.states[1]);
    try std.testing.expectEqual(@as(u32, 4), path.states[2]);
    try std.testing.expectApproxEqRel(2.0, path.total_cost, 0.0001);
}
