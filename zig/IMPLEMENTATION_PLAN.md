# Telchar Zig Implementation - Remaining Work Plan

## Completed ✅

### Phase 1: CSV Parsing & Data Loading
- ✅ Implemented CSV parser for GPS trip data (`src/stage2_clean/csv_parser.zig`)
- ✅ Support for Windows (`\r\n`) and Unix (`\n`) line endings
- ✅ Batch loading from directory of CSV files
- ✅ Conversion from CSV data to Trip objects
- ✅ Memory-efficient streaming parser
- ✅ Trip cleaning and validation (speed limits, bounding box, time gaps)

### Phase 2: Map Matching Core
- ✅ Implemented `projectPoint()` function to find candidate edges
- ✅ Integrated HMM+Viterbi algorithm
- ✅ Fixed Zig 0.15.1 API compatibility (`@log` builtin, `ArrayList`, `std.Io.Reader`)
- ✅ Proper memory management (defer blocks, allocator tracking)
- ✅ Type conversions between `ProjectionResult` and `Projection`
- ✅ Edge sequence extraction from matched projections

##  In Progress / Needs Fixing ⚠️

### Memory Management
- **Issue**: Memory leak detected in `splitTripByTimeGaps` function
- **Location**: `src/stage5_matching/map_matching.zig:125`
- **Fix**: Ensure all allocated subtours are properly freed in error paths
- **Priority**: HIGH

### Map Matching Failures
- **Issue**: All 17 test trips failed to match (0 matched, 17 failed)
- **Root Cause**: Sample test network has only 3 edges, real trip data is from Harbin, China
- **Options**:
  1. Load actual OSM data for Harbin region
  2. Create synthetic test data that matches the sample network
  3. Implement proper spatial indexing to filter edges efficiently
- **Priority**: MEDIUM

## Next Steps 🚀

### Phase 3: OSM Data Loading (HIGH PRIORITY)
Currently using placeholder test data. Need to implement actual OSM XML parsing:

**Tasks:**
1. **OSM XML Parser** (`src/stage1_osm/extract.zig`)
   - Implement SAX-style XML parser for `.osm` files
   - Extract nodes with lat/lon coordinates
   - Extract ways with highway tags
   - Filter by road types: primary, secondary, tertiary, residential
   - Handle large files (Harbin map is 61MB)

2. **Graph Construction** (`src/stage3_graph/build.zig`)
   - Convert OSM nodes → Vertices
   - Convert OSM ways → Directed Edges
   - Build spatial index (bin edges by lat/lon grid)
   - Compute edge lengths using Haversine distance
   - Handle bidirectional roads (oneways vs two-way streets)

3. **Testing with Real Data**
   - Use `input_data/map.osm` (Harbin, China)
   - Verify graph construction produces reasonable network
   - Test projection onto actual road edges

### Phase 4: Spatial Indexing Optimization (MEDIUM PRIORITY)

**Current State:**
- `Network.findNearbyEdges()` returns ALL edges (naive implementation)
- Acceptable for small networks, doesn't scale

**Required Implementation:**
1. Use existing `spatial_index: SpatialIndex` field in Network
2. Implement bin-based spatial query:
   ```zig
   // Calculate bins overlapping with search radius
   const center_bin = geo.pointToBin(point);
   const radius_in_bins = @ceil(max_distance_m / BIN_SIZE_METERS);

   // Check all bins in radius
   for (nearby_bins) |bin| {
       if (spatial_index.get(bin)) |edge_ids| {
           // Add edges from this bin to candidates
       }
   }
   ```
3. Filter candidates by actual distance (not just bin membership)

### Phase 5: Routing Integration (MEDIUM PRIORITY)

**Current State:**
- Map matching uses great-circle distance as route distance
- Line 258 in `map_matching.zig`: `const route_dist = great_circle_dist; // TODO: actual routing`

**Required Implementation:**
1. Use existing A* implementation from `stage4_distances/routing.zig`
2. For each transition (projection_i → projection_j):
   - Find shortest path between edges using A*
   - Use actual route distance for transition probability
   - Cache common routes (UBODT - Upper-Bounded Dijkstra Table)
3. Trade-off: Accuracy vs. speed
   - Option A: Route every transition (slow but accurate)
   - Option B: Cache pre-computed distances (fast but memory-intensive)
   - Option C: Use great-circle for close projections, route for distant ones

### Phase 6: Statistics Aggregation (LOW PRIORITY)

**Goal**: Compute edge travel speeds by time of day

**Tasks:**
1. **Implement `aggregateStatistics()`** (`src/stage6_stats/aggregation.zig`)
   - Input: Array of `MatchedTrip` objects
   - For each matched edge traversal:
     - Extract entry/exit timestamps from consecutive projections
     - Compute travel time and speed
     - Bin by time-of-day (5-minute intervals)
   - Aggregate per edge: mean speed, variance, sample count
   - Use Welford's online algorithm for numerical stability

2. **Edge Traversal Data Structure**
   ```zig
   pub const EdgeStats = struct {
       edge_id: u32,
       time_bin: u16,  // Minutes since midnight
       mean_speed_mps: f32,
       variance: f32,
       sample_count: u32,
   };
   ```

3. **Output Format**
   - JSON file with edge statistics
   - Format: `{ "edge_id": 123, "time_bins": [...] }`
   - One entry per edge with statistics for each time bin

### Phase 7: Performance Optimization (LOW PRIORITY)

**Optimization Opportunities:**
1. **Parallel Processing**
   - Match trips in parallel (trips are independent)
   - Use thread pool for batch processing
   - Zig stdlib: `std.Thread.Pool`

2. **Memory Pooling**
   - Reuse allocations across trips
   - Arena allocator for per-trip temporary data
   - Reset arena between trips instead of freeing individual allocations

3. **Profiling**
   - Identify bottlenecks (likely projection generation and Viterbi)
   - Use `std.time.Timer` to measure stage durations
   - Consider caching projection results for nearby points

## Testing Strategy 📊

### Unit Tests
- ✅ CSV parser (`test_parse_single_GPS_point_line`, `test_group_points_by_trip`)
- ✅ Projection (`test_segment_projection`, `test_endpoint_clamping`)
- ⚠️ Need: Map matching end-to-end test with known ground truth

### Integration Tests
- ⚠️ Test with small OSM extract (e.g., 1km² area)
- ⚠️ Verify statistics aggregation produces reasonable speeds
- ⚠️ Test memory usage with large datasets (millions of GPS points)

### Performance Benchmarks
- Target: Process 1M GPS points in < 5 minutes
- Current: Unknown (need benchmarking)
- Baseline: Python implementation processes 60M points in ~2 hours

## Dependencies & Tools

### Required
- Zig 0.15.1 (currently installed)
- OSM data for Harbin, China (already in `input_data/map.osm`)
- GPS trip CSV files (already in `input_data/trips_*.csv`)

### Optional
- XML parsing library (or implement SAX parser)
- Visualization tools for debugging matched routes
- Comparison with Python implementation for validation

## Known Issues 🐛

1. **Memory Leak** (HIGH)
   - Location: `splitTripByTimeGaps`
   - Impact: Accumulates over many trips
   - Fix: Add proper cleanup in all code paths

2. **Map Matching Failures** (MEDIUM)
   - All trips failing due to network mismatch
   - Need real OSM data loaded

3. **Naive Spatial Search** (MEDIUM)
   - Returns all edges, doesn't scale
   - Need bin-based filtering

4. **No Route Distance** (LOW)
   - Using great-circle approximation
   - Affects accuracy but algorithm still works

## Success Metrics 🎯

1. **Correctness**
   - Match rate > 80% on Harbin dataset
   - Speed estimates within 20% of ground truth

2. **Performance**
   - Process 60M GPS points in < 30 minutes
   - Memory usage < 4GB for full dataset

3. **Code Quality**
   - No memory leaks (GeneralPurposeAllocator in test mode)
   - All tests passing
   - Clear error messages for failures

## Timeline Estimate ⏱️

- **Phase 3** (OSM Loading): 4-6 hours
- **Phase 4** (Spatial Index): 2-3 hours
- **Phase 5** (Routing): 3-4 hours
- **Phase 6** (Statistics): 2-3 hours
- **Phase 7** (Optimization): 4-6 hours
- **Testing & Debugging**: 4-6 hours

**Total**: 19-28 hours of development work

## Notes

- The core map matching algorithm is complete and compiles successfully
- CSV parsing is production-ready
- Main blockers are OSM data loading and spatial indexing
- Once OSM data loads properly, expect immediate improvement in match rates
- The Zig implementation follows the same algorithm as the proven Python version
- Type safety and memory management are significantly better than the Python version
