const std = @import("std");
const helpers = @import("visualize_helpers.zig");
const zstbi = @import("zstbi");

// Fast PNG renderer using zstbi (stb_image_write)
// Renders network visualization directly to PNG files

const Vertex = struct {
    lon: f64,
    lat: f64,
};

const Edge = struct {
    start_idx: u32,
    end_idx: u32,
};

const TraversalData = helpers.TraversalData;

const BoundingBox = struct {
    lon_min: f64,
    lon_max: f64,
    lat_min: f64,
    lat_max: f64,
};

pub fn main() !void {
    var gpa = std.heap.GeneralPurposeAllocator(.{}){};
    defer _ = gpa.deinit();
    const allocator = gpa.allocator();

    // Initialize zstbi for PNG writing
    zstbi.init(allocator);
    defer zstbi.deinit();

    const args = try std.process.argsAlloc(allocator);
    defer std.process.argsFree(allocator, args);

    const output_dir = if (args.len > 1) args[1] else "../output";

    std.debug.print("=== Telchar Network Visualization (PNG Direct Writer) ===\n\n", .{});
    std.debug.print("Loading data from {s}...\n", .{output_dir});

    // Load vertices
    std.debug.print("  Loading vertices...\n", .{});
    const vertices = try loadVertices(allocator, output_dir);
    defer allocator.free(vertices);
    std.debug.print("  ✓ Loaded {} vertices\n", .{vertices.len});

    // Load edges
    std.debug.print("  Loading edges...\n", .{});
    const edges = try loadEdges(allocator, output_dir);
    defer allocator.free(edges);
    std.debug.print("  ✓ Loaded {} edges\n", .{edges.len});

    // Load traversal time data
    std.debug.print("  Loading traversal time data...\n", .{});
    var traversal_data = try helpers.loadTraversalData(allocator, output_dir, @intCast(edges.len));
    defer traversal_data.deinit();
    std.debug.print("  ✓ Loaded {} time bins\n", .{traversal_data.num_time_bins});

    // Calculate bounding box
    const bbox = calculateBoundingBox(vertices);
    std.debug.print("\n  Bounding box: lon[{d:.4}, {d:.4}], lat[{d:.4}, {d:.4}]\n", .{
        bbox.lon_min,
        bbox.lon_max,
        bbox.lat_min,
        bbox.lat_max,
    });

    // Render all time bins in parallel
    const cpu_count = try std.Thread.getCpuCount();
    std.debug.print("\nRendering {} time bins using {} CPU cores...\n", .{ traversal_data.num_time_bins, cpu_count });

    var progress = std.atomic.Value(usize).init(0);

    const RenderContext = struct {
        time_bin: u32,
        vertices: []const Vertex,
        edges: []const Edge,
        bbox: BoundingBox,
        traversal_data: *const TraversalData,
        allocator: std.mem.Allocator,
        progress: *std.atomic.Value(usize),
        total: u32,
    };

    const renderWorker = struct {
        fn run(ctx: RenderContext) void {
            const png_path = std.fmt.allocPrint(ctx.allocator, "rendered_frames/timebin_{d:0>3}.png", .{ctx.time_bin}) catch return;
            defer ctx.allocator.free(png_path);

            renderTimeBinPNG(std.heap.c_allocator, ctx.vertices, ctx.edges, ctx.bbox, ctx.traversal_data, ctx.time_bin, png_path) catch return;

            const done = ctx.progress.fetchAdd(1, .monotonic) + 1;
            if (done % 20 == 0 or done == ctx.total) {
                std.debug.print("  Progress: {}/{} time bins rendered\n", .{ done, ctx.total });
            }
        }
    }.run;

    // Spawn threads for parallel rendering
    const threads = try allocator.alloc(std.Thread, cpu_count);
    defer allocator.free(threads);

    const bins_per_thread = traversal_data.num_time_bins / @as(u32, @intCast(cpu_count));
    const extra_bins = traversal_data.num_time_bins % @as(u32, @intCast(cpu_count));

    const ThreadWork = struct {
        start: u32,
        end: u32,
        ctx_template: RenderContext,
    };

    var thread_work = try allocator.alloc(ThreadWork, cpu_count);
    defer allocator.free(thread_work);

    var start_bin: u32 = 0;
    for (0..cpu_count) |i| {
        const count = bins_per_thread + (if (i < extra_bins) @as(u32, 1) else 0);
        thread_work[i] = .{
            .start = start_bin,
            .end = start_bin + count,
            .ctx_template = .{
                .time_bin = 0,
                .vertices = vertices,
                .edges = edges,
                .bbox = bbox,
                .traversal_data = &traversal_data,
                .allocator = allocator,
                .progress = &progress,
                .total = traversal_data.num_time_bins,
            },
        };
        start_bin += count;
    }

    const threadMain = struct {
        fn run(work: ThreadWork) void {
            for (work.start..work.end) |bin| {
                var ctx = work.ctx_template;
                ctx.time_bin = @intCast(bin);
                renderWorker(ctx);
            }
        }
    }.run;

    for (threads, thread_work) |*thread, work| {
        thread.* = try std.Thread.spawn(.{}, threadMain, .{work});
    }

    for (threads) |thread| {
        thread.join();
    }

    std.debug.print("\n✓ All {} time bins rendered to rendered_frames/timebin_*.png\n", .{traversal_data.num_time_bins});
    std.debug.print("\nTo view: feh rendered_frames/timebin_*.png\n", .{});
    std.debug.print("Use arrow keys to navigate between time bins\n", .{});
}

fn loadVertices(allocator: std.mem.Allocator, output_dir: []const u8) ![]Vertex {
    const path = try std.fs.path.join(allocator, &[_][]const u8{ output_dir, "vertex.csv" });
    defer allocator.free(path);

    const file = try std.fs.cwd().openFile(path, .{});
    defer file.close();

    var vertices = std.ArrayList(Vertex){};
    defer vertices.deinit(allocator);

    var read_buffer: [8192]u8 = undefined;
    var file_reader = file.reader(&read_buffer);
    const reader = &file_reader.interface;

    // Skip header
    _ = reader.takeDelimiterExclusive('\n') catch |err| switch (err) {
        error.EndOfStream => return try vertices.toOwnedSlice(allocator),
        else => return err,
    };

    // Read vertices
    while (true) {
        const line = reader.takeDelimiterExclusive('\n') catch |err| switch (err) {
            error.EndOfStream => break,
            else => return err,
        };
        var iter = std.mem.splitScalar(u8, line, ',');
        _ = iter.next(); // Skip node_id

        const lon_str = iter.next() orelse continue;
        const lat_str = iter.next() orelse continue;

        const lon = std.fmt.parseFloat(f64, lon_str) catch continue;
        const lat = std.fmt.parseFloat(f64, lat_str) catch continue;

        try vertices.append(allocator, Vertex{ .lon = lon, .lat = lat });
    }

    return try vertices.toOwnedSlice(allocator);
}

fn loadEdges(allocator: std.mem.Allocator, output_dir: []const u8) ![]Edge {
    const path = try std.fs.path.join(allocator, &[_][]const u8{ output_dir, "edge_connections.csv" });
    defer allocator.free(path);

    const file = try std.fs.cwd().openFile(path, .{});
    defer file.close();

    var edges = std.ArrayList(Edge){};
    defer edges.deinit(allocator);

    var read_buffer: [8192]u8 = undefined;
    var file_reader = file.reader(&read_buffer);
    const reader = &file_reader.interface;

    // Skip header
    _ = reader.takeDelimiterExclusive('\n') catch |err| switch (err) {
        error.EndOfStream => return try edges.toOwnedSlice(allocator),
        else => return err,
    };

    // Read edges
    while (true) {
        const line = reader.takeDelimiterExclusive('\n') catch |err| switch (err) {
            error.EndOfStream => break,
            else => return err,
        };
        var iter = std.mem.splitScalar(u8, line, ',');
        _ = iter.next(); // Skip edge_id

        const start_str = iter.next() orelse continue;
        const end_str = iter.next() orelse continue;

        const start_idx = std.fmt.parseInt(u32, start_str, 10) catch continue;
        const end_idx = std.fmt.parseInt(u32, end_str, 10) catch continue;

        try edges.append(allocator, Edge{ .start_idx = start_idx, .end_idx = end_idx });
    }

    return try edges.toOwnedSlice(allocator);
}

fn calculateBoundingBox(vertices: []const Vertex) BoundingBox {
    var bbox = BoundingBox{
        .lon_min = vertices[0].lon,
        .lon_max = vertices[0].lon,
        .lat_min = vertices[0].lat,
        .lat_max = vertices[0].lat,
    };

    for (vertices) |v| {
        if (v.lon < bbox.lon_min) bbox.lon_min = v.lon;
        if (v.lon > bbox.lon_max) bbox.lon_max = v.lon;
        if (v.lat < bbox.lat_min) bbox.lat_min = v.lat;
        if (v.lat > bbox.lat_max) bbox.lat_max = v.lat;
    }

    return bbox;
}

fn renderTimeBinPNG(
    allocator: std.mem.Allocator,
    vertices: []const Vertex,
    edges: []const Edge,
    bbox: BoundingBox,
    traversal_data: *const TraversalData,
    time_bin: u32,
    output_path: []const u8,
) !void {
    // Create output directory
    try std.fs.cwd().makePath("rendered_frames");

    // Image dimensions (very large for detail)
    const width: u32 = 16384; // 16K width
    const height: u32 = 12288; // 12K height

    // Allocate framebuffer (RGB)
    const pixel_count = width * height;
    const pixels = try allocator.alloc(u8, pixel_count * 3);
    defer allocator.free(pixels);

    // Fill with background color (dark gray)
    @memset(pixels, 32);

    // Calculate scale
    const lon_range = bbox.lon_max - bbox.lon_min;
    const lat_range = bbox.lat_max - bbox.lat_min;
    const margin: f64 = 100;
    const scale_x = (@as(f64, @floatFromInt(width)) - 2 * margin) / lon_range;
    const scale_y = (@as(f64, @floatFromInt(height)) - 2 * margin) / lat_range;
    const scale = @min(scale_x, scale_y);

    // Helper to convert geo coords to pixel coords
    const toPixelX = struct {
        fn f(lon: f64, lon_min: f64, s: f64, m: f64) u32 {
            return @intFromFloat((lon - lon_min) * s + m);
        }
    }.f;

    const toPixelY = struct {
        fn f(lat: f64, lat_max: f64, lat_min: f64, s: f64, m: f64, h: u32) u32 {
            const y = @as(f64, @floatFromInt(h)) - ((lat - (lat_max - (lat_max - lat_min))) * s + m);
            return @intFromFloat(y);
        }
    }.f;

    // Calculate min/max for THIS time bin only
    const time_data = traversal_data.times[time_bin];
    const stats = helpers.getTimeBinStats(time_data);

    // Draw edges with color coding based on traversal time
    for (edges, 0..) |edge, edge_id| {
        if (edge.start_idx >= vertices.len or edge.end_idx >= vertices.len) continue;
        if (edge_id >= time_data.len) continue;

        const v1 = vertices[edge.start_idx];
        const v2 = vertices[edge.end_idx];

        const x1 = toPixelX(v1.lon, bbox.lon_min, scale, margin);
        const y1 = toPixelY(v1.lat, bbox.lat_max, bbox.lat_min, scale, margin, height);
        const x2 = toPixelX(v2.lon, bbox.lon_min, scale, margin);
        const y2 = toPixelY(v2.lat, bbox.lat_max, bbox.lat_min, scale, margin, height);

        // Get color based on traversal time (using per-bin normalization)
        const traversal_time = time_data[edge_id];
        const color = helpers.getColorForTime(traversal_time, stats.min_time, stats.max_time);

        drawLine(pixels, width, height, x1, y1, x2, y2, color.r, color.g, color.b);
    }

    // Draw legend in top-right corner
    drawLegend(pixels, width, height, time_bin, stats.min_time, stats.max_time);

    // Write PNG file directly using zstbi
    const output_path_z = try allocator.dupeZ(u8, output_path);
    defer allocator.free(output_path_z);

    // Create zstbi Image from our pixel buffer
    var image = zstbi.Image{
        .data = pixels,
        .width = @intCast(width),
        .height = @intCast(height),
        .num_components = 3, // RGB
        .bytes_per_component = 1, // 8-bit per channel
        .bytes_per_row = @intCast(width * 3),
        .is_hdr = false,
    };

    // Write to PNG file
    try image.writeToFile(output_path_z, .png);
}

fn drawLegend(pixels: []u8, width: u32, height: u32, time_bin: u32, min_time: f32, max_time: f32) void {
    // Draw background box in top-right corner (100x bigger = 5x the 20x)
    const box_width: u32 = 6000;
    const box_height: u32 = 2500;
    const box_x: u32 = width - box_width - 200;
    const box_y: u32 = 200;

    // Draw dark background
    for (box_y..box_y + box_height) |y| {
        for (box_x..box_x + box_width) |x| {
            if (x >= width or y >= height) continue;
            const idx = (y * width + x) * 3;
            pixels[idx] = 40;
            pixels[idx + 1] = 40;
            pixels[idx + 2] = 40;
        }
    }

    // Format text lines
    var buffer1: [128]u8 = undefined;
    var buffer2: [128]u8 = undefined;
    var buffer3: [128]u8 = undefined;

    const line1 = std.fmt.bufPrint(&buffer1, "Time Bin: {d:0>3} (Logarithmic)", .{time_bin}) catch "Time Bin";
    const line2 = std.fmt.bufPrint(&buffer2, "Min: {d:.1}s (BLUE)", .{min_time}) catch "Min";
    const line3 = std.fmt.bufPrint(&buffer3, "Max: {d:.1}s (RED)", .{max_time}) catch "Max";

    // Draw text with bitmap font (scale 25x for very large legend)
    const scale: u32 = 25;
    const text_x: u32 = box_x + 200;
    drawText(pixels, width, height, line1, text_x, box_y + 250, scale, 255, 255, 255);
    drawText(pixels, width, height, line2, text_x, box_y + 750, scale, 0, 128, 255);  // Blue
    drawText(pixels, width, height, line3, text_x, box_y + 1250, scale, 255, 0, 0);

    // Draw color gradient bar with new color scheme (Blue -> Cyan -> Yellow -> Red)
    const scale_y: u32 = box_y + 1800;
    const scale_width: u32 = 5000;
    const scale_height: u32 = 500;
    const scale_x: u32 = box_x + 200;

    for (0..scale_width) |i| {
        const normalized = @as(f32, @floatFromInt(i)) / @as(f32, @floatFromInt(scale_width));

        // Match the new color scheme from getColorForTime
        var r: u8 = 0;
        var g: u8 = 0;
        var b: u8 = 0;

        if (normalized < 0.33) {
            // Blue to Cyan
            const t = normalized / 0.33;
            r = 0;
            g = @intFromFloat(t * 255.0);
            b = 255;
        } else if (normalized < 0.66) {
            // Cyan to Yellow
            const t = (normalized - 0.33) / 0.33;
            r = @intFromFloat(t * 255.0);
            g = 255;
            b = @intFromFloat((1.0 - t) * 255.0);
        } else {
            // Yellow to Red
            const t = (normalized - 0.66) / 0.34;
            r = 255;
            g = @intFromFloat((1.0 - t) * 255.0);
            b = 0;
        }

        const bar_x = scale_x + @as(u32, @intCast(i));
        drawFilledRect(pixels, width, height, bar_x, scale_y, 1, scale_height, r, g, b);
    }
}

fn drawText(pixels: []u8, width: u32, height: u32, text: []const u8, x: u32, y: u32, scale: u32, r: u8, g: u8, b: u8) void {
    var cursor_x = x;
    for (text) |char| {
        drawChar(pixels, width, height, char, cursor_x, y, scale, r, g, b);
        cursor_x += (6 * scale); // 5 pixels + 1 space between chars
    }
}

fn drawChar(pixels: []u8, width: u32, height: u32, char: u8, x: u32, y: u32, scale: u32, r: u8, g: u8, b: u8) void {
    const font_data = getCharBitmap(char);

    // Draw 5x7 bitmap scaled up
    for (0..7) |row| {
        for (0..5) |col| {
            const bit = (font_data[row] >> @intCast(4 - col)) & 1;
            if (bit == 1) {
                // Draw scaled pixel
                for (0..scale) |dy| {
                    for (0..scale) |dx| {
                        const px = x + @as(u32, @intCast(col)) * scale + @as(u32, @intCast(dx));
                        const py = y + @as(u32, @intCast(row)) * scale + @as(u32, @intCast(dy));
                        if (px < width and py < height) {
                            const idx = (py * width + px) * 3;
                            pixels[idx] = r;
                            pixels[idx + 1] = g;
                            pixels[idx + 2] = b;
                        }
                    }
                }
            }
        }
    }
}

// Simple 5x7 bitmap font (each row is a byte, 1 = pixel on)
fn getCharBitmap(char: u8) [7]u8 {
    return switch (char) {
        '0' => [7]u8{ 0b01110, 0b10001, 0b10011, 0b10101, 0b11001, 0b10001, 0b01110 },
        '1' => [7]u8{ 0b00100, 0b01100, 0b00100, 0b00100, 0b00100, 0b00100, 0b01110 },
        '2' => [7]u8{ 0b01110, 0b10001, 0b00001, 0b00010, 0b00100, 0b01000, 0b11111 },
        '3' => [7]u8{ 0b01110, 0b10001, 0b00001, 0b00110, 0b00001, 0b10001, 0b01110 },
        '4' => [7]u8{ 0b00010, 0b00110, 0b01010, 0b10010, 0b11111, 0b00010, 0b00010 },
        '5' => [7]u8{ 0b11111, 0b10000, 0b11110, 0b00001, 0b00001, 0b10001, 0b01110 },
        '6' => [7]u8{ 0b01110, 0b10001, 0b10000, 0b11110, 0b10001, 0b10001, 0b01110 },
        '7' => [7]u8{ 0b11111, 0b00001, 0b00010, 0b00100, 0b01000, 0b01000, 0b01000 },
        '8' => [7]u8{ 0b01110, 0b10001, 0b10001, 0b01110, 0b10001, 0b10001, 0b01110 },
        '9' => [7]u8{ 0b01110, 0b10001, 0b10001, 0b01111, 0b00001, 0b10001, 0b01110 },
        'A' => [7]u8{ 0b01110, 0b10001, 0b10001, 0b11111, 0b10001, 0b10001, 0b10001 },
        'B' => [7]u8{ 0b11110, 0b10001, 0b10001, 0b11110, 0b10001, 0b10001, 0b11110 },
        'C' => [7]u8{ 0b01110, 0b10001, 0b10000, 0b10000, 0b10000, 0b10001, 0b01110 },
        'D' => [7]u8{ 0b11110, 0b10001, 0b10001, 0b10001, 0b10001, 0b10001, 0b11110 },
        'E' => [7]u8{ 0b11111, 0b10000, 0b10000, 0b11110, 0b10000, 0b10000, 0b11111 },
        'G' => [7]u8{ 0b01110, 0b10001, 0b10000, 0b10111, 0b10001, 0b10001, 0b01110 },
        'I' => [7]u8{ 0b01110, 0b00100, 0b00100, 0b00100, 0b00100, 0b00100, 0b01110 },
        'M' => [7]u8{ 0b10001, 0b11011, 0b10101, 0b10101, 0b10001, 0b10001, 0b10001 },
        'N' => [7]u8{ 0b10001, 0b11001, 0b10101, 0b10011, 0b10001, 0b10001, 0b10001 },
        'R' => [7]u8{ 0b11110, 0b10001, 0b10001, 0b11110, 0b10100, 0b10010, 0b10001 },
        'T' => [7]u8{ 0b11111, 0b00100, 0b00100, 0b00100, 0b00100, 0b00100, 0b00100 },
        'a' => [7]u8{ 0b00000, 0b00000, 0b01110, 0b00001, 0b01111, 0b10001, 0b01111 },
        'e' => [7]u8{ 0b00000, 0b00000, 0b01110, 0b10001, 0b11111, 0b10000, 0b01110 },
        'i' => [7]u8{ 0b00100, 0b00000, 0b01100, 0b00100, 0b00100, 0b00100, 0b01110 },
        'm' => [7]u8{ 0b00000, 0b00000, 0b11010, 0b10101, 0b10101, 0b10001, 0b10001 },
        'n' => [7]u8{ 0b00000, 0b00000, 0b10110, 0b11001, 0b10001, 0b10001, 0b10001 },
        's' => [7]u8{ 0b00000, 0b00000, 0b01111, 0b10000, 0b01110, 0b00001, 0b11110 },
        'x' => [7]u8{ 0b00000, 0b00000, 0b10001, 0b01010, 0b00100, 0b01010, 0b10001 },
        ':' => [7]u8{ 0b00000, 0b00100, 0b00100, 0b00000, 0b00100, 0b00100, 0b00000 },
        '.' => [7]u8{ 0b00000, 0b00000, 0b00000, 0b00000, 0b00000, 0b00100, 0b00100 },
        '(' => [7]u8{ 0b00010, 0b00100, 0b01000, 0b01000, 0b01000, 0b00100, 0b00010 },
        ')' => [7]u8{ 0b01000, 0b00100, 0b00010, 0b00010, 0b00010, 0b00100, 0b01000 },
        '|' => [7]u8{ 0b00100, 0b00100, 0b00100, 0b00100, 0b00100, 0b00100, 0b00100 },
        ' ' => [7]u8{ 0b00000, 0b00000, 0b00000, 0b00000, 0b00000, 0b00000, 0b00000 },
        else => [7]u8{ 0b11111, 0b10001, 0b10001, 0b10001, 0b10001, 0b10001, 0b11111 }, // Box for unknown
    };
}

fn drawFilledRect(pixels: []u8, width: u32, height: u32, x: u32, y: u32, w: u32, h: u32, r: u8, g: u8, b: u8) void {
    for (y..y + h) |py| {
        for (x..x + w) |px| {
            if (px >= width or py >= height) continue;
            const idx = (py * width + px) * 3;
            pixels[idx] = r;
            pixels[idx + 1] = g;
            pixels[idx + 2] = b;
        }
    }
}

fn drawLine(pixels: []u8, width: u32, height: u32, x1: u32, y1: u32, x2: u32, y2: u32, r: u8, g: u8, b: u8) void {
    // Bresenham's line algorithm
    const dx = if (x2 > x1) x2 - x1 else x1 - x2;
    const dy = if (y2 > y1) y2 - y1 else y1 - y2;
    const sx: i32 = if (x1 < x2) 1 else -1;
    const sy: i32 = if (y1 < y2) 1 else -1;
    var err: i32 = @as(i32, @intCast(dx)) - @as(i32, @intCast(dy));

    var x: i32 = @intCast(x1);
    var y: i32 = @intCast(y1);
    const x2i: i32 = @intCast(x2);
    const y2i: i32 = @intCast(y2);

    while (true) {
        // Set pixel
        if (x >= 0 and x < width and y >= 0 and y < height) {
            const xu: u32 = @intCast(x);
            const yu: u32 = @intCast(y);
            const idx = (yu * width + xu) * 3;
            pixels[idx] = r;
            pixels[idx + 1] = g;
            pixels[idx + 2] = b;
        }

        if (x == x2i and y == y2i) break;

        const e2 = 2 * err;
        if (e2 > -@as(i32, @intCast(dy))) {
            err -= @as(i32, @intCast(dy));
            x += sx;
        }
        if (e2 < @as(i32, @intCast(dx))) {
            err += @as(i32, @intCast(dx));
            y += sy;
        }
    }
}

fn renderSVG(
    _: std.mem.Allocator,
    vertices: []const Vertex,
    edges: []const Edge,
    bbox: BoundingBox,
    output_path: []const u8,
) !void {
    // Create output directory
    try std.fs.cwd().makePath("rendered_frames");

    const file = try std.fs.cwd().createFile(output_path, .{});
    defer file.close();

    var write_buffer: [8192]u8 = undefined;
    var file_writer = file.writer(&write_buffer);
    const writer = &file_writer.interface;

    // SVG dimensions
    const width: f64 = 1920;
    const height: f64 = 1080;
    const margin: f64 = 50;

    // Calculate scale
    const lon_range = bbox.lon_max - bbox.lon_min;
    const lat_range = bbox.lat_max - bbox.lat_min;
    const scale_x = (width - 2 * margin) / lon_range;
    const scale_y = (height - 2 * margin) / lat_range;
    const scale = @min(scale_x, scale_y);

    // Helper to convert geo coords to SVG coords
    const toX = struct {
        fn f(lon: f64, min: f64, s: f64, m: f64) f64 {
            return (lon - min) * s + m;
        }
    }.f;

    const toY = struct {
        fn f(lat: f64, lat_max: f64, s: f64, m: f64, h: f64, lat_min: f64) f64 {
            return h - ((lat - (lat_max - (lat_max - lat_min))) * s + m);
        }
    }.f;

    // Write SVG header
    try writer.print(
        \\<?xml version="1.0" encoding="UTF-8"?>
        \\<svg xmlns="http://www.w3.org/2000/svg" width="{d:.0}" height="{d:.0}" viewBox="0 0 {d:.0} {d:.0}">
        \\  <rect width="100%" height="100%" fill="#1a1a1a"/>
        \\  <g id="edges" stroke="#888888" stroke-width="0.5" opacity="0.7">
        \\
    , .{ width, height, width, height });

    // Draw edges
    for (edges) |edge| {
        if (edge.start_idx >= vertices.len or edge.end_idx >= vertices.len) continue;

        const v1 = vertices[edge.start_idx];
        const v2 = vertices[edge.end_idx];

        const x1 = toX(v1.lon, bbox.lon_min, scale, margin);
        const y1 = toY(v1.lat, bbox.lat_max, scale, margin, height, bbox.lat_min);
        const x2 = toX(v2.lon, bbox.lon_min, scale, margin);
        const y2 = toY(v2.lat, bbox.lat_max, scale, margin, height, bbox.lat_min);

        try writer.print("    <line x1=\"{d:.2}\" y1=\"{d:.2}\" x2=\"{d:.2}\" y2=\"{d:.2}\"/>\n", .{ x1, y1, x2, y2 });
    }

    // Write SVG footer
    try writer.writeAll(
        \\  </g>
        \\  <text x="10" y="30" font-family="Arial" font-size="24" fill="white">Telchar Road Network</text>
        \\</svg>
        \\
    );
}
