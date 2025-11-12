const std = @import("std");

/// OSM Node representation
pub const OsmNode = struct {
    id: u64,
    lat: f64,
    lon: f64,
};

/// OSM Way representation
pub const OsmWay = struct {
    id: u64,
    node_ids: []const u64,
    tags: std.StringHashMap([]const u8),

    pub fn deinit(self: *OsmWay, allocator: std.mem.Allocator) void {
        allocator.free(self.node_ids);
        // Free tag values before deiniting the HashMap
        var value_iter = self.tags.valueIterator();
        while (value_iter.next()) |value_ptr| {
            allocator.free(value_ptr.*);
        }
        self.tags.deinit();
    }
};

/// OSM data container
pub const OsmData = struct {
    nodes: []const OsmNode,
    ways: []const OsmWay,
    allocator: std.mem.Allocator,

    pub fn deinit(self: *OsmData) void {
        self.allocator.free(self.nodes);
        for (self.ways) |*way| {
            var mut_way = way.*;
            mut_way.deinit(self.allocator);
        }
        self.allocator.free(self.ways);
    }
};

/// Structure to hold way data during parsing
const WayData = struct {
    node_ids: std.ArrayList(u64),
    highway_tag: []const u8,
};

/// Simple OSM XML parser
/// Parses <node> and <way> elements with highway tags
fn parseOsmXml(
    allocator: std.mem.Allocator,
    osm_file_path: []const u8,
    road_types: []const []const u8,
) !OsmData {
    // Open and read the OSM XML file
    const file = try std.fs.cwd().openFile(osm_file_path, .{});
    defer file.close();

    const content = try file.readToEndAlloc(allocator, 200 * 1024 * 1024); // 200MB max
    defer allocator.free(content);

    // Parse nodes and ways
    var nodes_map = std.AutoHashMap(u64, OsmNode).init(allocator);
    defer nodes_map.deinit();

    var ways_list = std.ArrayList(OsmWay){};
    defer {
        for (ways_list.items) |*way| {
            way.deinit(allocator);
        }
        ways_list.deinit(allocator);
    }

    // First pass: collect all ways with highway tags and their node references
    var way_data_map = std.AutoHashMap(u64, WayData).init(allocator);
    defer {
        var iter = way_data_map.iterator();
        while (iter.next()) |entry| {
            entry.value_ptr.node_ids.deinit(allocator);
            allocator.free(entry.value_ptr.highway_tag);
        }
        way_data_map.deinit();
    }

    var needed_nodes = std.AutoHashMap(u64, void).init(allocator);
    defer needed_nodes.deinit();

    // Parse ways first to know which nodes we need
    try parseWays(allocator, content, road_types, &way_data_map, &needed_nodes);

    // Second pass: collect only the nodes we need
    try parseNodes(allocator, content, &needed_nodes, &nodes_map);

    // Build final ways list
    var way_iter = way_data_map.iterator();
    while (way_iter.next()) |entry| {
        const way_id = entry.key_ptr.*;
        const way_data = entry.value_ptr.*;

        // Copy node IDs
        const node_ids_copy = try allocator.alloc(u64, way_data.node_ids.items.len);
        @memcpy(node_ids_copy, way_data.node_ids.items);

        // Create tags map with highway tag
        var tags = std.StringHashMap([]const u8).init(allocator);
        const highway_tag_copy = try allocator.dupe(u8, way_data.highway_tag);
        try tags.put("highway", highway_tag_copy);

        try ways_list.append(allocator, OsmWay{
            .id = way_id,
            .node_ids = node_ids_copy,
            .tags = tags,
        });
    }

    // Convert nodes map to array
    var nodes_list = std.ArrayList(OsmNode){};
    defer nodes_list.deinit(allocator);

    var node_iter = nodes_map.iterator();
    while (node_iter.next()) |entry| {
        try nodes_list.append(allocator, entry.value_ptr.*);
    }

    return OsmData{
        .nodes = try nodes_list.toOwnedSlice(allocator),
        .ways = try ways_list.toOwnedSlice(allocator),
        .allocator = allocator,
    };
}

/// Parse OSM nodes from XML content
fn parseNodes(
    _: std.mem.Allocator,
    content: []const u8,
    needed_nodes: *const std.AutoHashMap(u64, void),
    nodes_map: *std.AutoHashMap(u64, OsmNode),
) !void {
    var pos: usize = 0;
    while (std.mem.indexOfPos(u8, content, pos, "<node ")) |start| {
        pos = start + 6;

        // Find end of node tag
        const end = std.mem.indexOfPos(u8, content, pos, "/>") orelse
                   std.mem.indexOfPos(u8, content, pos, "</node>") orelse continue;

        const node_str = content[start..end];

        // Parse id
        const id = parseAttribute(u64, node_str, "id") orelse continue;

        // Check if we need this node
        if (!needed_nodes.contains(id)) {
            pos = end + 2;
            continue;
        }

        // Parse lat/lon
        const lat = parseAttribute(f64, node_str, "lat") orelse continue;
        const lon = parseAttribute(f64, node_str, "lon") orelse continue;

        try nodes_map.put(id, OsmNode{
            .id = id,
            .lat = lat,
            .lon = lon,
        });

        pos = end + 2;
    }
}

/// Parse OSM ways from XML content
fn parseWays(
    allocator: std.mem.Allocator,
    content: []const u8,
    road_types: []const []const u8,
    way_data_map: anytype,
    needed_nodes: *std.AutoHashMap(u64, void),
) !void {
    var pos: usize = 0;
    while (std.mem.indexOfPos(u8, content, pos, "<way ")) |start| {
        pos = start + 5;

        // Find end of way element
        const end = std.mem.indexOfPos(u8, content, pos, "</way>") orelse continue;
        const way_str = content[start..end];

        // Parse way id
        const way_id = parseAttribute(u64, way_str, "id") orelse continue;

        // Check if this way has a highway tag and get its value
        var highway_value_opt: ?[]const u8 = null;
        var way_pos: usize = 0;
        while (std.mem.indexOfPos(u8, way_str, way_pos, "<tag k=\"highway\"")) |tag_start| {
            way_pos = tag_start + 17;

            // Extract highway value
            const v_start = std.mem.indexOfPos(u8, way_str, way_pos, "v=\"") orelse continue;
            const v_end = std.mem.indexOfPos(u8, way_str, v_start + 3, "\"") orelse continue;
            const highway_value = way_str[v_start + 3..v_end];

            // Check if this road type is in our filter list
            for (road_types) |road_type| {
                if (std.mem.eql(u8, highway_value, road_type)) {
                    highway_value_opt = highway_value;
                    break;
                }
            }

            if (highway_value_opt != null) break;
        }

        if (highway_value_opt == null) {
            pos = end + 6;
            continue;
        }

        // Parse node references
        var node_refs = std.ArrayList(u64){};
        var nd_pos: usize = 0;
        while (std.mem.indexOfPos(u8, way_str, nd_pos, "<nd ref=\"")) |nd_start| {
            nd_pos = nd_start + 9;
            const ref_end = std.mem.indexOfPos(u8, way_str, nd_pos, "\"") orelse continue;
            const ref_str = way_str[nd_pos..ref_end];

            const node_id = std.fmt.parseInt(u64, ref_str, 10) catch continue;
            try node_refs.append(allocator, node_id);
            try needed_nodes.put(node_id, {});

            nd_pos = ref_end + 1;
        }

        if (node_refs.items.len > 0) {
            const highway_tag_copy = try allocator.dupe(u8, highway_value_opt.?);
            try way_data_map.put(way_id, WayData{
                .node_ids = node_refs,
                .highway_tag = highway_tag_copy,
            });
        } else {
            node_refs.deinit(allocator);
        }

        pos = end + 6;
    }
}

/// Parse an attribute value from an XML tag
fn parseAttribute(comptime T: type, tag_str: []const u8, attr_name: []const u8) ?T {
    // Build search pattern: " attr_name="
    var buf: [128]u8 = undefined;
    const search_str = std.fmt.bufPrint(&buf, " {s}=\"", .{attr_name}) catch return null;

    const attr_start = std.mem.indexOf(u8, tag_str, search_str) orelse return null;
    const value_start = attr_start + search_str.len;
    const value_end = std.mem.indexOfPos(u8, tag_str, value_start, "\"") orelse return null;
    const value_str = tag_str[value_start..value_end];

    return switch (T) {
        u64 => std.fmt.parseInt(u64, value_str, 10) catch null,
        f64 => std.fmt.parseFloat(f64, value_str) catch null,
        else => null,
    };
}

/// Extract OSM data from XML file
/// Filters for highway tags and specified road types
pub fn extractOsmData(
    allocator: std.mem.Allocator,
    osm_file_path: []const u8,
    road_types: []const []const u8,
) !OsmData {
    // Try XML parsing first
    if (parseOsmXml(allocator, osm_file_path, road_types)) |osm_data| {
        return osm_data;
    } else |xml_err| {
        // If XML parsing fails, try JSON format
        var nodes_path_buf: [512]u8 = undefined;
        var ways_path_buf: [512]u8 = undefined;

        const nodes_path = try std.fmt.bufPrint(&nodes_path_buf, "{s}.nodes.json", .{osm_file_path});
        const ways_path = try std.fmt.bufPrint(&ways_path_buf, "{s}.ways.json", .{osm_file_path});

        return readOsmDataFromJson(allocator, nodes_path, ways_path, road_types) catch |json_err| {
            // Both failed - report and return empty
            std.debug.print("Warning: Could not load OSM data from {s}\n", .{osm_file_path});
            std.debug.print("  XML error: {}\n", .{xml_err});
            std.debug.print("  JSON error: {}\n", .{json_err});
            std.debug.print("Expected XML format or JSON files: {s} and {s}\n", .{nodes_path, ways_path});
            return OsmData{
                .nodes = &[_]OsmNode{},
                .ways = &[_]OsmWay{},
                .allocator = allocator,
            };
        };
    }
}

/// Read OSM data from JSON (alternative to XML parsing)
/// This is a practical format for development and testing
pub fn readOsmDataFromJson(
    allocator: std.mem.Allocator,
    nodes_path: []const u8,
    ways_path: []const u8,
    road_types: []const []const u8,
) !OsmData {
    // Read nodes file
    const nodes_file = try std.fs.cwd().openFile(nodes_path, .{});
    defer nodes_file.close();

    const nodes_content = try nodes_file.readToEndAlloc(allocator, 100 * 1024 * 1024); // 100MB max
    defer allocator.free(nodes_content);

    // Read ways file
    const ways_file = try std.fs.cwd().openFile(ways_path, .{});
    defer ways_file.close();

    const ways_content = try ways_file.readToEndAlloc(allocator, 100 * 1024 * 1024);
    defer allocator.free(ways_content);

    // Parse JSON
    const parsed_nodes = try std.json.parseFromSlice([]const NodeJson, allocator, nodes_content, .{});
    defer parsed_nodes.deinit();

    const parsed_ways = try std.json.parseFromSlice([]const WayJson, allocator, ways_content, .{});
    defer parsed_ways.deinit();

    // Convert to OsmData
    var nodes = std.ArrayList(OsmNode){};
    defer nodes.deinit(allocator);

    for (parsed_nodes.value) |node_json| {
        try nodes.append(allocator, .{
            .id = node_json.id,
            .lat = node_json.lat,
            .lon = node_json.lon,
        });
    }

    var ways = std.ArrayList(OsmWay){};
    defer ways.deinit(allocator);

    for (parsed_ways.value) |way_json| {
        // Filter by road type
        if (way_json.tags.highway) |highway| {
            var matches = false;
            for (road_types) |rt| {
                if (std.mem.eql(u8, highway, rt)) {
                    matches = true;
                    break;
                }
            }
            if (!matches) continue;

            // Convert tags to hashmap
            var tags = std.StringHashMap([]const u8).init(allocator);
            try tags.put("highway", try allocator.dupe(u8, highway));

            if (way_json.tags.oneway) |oneway| {
                try tags.put("oneway", try allocator.dupe(u8, oneway));
            }

            try ways.append(allocator, .{
                .id = way_json.id,
                .node_ids = try allocator.dupe(u64, way_json.nodes),
                .tags = tags,
            });
        }
    }

    return OsmData{
        .nodes = try nodes.toOwnedSlice(allocator),
        .ways = try ways.toOwnedSlice(allocator),
        .allocator = allocator,
    };
}

/// JSON structures for parsing
const NodeJson = struct {
    id: u64,
    lat: f64,
    lon: f64,
};

const WayJson = struct {
    id: u64,
    nodes: []const u64,
    tags: TagsJson,
};

const TagsJson = struct {
    highway: ?[]const u8 = null,
    oneway: ?[]const u8 = null,
};

/// Write OSM data to JSON (for preprocessing/caching)
pub fn writeOsmDataToJson(
    osm_data: OsmData,
    nodes_path: []const u8,
    ways_path: []const u8,
) !void {
    // Write nodes
    const nodes_file = try std.fs.cwd().createFile(nodes_path, .{});
    defer nodes_file.close();

    var nodes_json = std.ArrayList(NodeJson){};
    defer nodes_json.deinit(osm_data.allocator);

    for (osm_data.nodes) |node| {
        try nodes_json.append(osm_data.allocator, .{
            .id = node.id,
            .lat = node.lat,
            .lon = node.lon,
        });
    }

    try std.json.stringify(nodes_json.items, .{}, nodes_file.writer());

    // Write ways
    const ways_file = try std.fs.cwd().createFile(ways_path, .{});
    defer ways_file.close();

    var ways_json = std.ArrayList(WayJson){};
    defer ways_json.deinit(osm_data.allocator);

    for (osm_data.ways) |way| {
        const highway = way.tags.get("highway") orelse "unknown";
        const oneway = way.tags.get("oneway");

        try ways_json.append(osm_data.allocator, .{
            .id = way.id,
            .nodes = way.node_ids,
            .tags = .{
                .highway = highway,
                .oneway = oneway,
            },
        });
    }

    try std.json.stringify(ways_json.items, .{}, ways_file.writer());
}

/// Create sample test data
pub fn createSampleData(allocator: std.mem.Allocator) !OsmData {
    // Create a small test network
    const nodes = try allocator.alloc(OsmNode, 4);
    nodes[0] = .{ .id = 1, .lat = 45.0, .lon = 126.0 };
    nodes[1] = .{ .id = 2, .lat = 45.01, .lon = 126.0 };
    nodes[2] = .{ .id = 3, .lat = 45.02, .lon = 126.0 };
    nodes[3] = .{ .id = 4, .lat = 45.01, .lon = 126.01 };

    const ways = try allocator.alloc(OsmWay, 2);

    // Way 1: nodes 1 -> 2 -> 3
    var tags1 = std.StringHashMap([]const u8).init(allocator);
    try tags1.put("highway", "primary");
    const node_ids1 = try allocator.alloc(u64, 3);
    node_ids1[0] = 1;
    node_ids1[1] = 2;
    node_ids1[2] = 3;
    ways[0] = .{ .id = 1, .node_ids = node_ids1, .tags = tags1 };

    // Way 2: nodes 2 -> 4
    var tags2 = std.StringHashMap([]const u8).init(allocator);
    try tags2.put("highway", "secondary");
    const node_ids2 = try allocator.alloc(u64, 2);
    node_ids2[0] = 2;
    node_ids2[1] = 4;
    ways[1] = .{ .id = 2, .node_ids = node_ids2, .tags = tags2 };

    return OsmData{
        .nodes = nodes,
        .ways = ways,
        .allocator = allocator,
    };
}
