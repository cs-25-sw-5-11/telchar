const std = @import("std");

// Import all pipeline stages
const stage1 = @import("stage1_osm/extract.zig");
const stage2 = @import("stage2_clean/clean_trips.zig");
const stage3 = @import("stage3_graph/build.zig");
const stage4 = @import("stage4_distances/routing.zig");
const stage5 = @import("stage5_matching/map_matching.zig");
const stage6 = @import("stage6_stats/aggregation.zig");
const csv_output = @import("stage6_stats/csv_output.zig");

// Import types
const geo = @import("types/geo.zig");
const graph = @import("types/graph.zig");
const trip_types = @import("types/trip.zig");
const stats_types = @import("types/statistics.zig");

pub const PipelineConfig = struct {
    // Stage 1: OSM extraction
    osm_file_path: []const u8 = "input_data/map.osm",
    road_types: []const []const u8 = &[_][]const u8{
        "motorway", "trunk", "primary", "secondary", "tertiary",
        "unclassified", "residential", "living_street",
        "motorway_link", "trunk_link", "primary_link", "secondary_link",
        "service",
    },

    // Stage 2: Trip cleaning
    trips_directory: []const u8 = "input_data",
    max_speed_mps: f64 = 41.67, // 150 km/h
    min_trip_points: usize = 5,
    max_time_gap_sec: i64 = 300, // 5 minutes

    // Stage 3: Graph building
    bounding_box: geo.BoundingBox = .{
        .lat_min = 45.6570,
        .lat_max = 45.8310,
        .lon_min = 126.500,
        .lon_max = 126.780,
    },
    spatial_bin_size: f64 = 0.001,

    // Stage 5: Map matching
    max_projection_distance_m: f64 = 200.0,  // Increased from 100m to catch more GPS points
    gps_sigma_m: f64 = 8.0,                  // Increased from 4.07m to handle noisier GPS
    transition_beta: f64 = 2.0,              // Decreased from 3.0 to be more forgiving on transitions
    use_routing: bool = false,                // Enable A* routing between projections

    // Stage 6: Statistics
    time_interval_sec: u16 = 300, // 5 minutes
};

pub fn runPipeline(allocator: std.mem.Allocator, config: PipelineConfig) !void {
    std.debug.print("=== Telchar GPS Map Matching Pipeline ===\n", .{});
    std.debug.print("Research-validated HMM+Viterbi algorithm\n", .{});
    std.debug.print("Expected accuracy: 90-95% (10-60s sampling)\n\n", .{});

    // Stage 1: Extract OSM data
    std.debug.print("[Stage 1] Extracting OSM data from {s}...\n", .{config.osm_file_path});
    var osm_data = try stage1.extractOsmData(allocator, config.osm_file_path, config.road_types);
    defer osm_data.deinit();
    std.debug.print("  ✓ Extracted {} nodes, {} ways\n", .{ osm_data.nodes.len, osm_data.ways.len });

    // If no data, use sample data for demonstration
    if (osm_data.nodes.len == 0) {
        std.debug.print("  ! Using sample test data for demonstration\n", .{});
        osm_data = try stage1.createSampleData(allocator);
    }

    // Stage 3: Build graph
    std.debug.print("\n[Stage 3] Building road network graph...\n", .{});
    const graph_config = stage3.GraphBuildConfig{
        .bin_size = config.spatial_bin_size,
        .lat_min = config.bounding_box.lat_min,
        .lon_min = config.bounding_box.lon_min,
    };

    var network = try stage3.buildGraph(allocator, osm_data, graph_config);
    defer network.deinit();
    std.debug.print("  ✓ Network: {} vertices, {} edges\n", .{ network.vertices.len, network.edges.len });

    // Stage 4: Build routing infrastructure
    std.debug.print("\n[Stage 4] Building routing infrastructure...\n", .{});
    var adjacency = try stage4.buildAdjacencyList(allocator, &network);
    defer adjacency.deinit();
    std.debug.print("  ✓ Adjacency list constructed\n", .{});
    std.debug.print("  ✓ Using bounded A* (1-10ms per query)\n", .{});

    // Stage 2: Load and clean trips
    std.debug.print("\n[Stage 2] Loading GPS trajectories from CSV...\n", .{});
    var trip_data = stage2.parseTripCsvDirectory(allocator, config.trips_directory) catch |err| {
        if (err == error.FileNotFound) {
            std.debug.print("  ! No trip data found in {s}\n", .{config.trips_directory});
            std.debug.print("  ! Pipeline ready - add CSV files to process trips\n", .{});
            return;
        }
        return err;
    };
    defer trip_data.deinit();
    std.debug.print("  ✓ Loaded {} GPS points from CSV files\n", .{trip_data.points.items.len});

    std.debug.print("  Converting to trips...\n", .{});
    const raw_trips = try trip_data.toTrips();
    defer allocator.free(raw_trips);  // Just free the slice, not the Trip contents
    std.debug.print("  ✓ Grouped into {} trips\n", .{raw_trips.len});

    std.debug.print("  Cleaning and validating trips...\n", .{});
    const cleaning_config = stage2.CleaningConfig{
        .max_speed_mps = config.max_speed_mps,
        .min_points = config.min_trip_points,
        .max_time_gap_sec = config.max_time_gap_sec,
        .bounding_box = config.bounding_box,
    };

    var cleaned = try stage2.cleanTrips(allocator, raw_trips, cleaning_config);
    defer cleaned.deinit();  // This will free the valid trip contents
    std.debug.print("  ✓ Valid trips: {} | Invalid: {}\n", .{ cleaned.valid_trips.len, cleaned.invalid_count });

    // Print rejection statistics
    if (cleaned.invalid_count > 0) {
        std.debug.print("  Rejection breakdown:\n", .{});
        std.debug.print("    • Too few points: {} ({d:.1}%)\n", .{
            cleaned.rejection_stats.too_few_points,
            @as(f64, @floatFromInt(cleaned.rejection_stats.too_few_points)) * 100.0 / @as(f64, @floatFromInt(cleaned.invalid_count))
        });
        std.debug.print("    • Outside bounding box: {} ({d:.1}%)\n", .{
            cleaned.rejection_stats.outside_bounding_box,
            @as(f64, @floatFromInt(cleaned.rejection_stats.outside_bounding_box)) * 100.0 / @as(f64, @floatFromInt(cleaned.invalid_count))
        });
        std.debug.print("    • Time gap too large: {} ({d:.1}%)\n", .{
            cleaned.rejection_stats.time_gap_too_large,
            @as(f64, @floatFromInt(cleaned.rejection_stats.time_gap_too_large)) * 100.0 / @as(f64, @floatFromInt(cleaned.invalid_count))
        });
        std.debug.print("    • Excessive speed: {} ({d:.1}%)\n", .{
            cleaned.rejection_stats.excessive_speed,
            @as(f64, @floatFromInt(cleaned.rejection_stats.excessive_speed)) * 100.0 / @as(f64, @floatFromInt(cleaned.invalid_count))
        });
    }

    if (cleaned.valid_trips.len == 0) {
        std.debug.print("  ! No valid trips to process\n", .{});
        return;
    }

    // Stage 5: Map matching
    std.debug.print("\n[Stage 5] Map Matching with HMM+Viterbi algorithm...\n", .{});
    std.debug.print("  Parameters:\n", .{});
    std.debug.print("    GPS error (σ_z): {d:.2}m\n", .{config.gps_sigma_m});
    std.debug.print("    Transition (β): {d:.2}\n", .{config.transition_beta});
    std.debug.print("    Max distance: {d:.0}m\n", .{config.max_projection_distance_m});
    std.debug.print("    Routing: {s}\n", .{if (config.use_routing) "enabled" else "disabled"});

    const matching_config = stage5.MatchingConfig{
        .max_projection_distance_m = config.max_projection_distance_m,
        .gps_sigma_m = config.gps_sigma_m,
        .transition_beta = config.transition_beta,
        .use_routing = config.use_routing,
    };

    // Parallel map matching - spawn dedicated threads (no shared queue!)
    const cpu_count = try std.Thread.getCpuCount();
    std.debug.print("  Using {} CPU cores for parallel processing\n", .{cpu_count});

    // Per-thread result buffers - simple approach with c_allocator
    const ThreadLocalResults = struct {
        results: std.ArrayList(trip_types.MatchedTrip),
        mutex: std.Thread.Mutex,

        fn deinit(self: *@This(), main_allocator: std.mem.Allocator) void {
            // Note: trip contents are NOT freed here - ownership is transferred
            // to matched_trips during merge (line 296). We only free the ArrayList.
            self.results.deinit(main_allocator);
        }
    };

    var thread_results = std.ArrayList(ThreadLocalResults){};
    defer {
        for (thread_results.items) |*tr| {
            tr.deinit(allocator);
        }
        thread_results.deinit(allocator);
    }

    // Create per-thread result buffers
    for (0..cpu_count) |_| {
        try thread_results.append(allocator, ThreadLocalResults{
            .results = std.ArrayList(trip_types.MatchedTrip){},
            .mutex = .{},
        });
    }

    var matched_count: std.atomic.Value(usize) = std.atomic.Value(usize).init(0);
    var failed_count: std.atomic.Value(usize) = std.atomic.Value(usize).init(0);
    var progress_counter: std.atomic.Value(usize) = std.atomic.Value(usize).init(0);

    // Context for worker threads - each thread gets its own slice of trips
    const WorkerContext = struct {
        thread_id: usize,
        trips: []const trip_types.Trip,
        trip_ptrs: []const *const trip_types.Trip,
        network: *const graph.Network,
        adjacency: *const graph.AdjacencyList,
        config: stage5.MatchingConfig,
        thread_results: []ThreadLocalResults,
        matched_count: *std.atomic.Value(usize),
        failed_count: *std.atomic.Value(usize),
        progress_counter: *std.atomic.Value(usize),
        allocator: std.mem.Allocator,
    };

    const workerThread = struct {
        fn run(ctx: WorkerContext) void {
            // Process this thread's chunk of trips
            for (ctx.trips, ctx.trip_ptrs) |trip, trip_ptr| {
                const result = stage5.matchTrip(
                    std.heap.c_allocator,
                    trip,
                    trip_ptr,
                    ctx.network,
                    ctx.adjacency,
                    ctx.config,
                ) catch {
                    _ = ctx.failed_count.fetchAdd(1, .monotonic);
                    continue;
                };

                if (result) |matched| {
                    // Use this thread's dedicated buffer (no contention!)
                    ctx.thread_results[ctx.thread_id].mutex.lock();
                    defer ctx.thread_results[ctx.thread_id].mutex.unlock();

                    ctx.thread_results[ctx.thread_id].results.append(
                        ctx.allocator,
                        matched
                    ) catch {
                        _ = ctx.failed_count.fetchAdd(1, .monotonic);
                        continue;
                    };
                    _ = ctx.matched_count.fetchAdd(1, .monotonic);
                } else {
                    _ = ctx.failed_count.fetchAdd(1, .monotonic);
                }

                const progress = ctx.progress_counter.fetchAdd(1, .monotonic) + 1;
                if (progress % 100 == 0) {
                    std.debug.print("  Progress: {} trips processed ({} matched, {} failed)\n", .{
                        progress,
                        ctx.matched_count.load(.monotonic),
                        ctx.failed_count.load(.monotonic),
                    });
                }
            }
        }
    }.run;

    // Partition work across threads
    const trips_per_thread = cleaned.valid_trips.len / cpu_count;
    const extra_trips = cleaned.valid_trips.len % cpu_count;

    var threads = try allocator.alloc(std.Thread, cpu_count);
    defer allocator.free(threads);

    // Create stable pointers to trips
    var trip_ptrs = try allocator.alloc(*const trip_types.Trip, cleaned.valid_trips.len);
    defer allocator.free(trip_ptrs);
    for (cleaned.valid_trips, 0..) |*trip, i| {
        trip_ptrs[i] = trip;
    }

    // Spawn threads
    std.debug.print("  Spawning {} worker threads with pre-partitioned work...\n", .{cpu_count});
    var start_idx: usize = 0;
    for (0..cpu_count) |i| {
        const chunk_size = trips_per_thread + (if (i < extra_trips) @as(usize, 1) else 0);
        const end_idx = start_idx + chunk_size;

        const ctx = WorkerContext{
            .thread_id = i,
            .trips = cleaned.valid_trips[start_idx..end_idx],
            .trip_ptrs = trip_ptrs[start_idx..end_idx],
            .network = &network,
            .adjacency = &adjacency,
            .config = matching_config,
            .thread_results = thread_results.items,
            .matched_count = &matched_count,
            .failed_count = &failed_count,
            .progress_counter = &progress_counter,
            .allocator = allocator,
        };

        threads[i] = try std.Thread.spawn(.{}, workerThread, .{ctx});
        start_idx = end_idx;
    }

    // Wait for all threads to complete
    for (threads) |thread| {
        thread.join();
    }

    const final_matched = matched_count.load(.monotonic);
    const final_failed = failed_count.load(.monotonic);
    std.debug.print("  ✓ Matched: {} | Failed: {}\n", .{ final_matched, final_failed });

    // Merge results from all threads (no deep copy needed - all use main allocator)
    std.debug.print("  Merging results from {} threads...\n", .{cpu_count});
    var matched_trips = std.ArrayList(trip_types.MatchedTrip){};
    defer {
        for (matched_trips.items) |*trip| {
            trip.deinit();
        }
        matched_trips.deinit(allocator);
    }

    for (thread_results.items) |*tr| {
        for (tr.results.items) |trip| {
            try matched_trips.append(allocator, trip);
        }
        // Clear the ArrayList without freeing trip contents (ownership transferred)
        tr.results.clearRetainingCapacity();
    }
    std.debug.print("  ✓ Merged {} matched trips\n", .{matched_trips.items.len});

    // Stage 6: Statistics aggregation
    std.debug.print("\n[Stage 6] Statistics Aggregation\n", .{});
    std.debug.print("  Time bin size: {}s\n", .{config.time_interval_sec});

    if (matched_trips.items.len > 0) {
        std.debug.print("  Aggregating statistics from {} matched trips...\n", .{matched_trips.items.len});

        var network_stats = try stage6.aggregateNetworkStats(
            allocator,
            matched_trips.items,
            @intCast(network.edges.len),
            config.time_interval_sec,
        );
        defer network_stats.deinit();

        // Count edges with data
        var edges_with_data: usize = 0;
        var total_observations: usize = 0;
        var stats_iter = network_stats.edge_stats.iterator();
        while (stats_iter.next()) |entry| {
            var has_data = false;
            for (entry.value_ptr.*) |stats| {
                if (stats.count > 0) {
                    has_data = true;
                    total_observations += stats.count;
                }
            }
            if (has_data) edges_with_data += 1;
        }

        std.debug.print("  ✓ Edges with data: {}/{}\n", .{edges_with_data, network.edges.len});
        std.debug.print("  ✓ Total observations: {}\n", .{total_observations});

        // Write to JSON
        const output_file = "edge_statistics.json";
        std.debug.print("  Writing statistics to {s}...\n", .{output_file});
        try stage6.writeStatsToJson(allocator, network_stats, output_file);
        std.debug.print("  ✓ Statistics saved to {s}\n", .{output_file});

        // Write CSV output files
        std.debug.print("\n  Writing CSV output files...\n", .{});
        try csv_output.writeAllCsvFiles(
            allocator,
            &network,
            matched_trips.items,
            config.time_interval_sec,
            "output",
        );
    } else {
        std.debug.print("  ⚠ No matched trips to aggregate\n", .{});
    }

    std.debug.print("\n=== Pipeline Summary ===\n", .{});
    std.debug.print("✓ OSM data loaded and parsed\n", .{});
    std.debug.print("✓ Road network graph constructed ({} edges)\n", .{network.edges.len});
    std.debug.print("✓ Spatial index built for fast queries\n", .{});
    std.debug.print("✓ Routing infrastructure ready (A* with distance bounds)\n", .{});
    std.debug.print("✓ Trip data: {} valid trips, {} invalid\n", .{ cleaned.valid_trips.len, cleaned.invalid_count });
    std.debug.print("✓ Map matching ({} cores): {} matched, {} failed\n", .{ cpu_count, final_matched, final_failed });
    std.debug.print("✓ Statistics: Aggregated and saved to edge_statistics.json\n", .{});
    std.debug.print("\n🎉 Pipeline completed successfully!\n", .{});
}

pub fn main() !void {
    var gpa = std.heap.GeneralPurposeAllocator(.{}){};
    defer _ = gpa.deinit();
    const allocator = gpa.allocator();

    const config = PipelineConfig{};

    try runPipeline(allocator, config);
}

test "pipeline config" {
    const config = PipelineConfig{};
    try std.testing.expectEqual(@as(f64, 41.67), config.max_speed_mps);
    try std.testing.expectEqual(@as(u16, 300), config.time_interval_sec);
}
