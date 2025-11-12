const std = @import("std");

pub fn build(b: *std.Build) void {
    const target = b.standardTargetOptions(.{});
    const optimize = b.standardOptimizeOption(.{});

    // Main executable
    const exe = b.addExecutable(.{
        .name = "telchar",
        .root_module = b.createModule(.{
            .root_source_file = b.path("src/main.zig"),
            .target = target,
            .optimize = optimize,
        }),
    });

    // Link libc for c_allocator
    exe.linkLibC();

    b.installArtifact(exe);

    // Run command
    const run_step = b.step("run", "Run the app");
    const run_cmd = b.addRunArtifact(exe);
    run_step.dependOn(&run_cmd.step);
    run_cmd.step.dependOn(b.getInstallStep());

    if (b.args) |args| {
        run_cmd.addArgs(args);
    }

    // Tests
    const test_step = b.step("test", "Run unit tests");

    // Simple modules (no dependencies)
    addSimpleTests(b, test_step, "src/types/geo.zig", target, optimize);
    addSimpleTests(b, test_step, "src/stage5_matching/viterbi.zig", target, optimize);

    // Modules with dependencies need a root test file that imports them
    // For now, just test the simple ones
}

fn addSimpleTests(
    b: *std.Build,
    test_step: *std.Build.Step,
    comptime source_file: []const u8,
    target: std.Build.ResolvedTarget,
    optimize: std.builtin.OptimizeMode,
) void {
    const unit_tests = b.addTest(.{
        .root_module = b.createModule(.{
            .root_source_file = b.path(source_file),
            .target = target,
            .optimize = optimize,
        }),
    });

    const run_unit_tests = b.addRunArtifact(unit_tests);
    test_step.dependOn(&run_unit_tests.step);
}
