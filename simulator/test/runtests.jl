using Test
using MammographySimulation

const SYNTHETIC_ROI_PIXELS = [
    0 0 0 0 0
    0 80 80 80 0
    0 80 0 255 0
    0 80 80 80 0
    0 0 0 0 0
]

function synthetic_roi_image()
    return PgmImage(5, 5, 255, SYNTHETIC_ROI_PIXELS)
end

function empty_mpc_space(width = 10, height = 10)
    return SimulationSpace(
        width,
        height,
        1.0,
        Float64(width),
        Float64(height),
        1,
        255,
        1,
        255,
        trues(height, width),
        zeros(Float64, height, width),
        SimulationObstacle[],
    )
end

function central_cylinder_space()
    space = empty_mpc_space(10, 10)
    obstacle = SimulationObstacle(
        4,
        4,
        5.0,
        5.0,
        0.5,
        0,
        0.0,
        1.0,
        1.0,
        true,
    )

    return SimulationSpace(
        space.width,
        space.height,
        space.cell_length,
        space.lx,
        space.ly,
        space.lz,
        space.max_gray,
        space.tissue_threshold,
        space.obstacle_threshold,
        space.domain_mask,
        space.normalized_intensities,
        [obstacle],
    )
end

function vertical_breast_domain_space()
    domain_mask = falses(3, 4)
    domain_mask[:, 1:2] .= true

    return SimulationSpace(
        4,
        3,
        1.0,
        4.0,
        3.0,
        1,
        255,
        1,
        255,
        domain_mask,
        zeros(Float64, 3, 4),
        SimulationObstacle[],
    )
end

@testset "PGM reader" begin
    mktempdir() do dir
        ascii_path = joinpath(dir, "ascii.pgm")
        binary_path = joinpath(dir, "binary.pgm")
        invalid_path = joinpath(dir, "invalid.pgm")

        write(
            ascii_path,
            """
            P2
            # PGM ASCII de prueba
            2 2
            255
            0 10
            20 30
            """,
        )

        write(binary_path, UInt8[
            UInt8('P'), UInt8('5'), UInt8('\n'),
            UInt8('2'), UInt8(' '), UInt8('2'), UInt8('\n'),
            UInt8('2'), UInt8('5'), UInt8('5'), UInt8('\n'),
            0x00, 0x80, 0xff, 0x40,
        ])

        write(invalid_path, "P3\n1 1\n255\n0 0 0\n")

        ascii_image = read_pgm(ascii_path)
        binary_image = read_pgm(binary_path)

        @test ascii_image.width == 2
        @test ascii_image.height == 2
        @test ascii_image.max_gray == 255
        @test ascii_image.pixels == [0 10; 20 30]

        @test binary_image.width == 2
        @test binary_image.height == 2
        @test binary_image.max_gray == 255
        @test binary_image.pixels == [0 128; 255 64]

        @test_throws ArgumentError read_pgm(invalid_path)
        @test_throws ArgumentError read_pgm(joinpath(dir, "missing.pgm"))
    end
end

@testset "Simulation space builder" begin
    image = synthetic_roi_image()
    space = build_simulation_space(image)

    @test space.width == 5
    @test space.height == 5
    @test space.cell_length == 1.0
    @test space.lx == 5.0
    @test space.ly == 5.0
    @test space.lz == 1
    @test space.max_gray == 255
    @test space.tissue_threshold == 8
    @test space.obstacle_threshold == 217
    @test size(space.domain_mask) == (5, 5)
    @test size(space.normalized_intensities) == (5, 5)
    @test space.normalized_intensities[1, 1] == 0.0
    @test space.normalized_intensities[3, 4] == 1.0
    @test count(space.domain_mask) == 9
    @test !space.domain_mask[1, 1]
    @test space.domain_mask[3, 3]
    @test length(space.obstacles) == 9

    bright_obstacle = only([
        obstacle for obstacle in space.obstacles
        if obstacle.x == 3 && obstacle.y == 2
    ])
    dark_obstacle = only([
        obstacle for obstacle in space.obstacles
        if obstacle.x == 2 && obstacle.y == 2
    ])
    medium_obstacle = only([
        obstacle for obstacle in space.obstacles
        if obstacle.x == 1 && obstacle.y == 1
    ])

    @test bright_obstacle.center_x == 3.5
    @test bright_obstacle.center_y == 2.5
    @test bright_obstacle.center_z == 0.5
    @test bright_obstacle.intensity == 255
    @test bright_obstacle.height == 1.0
    @test !bright_obstacle.preliminary_blocking
    @test isapprox(bright_obstacle.radius, 0.001953125)
    @test dark_obstacle.intensity == 0
    @test dark_obstacle.preliminary_blocking
    @test isapprox(dark_obstacle.radius, 0.5)
    @test medium_obstacle.intensity == 80
    @test medium_obstacle.preliminary_blocking
    @test isapprox(medium_obstacle.radius, 0.34375)

    @test_throws ArgumentError build_simulation_space(image; tissue_threshold = 0)
    @test_throws ArgumentError build_simulation_space(image; obstacle_threshold = 0)
    @test_throws ArgumentError build_simulation_space(PgmImage(2, 2, 255, zeros(Int, 2, 2)))
end

@testset "Minimal sequential simulation" begin
    space = build_simulation_space(synthetic_roi_image())

    result_a = run_minimal_simulation(
        space;
        seed = 7,
        steps = 5,
        particle_density = 0.5,
    )
    result_b = run_minimal_simulation(
        space;
        seed = 7,
        steps = 5,
        particle_density = 0.5,
    )

    positions_a = [(particle.id, particle.x, particle.y) for particle in result_a.particles]
    positions_b = [(particle.id, particle.x, particle.y) for particle in result_b.particles]

    @test result_a.steps == 5
    @test result_a.seed == 7
    @test result_a.particle_density == 0.5
    @test length(result_a.particles) == 1
    @test result_a.attempted_moves == 5
    @test result_a.collision_count >= 0
    @test all(particle -> space.domain_mask[particle.y + 1, particle.x + 1], result_a.particles)
    @test sum(result_a.visit_counts[.!space.domain_mask]) == 0
    @test result_a.visit_counts == result_b.visit_counts
    @test positions_a == positions_b

    empty_result = run_minimal_simulation(
        space;
        seed = 7,
        steps = 5,
        particle_density = 0.0,
    )

    @test isempty(empty_result.particles)
    @test empty_result.attempted_moves == 0
    @test sum(empty_result.visit_counts) == 0
    @test_throws ArgumentError run_minimal_simulation(space; steps = -1)
    @test_throws ArgumentError run_minimal_simulation(space; particle_density = 1.1)
end

@testset "MPC base configuration" begin
    mktempdir() do dir
        input_path = joinpath(dir, "simulation_input.pgm")
        output_dir = joinpath(dir, "results")

        write(input_path, "P2\n1 1\n255\n120\n")

        config = parse_cli_args([
            "--input",
            input_path,
            "--output",
            output_dir,
            "--seed",
            "99",
            "--steps",
            "500",
            "--n0",
            "10",
            "--mass",
            "1",
            "--kbt",
            "1",
            "--tau",
            "1",
            "--rotation-angle",
            string(pi / 2),
            "--realizations",
            "2",
            "--labeled-particles",
            "15",
            "--correlation-initial-times",
            "3",
            "--output-times",
            "0,100,500",
            "--grid-shift",
            "false",
        ])

        @test config.input_path == input_path
        @test config.output_dir == output_dir
        @test config.seed == 99
        @test config.steps == 500
        @test config.mpc_config.input_role == "confirmed_roi_pgm"
        @test config.mpc_config.cell_length == 1.0
        @test config.mpc_config.lz == 1
        @test config.mpc_config.n0 == 10.0
        @test config.mpc_config.mass == 1.0
        @test config.mpc_config.kbt == 1.0
        @test config.mpc_config.tau == 1.0
        @test isapprox(config.mpc_config.rotation_angle, pi / 2)
        @test config.mpc_config.realizations == 2
        @test config.mpc_config.labeled_particles == 15
        @test config.mpc_config.correlation_initial_times == 3
        @test config.mpc_config.output_times == [0, 100, 500]
        @test !config.mpc_config.grid_shift_enabled
        @test occursin("disabled_initially", config.mpc_config.grid_shift_decision)

        default_config = parse_cli_args([
            "--input",
            input_path,
            "--output",
            output_dir,
        ])

        @test default_config.mpc_config.labeled_particles == 500

        @test_throws ArgumentError parse_cli_args([
            "--input",
            input_path,
            "--output",
            output_dir,
            "--n0",
            "0",
        ])
        @test_throws ArgumentError parse_cli_args([
            "--input",
            input_path,
            "--output",
            output_dir,
            "--correlation-initial-times",
            "0",
        ])
        @test_throws ArgumentError parse_cli_args([
            "--input",
            input_path,
            "--output",
            output_dir,
            "--output-times",
            "0,-1",
        ])
    end
end

@testset "MPC continuous particle initialization" begin
    space = build_simulation_space(synthetic_roi_image())
    config = MpcModelConfig(
        n0 = 1.0,
        mass = 2.0,
        kbt = 8.0,
        labeled_particles = 3,
    )

    initialization_a = initialize_mpc_particles(space, config; seed = 21)
    initialization_b = initialize_mpc_particles(space, config; seed = 21)

    particle_state_a = [
        (
            particle.id,
            particle.x,
            particle.y,
            particle.z,
            particle.vx,
            particle.vy,
            particle.vz,
            particle.labeled,
        )
        for particle in initialization_a.particles
    ]
    particle_state_b = [
        (
            particle.id,
            particle.x,
            particle.y,
            particle.z,
            particle.vx,
            particle.vy,
            particle.vz,
            particle.labeled,
        )
        for particle in initialization_b.particles
    ]

    @test initialization_a.seed == 21
    @test initialization_a.target_particle_count == 9
    @test initialization_a.domain_volume == 9.0
    @test initialization_a.velocity_sigma == 2.0
    @test length(initialization_a.particles) == 9
    @test particle_state_a == particle_state_b
    @test count(particle -> particle.labeled, initialization_a.particles) == 3
    @test all(particle -> particle.mass == 2.0, initialization_a.particles)
    @test all(particle -> particle.species == "fluid", initialization_a.particles)

    capped_config = MpcModelConfig(
        n0 = 1.0,
        labeled_particles = 500,
    )
    capped_initialization = initialize_mpc_particles(space, capped_config; seed = 22)

    @test length(capped_initialization.particles) == 9
    @test count(particle -> particle.labeled, capped_initialization.particles) == 9

    for particle in initialization_a.particles
        @test 0.0 <= particle.x < space.lx
        @test 0.0 <= particle.y < space.ly
        @test 0.0 <= particle.z < space.lz

        cell_x = floor(Int, particle.x / space.cell_length)
        cell_y = floor(Int, particle.y / space.cell_length)

        @test space.domain_mask[cell_y + 1, cell_x + 1]

        obstacle = only([
            obstacle for obstacle in space.obstacles
            if obstacle.x == cell_x && obstacle.y == cell_y
        ])
        dx = particle.x - obstacle.center_x
        dy = particle.y - obstacle.center_y

        @test dx^2 + dy^2 >= obstacle.radius^2
    end
end

@testset "MPC free streaming, periodic borders and cylinder bounce" begin
    no_obstacle_space = empty_mpc_space()
    config = MpcModelConfig(tau = 0.5)
    initialization = MpcParticleInitialization(
        1,
        1,
        100.0,
        1.0,
        0,
        [
            MpcParticle(
                1,
                1.0,
                1.0,
                0.25,
                2.0,
                3.0,
                0.0,
                1.0,
                "fluid",
                false,
            ),
        ],
    )

    streamed = stream_mpc_particles(initialization, no_obstacle_space, config; steps = 1)
    particle = streamed.particles[1]

    @test streamed.obstacle_collision_count == 0
    @test streamed.domain_boundary_collision_count == 0
    @test streamed.boundary_crossing_count_x == 0
    @test streamed.boundary_crossing_count_y == 0
    @test isapprox(particle.x, 2.0)
    @test isapprox(particle.y, 2.5)
    @test isapprox(particle.z, 0.25)
    @test isapprox(particle.vx, 2.0)
    @test isapprox(particle.vy, 3.0)

    periodic_initialization = MpcParticleInitialization(
        1,
        1,
        100.0,
        1.0,
        0,
        [
            MpcParticle(
                1,
                9.8,
                5.0,
                0.25,
                1.0,
                0.0,
                0.0,
                1.0,
                "fluid",
                false,
            ),
        ],
    )

    periodic_streamed = stream_mpc_particles(
        periodic_initialization,
        no_obstacle_space,
        config;
        steps = 1,
    )
    periodic_particle = periodic_streamed.particles[1]

    @test periodic_streamed.boundary_crossing_count_x == 1
    @test periodic_streamed.boundary_crossing_count_y == 0
    @test periodic_streamed.domain_boundary_collision_count == 0
    @test isapprox(periodic_particle.x, 0.3; atol = 1.0e-12)
    @test isapprox(periodic_particle.y, 5.0)
    @test isapprox(periodic_particle.vx, 1.0)

    bounce_space = central_cylinder_space()
    bounce_config = MpcModelConfig(tau = 1.0)
    bounce_initialization = MpcParticleInitialization(
        1,
        1,
        100.0,
        1.0,
        0,
        [
            MpcParticle(
                1,
                3.0,
                5.0,
                0.5,
                4.0,
                0.0,
                0.0,
                1.0,
                "fluid",
                false,
            ),
        ],
    )

    bounced = stream_mpc_particles(bounce_initialization, bounce_space, bounce_config; steps = 1)
    bounced_particle = bounced.particles[1]

    @test bounced.obstacle_collision_count == 1
    @test bounced.domain_boundary_collision_count == 0
    @test bounced.boundary_crossing_count_x == 0
    @test isapprox(bounced_particle.x, 1.0; atol = 1.0e-8)
    @test isapprox(bounced_particle.y, 5.0; atol = 1.0e-8)
    @test isapprox(bounced_particle.vx, -4.0)
    @test isapprox(bounced_particle.vy, -0.0)

    masked_space = vertical_breast_domain_space()
    masked_config = MpcModelConfig(tau = 1.0)
    masked_initialization = MpcParticleInitialization(
        1,
        1,
        6.0,
        1.0,
        0,
        [
            MpcParticle(
                1,
                1.8,
                1.0,
                0.5,
                1.0,
                0.0,
                0.0,
                1.0,
                "fluid",
                false,
            ),
        ],
    )

    masked_streamed = stream_mpc_particles(masked_initialization, masked_space, masked_config; steps = 1)
    masked_particle = masked_streamed.particles[1]

    @test masked_streamed.obstacle_collision_count == 0
    @test masked_streamed.domain_boundary_collision_count == 1
    @test isapprox(masked_particle.x, 1.8)
    @test isapprox(masked_particle.y, 1.0)
    @test isapprox(masked_particle.vx, -1.0)
    @test masked_space.domain_mask[2, 2]
end

@testset "MPC multiparticle collision by cells" begin
    space = empty_mpc_space()
    config = MpcModelConfig(rotation_angle = pi / 2)
    streaming = MpcStreamingResult(
        1,
        1.0,
        3,
        0,
        0,
        0,
        0,
        1,
        [
            MpcParticle(1, 1.2, 1.2, 0.5, 1.0, 0.0, 0.0, 1.0, "fluid", false),
            MpcParticle(2, 1.8, 1.7, 0.5, -1.0, 0.0, 0.0, 1.0, "fluid", false),
            MpcParticle(3, 4.2, 4.2, 0.5, 2.0, 3.0, 0.0, 1.0, "fluid", false),
        ],
    )

    collision_a = collide_mpc_particles(streaming, space, config; seed = 5)
    collision_b = collide_mpc_particles(streaming, space, config; seed = 5)

    velocities_a = [(particle.vx, particle.vy, particle.vz) for particle in collision_a.particles]
    velocities_b = [(particle.vx, particle.vy, particle.vz) for particle in collision_b.particles]
    collision_cell = only([
        cell for cell in collision_a.cell_statistics
        if cell.cell_x == 1 && cell.cell_y == 1
    ])
    singleton_cell = only([
        cell for cell in collision_a.cell_statistics
        if cell.cell_x == 4 && cell.cell_y == 4
    ])

    @test collision_a.seed == 5
    @test collision_a.particle_count == 3
    @test length(collision_a.particles) == 3
    @test collision_a.active_cell_count == 2
    @test collision_a.collision_cell_count == 1
    @test collision_a.singleton_cell_count == 1
    @test collision_a.max_particles_per_cell == 2
    @test velocities_a == velocities_b
    @test collision_cell.particle_count == 2
    @test isapprox(collision_cell.center_vx_before, 0.0)
    @test isapprox(collision_cell.center_vy_before, 0.0)
    @test isapprox(collision_cell.center_vx_after, 0.0; atol = 1.0e-12)
    @test isapprox(collision_cell.center_vy_after, 0.0; atol = 1.0e-12)
    @test isapprox(abs(collision_cell.rotation_angle), pi / 2)
    @test singleton_cell.rotation_angle == 0.0
    @test isapprox(collision_a.particles[3].vx, 2.0)
    @test isapprox(collision_a.particles[3].vy, 3.0)
    @test all(particle -> particle.mass == 1.0, collision_a.particles)

    rotated_speed_1 = hypot(collision_a.particles[1].vx, collision_a.particles[1].vy)
    rotated_speed_2 = hypot(collision_a.particles[2].vx, collision_a.particles[2].vy)

    @test isapprox(rotated_speed_1, 1.0; atol = 1.0e-12)
    @test isapprox(rotated_speed_2, 1.0; atol = 1.0e-12)
end

@testset "MPC concentration maps by simulation time" begin
    space = empty_mpc_space(3, 2)
    config = MpcModelConfig(
        n0 = 0.5,
        tau = 1.0,
        rotation_angle = pi / 2,
        output_times = [0, 1, 2, 5],
    )
    initialization = MpcParticleInitialization(
        17,
        3,
        6.0,
        1.0,
        0,
        [
            MpcParticle(1, 0.2, 0.2, 0.5, 0.0, 0.0, 0.0, 1.0, "fluid", false),
            MpcParticle(2, 0.7, 0.8, 0.5, 0.0, 0.0, 0.0, 1.0, "fluid", false),
            MpcParticle(3, 2.2, 1.1, 0.5, 0.0, 0.0, 0.0, 1.0, "fluid", false),
        ],
    )

    concentration = generate_mpc_concentration_maps(
        initialization,
        space,
        config;
        steps = 2,
        seed = 99,
    )
    initial_snapshot = first(concentration.snapshots)

    @test concentration.requested_output_times == [0, 1, 2, 5]
    @test concentration.captured_output_times == [0, 1, 2]
    @test concentration.expected_density == 0.5
    @test concentration.high_concentration_threshold == 1.0
    @test concentration.particle_count == 3
    @test length(concentration.snapshots) == 3
    @test initial_snapshot.time == 0
    @test sum(initial_snapshot.density_grid) == 3
    @test initial_snapshot.particle_count == 3
    @test initial_snapshot.density_grid[1, 1] == 2
    @test initial_snapshot.density_grid[2, 3] == 1
    @test initial_snapshot.high_concentration_mask[1, 1]
    @test !initial_snapshot.high_concentration_mask[2, 3]
    @test all(snapshot -> sum(snapshot.density_grid) == 3, concentration.snapshots)

    multi_config = MpcModelConfig(
        n0 = 0.5,
        tau = 1.0,
        rotation_angle = pi / 2,
        realizations = 3,
        output_times = [0, 2],
    )
    multi_concentration = generate_mpc_concentration_maps(
        initialization,
        space,
        multi_config;
        steps = 2,
        seed = 99,
    )

    @test multi_concentration.realization_count == 3
    @test multi_concentration.realization_seeds == [99, 10106, 20113]
    @test all(snapshot -> isapprox(sum(snapshot.density_grid), 3.0), multi_concentration.snapshots)
    @test all(snapshot -> snapshot.max_concentration <= 3.0, multi_concentration.snapshots)

    mktempdir() do dir
        outputs = MammographySimulation.write_mpc_concentration_outputs(
            dir,
            multi_concentration,
            space,
        )

        @test isfile(outputs.summary_path)
        @test isfile(outputs.times_path)
        @test isfile(outputs.initial_map_path)
        @test isfile(outputs.final_map_path)
        @test isfile(outputs.initial_high_map_path)
        @test isfile(outputs.final_high_map_path)
        @test length(outputs.time_map_paths) == 2
        @test all(isfile, outputs.time_map_paths)
        @test all(isfile, outputs.time_high_map_paths)
        @test occursin("aggregation=mean_across_realizations", read(outputs.summary_path, String))
        @test occursin("realizations=3", read(outputs.summary_path, String))
        @test occursin("realization_seeds=99,10106,20113", read(outputs.summary_path, String))
        @test occursin("captured_output_times=0,2", read(outputs.summary_path, String))
        @test occursin("skipped_output_times=", read(outputs.summary_path, String))
        @test occursin("snapshot_t_0_particle_sum=3", read(outputs.summary_path, String))
        @test occursin("domain_mask_applied=true", read(outputs.summary_path, String))
        @test occursin("time\tx\ty\tconcentration", read(outputs.times_path, String))
        @test startswith(read(outputs.initial_map_path, String), "P2")
        @test startswith(read(outputs.initial_high_map_path, String), "P2")
    end

    masked_space = vertical_breast_domain_space()
    masked_config = MpcModelConfig(
        n0 = 0.5,
        tau = 1.0,
        output_times = [0, 1],
    )
    masked_initialization = MpcParticleInitialization(
        23,
        1,
        6.0,
        1.0,
        0,
        [
            MpcParticle(1, 1.8, 1.0, 0.5, 1.0, 0.0, 0.0, 1.0, "fluid", false),
        ],
    )
    masked_concentration = generate_mpc_concentration_maps(
        masked_initialization,
        masked_space,
        masked_config;
        steps = 1,
        seed = 23,
    )
    masked_final_snapshot = last(masked_concentration.snapshots)

    @test sum(masked_final_snapshot.density_grid[.!masked_space.domain_mask]) == 0
    @test masked_final_snapshot.particle_count == 1

    mktempdir() do dir
        outputs = MammographySimulation.write_mpc_concentration_outputs(
            dir,
            masked_concentration,
            masked_space,
        )
        final_map = read_pgm(outputs.final_map_path)
        final_high_map = read_pgm(outputs.final_high_map_path)

        @test all(final_map.pixels[.!masked_space.domain_mask] .== 0)
        @test all(final_high_map.pixels[.!masked_space.domain_mask] .== 0)
        @test all(final_map.pixels[masked_space.domain_mask] .>= 16)
        @test all(final_high_map.pixels[masked_space.domain_mask] .>= 16)
    end
end

@testset "MPC velocity autocorrelation and MDC" begin
    history = Matrix{Float64}[
        [1.0 0.0; 0.0 2.0],
        [0.5 0.0; 0.0 1.0],
        [0.0 0.0; 0.0 0.0],
    ]

    autocorrelation = calculate_velocity_autocorrelation(
        [history],
        [1, 2],
        [0];
        tau = 1.0,
        dimension = 2,
        realization_seeds = [101],
        requested_labeled_particles = 2,
        requested_initial_time_count = 1,
    )

    @test autocorrelation.steps == 2
    @test autocorrelation.dimension == 2
    @test autocorrelation.realization_count == 1
    @test autocorrelation.labeled_particle_count == 2
    @test autocorrelation.initial_times == [0]
    @test autocorrelation.realization_seeds == [101]
    @test autocorrelation.sample_counts == [2, 2, 2]
    @test isapprox(autocorrelation.cv_values[1], 2.5)
    @test isapprox(autocorrelation.cv_values[2], 1.25)
    @test isapprox(autocorrelation.cv_values[3], 0.0)
    @test isapprox(autocorrelation.mdc, 1.25)
    @test isapprox(autocorrelation.characteristic_time, 1 / log(2); atol = 1.0e-12)

    small_space = build_simulation_space(synthetic_roi_image())
    capped_config = MpcModelConfig(
        n0 = 1.0,
        labeled_particles = 500,
        correlation_initial_times = 1,
    )
    capped_autocorrelation = calculate_mpc_velocity_autocorrelation(
        small_space,
        capped_config;
        steps = 2,
        seed = 33,
    )

    @test capped_autocorrelation.requested_labeled_particles == 500
    @test capped_autocorrelation.labeled_particle_count == 9
    @test length(capped_autocorrelation.cv_values) == 3

    multi_config = MpcModelConfig(
        n0 = 1.0,
        labeled_particles = 9,
        realizations = 3,
        correlation_initial_times = 1,
    )
    multi_autocorrelation = calculate_mpc_velocity_autocorrelation(
        small_space,
        multi_config;
        steps = 2,
        seed = 44,
    )

    @test multi_autocorrelation.realization_count == 3
    @test multi_autocorrelation.realization_seeds == [44, 10051, 20058]
    @test length(multi_autocorrelation.realization_mdc_values) == 3
    @test length(multi_autocorrelation.realization_cv0_values) == 3
    @test length(multi_autocorrelation.realization_cv_final_values) == 3
    @test length(multi_autocorrelation.realization_sample_counts) == 3
    @test all(isfinite, multi_autocorrelation.realization_mdc_values)

    mktempdir() do dir
        outputs = MammographySimulation.write_velocity_autocorrelation_outputs(
            dir,
            multi_autocorrelation,
        )

        @test isfile(outputs.autocorrelation_path)
        @test isfile(outputs.summary_path)
        @test isfile(outputs.realizations_path)
        @test occursin("lag\ttime\tcv\tcv_average_xy", read(outputs.autocorrelation_path, String))
        @test occursin("aggregation=mean_across_realizations", read(outputs.summary_path, String))
        @test occursin("realizations=3", read(outputs.summary_path, String))
        @test occursin("realization_seeds=44,10051,20058", read(outputs.summary_path, String))
        @test occursin("requested_labeled_particles=9", read(outputs.summary_path, String))
        @test occursin("labeled_particle_count=9", read(outputs.summary_path, String))
        @test occursin("realization_mdc_values=", read(outputs.summary_path, String))
        @test occursin("mdc_standard_deviation=", read(outputs.summary_path, String))
        @test occursin("realization\tseed\tlabeled_particle_count\tinitial_times\tsample_count\tcv0\tcv_final\tmdc", read(outputs.realizations_path, String))
        @test occursin("3\t20058", read(outputs.realizations_path, String))
    end
end

@testset "MPC normalized diffusion metrics" begin
    config = MpcModelConfig(
        n0 = 10.0,
        mass = 1.0,
        kbt = 1.0,
        tau = 1.0,
    )
    mdc0 = calculate_theoretical_mdc0(config)

    @test isapprox(mdc0, 1.16665; atol = 1.0e-4)
    @test isapprox(calculate_mdc_star(0.583325, mdc0), 0.5; atol = 1.0e-4)
    @test_throws ArgumentError calculate_mdc_star(1.0, 0.0)
    @test_throws ArgumentError calculate_mdc_star(Inf, mdc0)

    autocorrelation = MpcVelocityAutocorrelationResult(
        2,
        1.0,
        2,
        1,
        2,
        2,
        1,
        [0],
        [101],
        [2.5, 1.25, 0.0],
        [2, 2, 2],
        1.25,
        1 / log(2),
        [1.25],
        [2.5],
        [0.0],
        [6],
    )
    metrics = MammographySimulation.build_comparable_diffusion_metrics(
        autocorrelation,
        config,
    )

    @test metrics.metric_model == "mdc_normalized_against_theoretical_reference"
    @test metrics.reference_origin == "theoretical_mdc0_without_obstacles"
    @test metrics.units == "reduced_mpc_units"
    @test metrics.mdc == 1.25
    @test isapprox(metrics.mdc0, mdc0)
    @test isapprox(metrics.mdc_star, 1.25 / mdc0)
    @test metrics.mdc_standard_deviation == 0.0
    @test metrics.realization_mdc_values == [1.25]
    @test occursin("academico", metrics.purpose_note)

    mktempdir() do dir
        outputs = MammographySimulation.write_comparable_diffusion_metrics_outputs(
            dir,
            metrics,
        )

        @test isfile(outputs.json_path)
        @test isfile(outputs.tsv_path)
        @test isfile(outputs.summary_path)
        @test occursin("\"mdc_star\"", read(outputs.json_path, String))
        @test occursin("metric_model\treference_origin", read(outputs.tsv_path, String))
        @test occursin("formula_mdc_star=MDC* = MDC / MDC0", read(outputs.summary_path, String))
        @test occursin("no constituye diagnostico clinico", read(outputs.summary_path, String))
    end
end

@testset "Synthetic validation cases for C tutor comparison" begin
    case_names = synthetic_validation_case_names()

    @test case_names == [
        "free_field",
        "central_obstacle",
        "intensity_pattern",
        "clear_dark_channel",
        "synthetic_roi",
    ]

    free_field = build_synthetic_validation_case("free_field")
    central_obstacle = build_synthetic_validation_case("central_obstacle")

    @test free_field.expected_domain_cell_count == 64
    @test free_field.expected_preliminary_blocking_obstacle_count == 0
    @test central_obstacle.expected_domain_cell_count == 81
    @test central_obstacle.expected_preliminary_blocking_obstacle_count == 9

    mktempdir() do dir
        written = MammographySimulation.write_synthetic_validation_case(
            dir,
            central_obstacle,
        )

        @test isfile(written.pgm_path)
        @test isfile(written.matrix_path)
        @test isfile(written.size_path)
        @test isfile(written.metadata_path)
        @test read(written.size_path, String) == "9\t9\t0\n"
        @test length(readlines(written.matrix_path)) == 81
        @test startswith(read(written.pgm_path, String), "P2")
        @test occursin("expected_domain_cell_count\t81", read(written.metadata_path, String))
    end

    mktempdir() do dir
        cases = generate_synthetic_validation_cases(joinpath(dir, "cases"))

        @test length(cases) == 5
        @test isfile(joinpath(dir, "cases", "validation_cases.tsv"))
        @test isfile(joinpath(dir, "cases", "free_field", "matrix.in"))
        @test isfile(joinpath(dir, "cases", "synthetic_roi", "size.in"))
    end

    mktempdir() do dir
        config = MpcModelConfig(
            n0 = 0.25,
            labeled_particles = 2,
            correlation_initial_times = 1,
            output_times = [0, 2],
        )
        results = validate_synthetic_cases(
            dir;
            seed = 11,
            steps = 2,
            mpc_config = config,
        )

        @test length(results) == 5
        @test all(result -> result.status == "ok", results)
        @test all(result -> result.particle_conservation_ok, results)
        @test all(result -> result.mpc_particle_count == result.concentration_particle_sum, results)
        @test all(result -> isfinite(result.mdc), results)
        @test all(result -> isfinite(result.mdc0), results)
        @test all(result -> isfinite(result.mdc_star), results)
        @test isfile(joinpath(dir, "validation_summary.tsv"))
        @test isfile(joinpath(dir, "validation_summary.md"))
        @test occursin(
            "Validacion sintetica del simulador Julia",
            read(joinpath(dir, "validation_summary.md"), String),
        )

        free_field_result = only([
            result for result in results
            if result.case_name == "free_field"
        ])

        @test isfile(joinpath(free_field_result.output_dir, "diffusion_metrics.json"))
        @test isfile(joinpath(free_field_result.output_dir, "mpc_concentration_summary.txt"))
        @test isfile(joinpath(free_field_result.output_dir, "mpc_concentration_times.tsv"))
    end
end

@testset "Preliminary simulation results" begin
    space = build_simulation_space(synthetic_roi_image())
    simulation = run_minimal_simulation(
        space;
        seed = 7,
        steps = 5,
        particle_density = 0.5,
    )

    mktempdir() do dir
        preliminary_results = generate_preliminary_results(dir, simulation, space)

        @test isfile(preliminary_results.metrics_path)
        @test isfile(preliminary_results.domain_mask_path)
        @test isfile(preliminary_results.density_map_path)
        @test isfile(preliminary_results.density_matrix_path)

        metrics_content = read(preliminary_results.metrics_path, String)
        domain_mask_content = read(preliminary_results.domain_mask_path, String)
        density_map_content = read(preliminary_results.density_map_path, String)
        density_matrix_content = read(preliminary_results.density_matrix_path, String)

        @test preliminary_results.metrics.status == "preliminary_results_ready"
        @test preliminary_results.metrics.width == 5
        @test preliminary_results.metrics.height == 5
        @test preliminary_results.metrics.domain_cell_count == 9
        @test preliminary_results.metrics.excluded_background_count == 16
        @test preliminary_results.metrics.obstacle_count == 9
        @test preliminary_results.metrics.preliminary_blocking_obstacle_count == 8
        @test occursin("\"status\": \"preliminary_results_ready\"", metrics_content)
        @test occursin("\"domain_cell_count\": 9", metrics_content)
        @test occursin("\"obstacle_count\": 9", metrics_content)
        @test occursin("\"preliminary_blocking_obstacle_count\": 8", metrics_content)
        @test occursin("\"collision_rate\"", metrics_content)
        @test startswith(domain_mask_content, "P2")
        @test occursin("5 5", domain_mask_content)
        @test startswith(density_map_content, "P2")
        @test occursin("5 5", density_map_content)
        @test occursin("x\ty\tvisits\tdensity_value\tis_domain\tis_obstacle", density_matrix_content)
    end
end

@testset "MammographySimulation CLI base" begin
    mktempdir() do dir
        input_path = joinpath(dir, "simulation_input.pgm")
        output_dir = joinpath(dir, "results")

        write(
            input_path,
            "P2\n5 5\n255\n0 0 0 0 0\n0 80 80 80 0\n0 80 0 255 0\n0 80 80 80 0\n0 0 0 0 0\n",
        )

        config = SimulationRunConfig(
            input_path = input_path,
            output_dir = output_dir,
            seed = 42,
            steps = 3,
            particle_density = 0.5,
            mpc_config = MpcModelConfig(
                n0 = 10.0,
                mass = 1.0,
                kbt = 1.0,
                tau = 1.0,
                rotation_angle = pi / 2,
                realizations = 2,
                labeled_particles = 15,
                correlation_initial_times = 2,
                output_times = [0, 3],
            ),
        )

        result = run_case(config)

        @test isfile(result.log_path)
        @test isfile(result.config_path)
        @test isfile(result.mpc_config_path)
        @test isfile(result.summary_path)
        @test isfile(result.space_summary_path)
        @test isfile(result.obstacles_path)
        @test isfile(result.obstacle_radius_matrix_path)
        @test isfile(result.obstacle_radius_map_path)
        @test isfile(result.obstacle_radius_histogram_path)
        @test isfile(result.mpc_initial_particles_path)
        @test isfile(result.mpc_streamed_particles_path)
        @test isfile(result.mpc_streaming_summary_path)
        @test isfile(result.mpc_collided_particles_path)
        @test isfile(result.mpc_collision_summary_path)
        @test isfile(result.mpc_cell_collisions_path)
        @test isfile(result.mpc_concentration_summary_path)
        @test isfile(result.mpc_concentration_times_path)
        @test isfile(result.mpc_concentration_initial_map_path)
        @test isfile(result.mpc_concentration_final_map_path)
        @test isfile(result.mpc_high_concentration_initial_map_path)
        @test isfile(result.mpc_high_concentration_final_map_path)
        @test all(isfile, result.mpc_concentration_time_map_paths)
        @test all(isfile, result.mpc_high_concentration_time_map_paths)
        @test isfile(result.velocity_autocorrelation_path)
        @test isfile(result.velocity_autocorrelation_summary_path)
        @test isfile(result.velocity_autocorrelation_realizations_path)
        @test isfile(result.diffusion_metrics_json_path)
        @test isfile(result.diffusion_metrics_tsv_path)
        @test isfile(result.diffusion_metrics_summary_path)
        @test isfile(result.simulation_summary_path)
        @test isfile(result.simulation_state_path)
        @test isfile(result.visit_counts_path)
        @test isfile(result.metrics_path)
        @test isfile(result.domain_mask_path)
        @test isfile(result.density_map_path)
        @test isfile(result.density_matrix_path)
        @test occursin("status=preliminary_results_ready", read(result.log_path, String))
        @test occursin("width=5", read(result.summary_path, String))
        @test occursin("domain_cell_count=9", read(result.space_summary_path, String))
        @test occursin("excluded_background_count=16", read(result.space_summary_path, String))
        @test occursin("obstacle_count=9", read(result.space_summary_path, String))
        @test occursin("preliminary_blocking_obstacle_count=8", read(result.space_summary_path, String))
        @test occursin("radius_formula=0.5 * cell_length * (1 - intensity / (max_gray + 1))", read(result.space_summary_path, String))
        @test occursin("configuration_model=mpc_base_configuration", read(result.simulation_summary_path, String))
        @test occursin("execution_engine=sequential_minimal_random_walk", read(result.simulation_summary_path, String))
        @test occursin("particle_count=1", read(result.simulation_summary_path, String))
        @test occursin("mpc_particle_model=continuous_position_maxwellian_velocity", read(result.simulation_summary_path, String))
        @test occursin("mpc_particle_count=90", read(result.simulation_summary_path, String))
        @test occursin("mpc_velocity_sigma=1.0", read(result.simulation_summary_path, String))
        @test occursin("mpc_streaming_model=free_translation_periodic_boundaries_bounce_back", read(result.simulation_summary_path, String))
        @test occursin("mpc_streaming_steps=3", read(result.simulation_summary_path, String))
        @test occursin("mpc_collision_model=multiparticle_collision_by_cell", read(result.simulation_summary_path, String))
        @test occursin("mpc_collision_particle_count=90", read(result.simulation_summary_path, String))
        @test occursin("mpc_concentration_model=particles_per_cell_snapshot", read(result.simulation_summary_path, String))
        @test occursin("mpc_concentration_aggregation=mean_across_realizations", read(result.simulation_summary_path, String))
        @test occursin("mpc_concentration_realizations=2", read(result.simulation_summary_path, String))
        @test occursin("mpc_concentration_realization_seeds=42,10049", read(result.simulation_summary_path, String))
        @test occursin("mpc_concentration_captured_output_times=0,3", read(result.simulation_summary_path, String))
        @test occursin("velocity_autocorrelation_model=green_kubo_xy", read(result.simulation_summary_path, String))
        @test occursin("velocity_autocorrelation_aggregation=mean_across_realizations", read(result.simulation_summary_path, String))
        @test occursin("velocity_autocorrelation_realizations=2", read(result.simulation_summary_path, String))
        @test occursin("velocity_autocorrelation_requested_labeled_particles=15", read(result.simulation_summary_path, String))
        @test occursin("velocity_autocorrelation_labeled_particle_count=15", read(result.simulation_summary_path, String))
        @test occursin("velocity_autocorrelation_requested_initial_time_count=2", read(result.simulation_summary_path, String))
        @test occursin("velocity_autocorrelation_realization_mdc_values=", read(result.simulation_summary_path, String))
        @test occursin("diffusion_metric_model=mdc_normalized_against_theoretical_reference", read(result.simulation_summary_path, String))
        @test occursin("diffusion_metric_mdc_star=", read(result.simulation_summary_path, String))
        @test occursin("diffusion_metric_mdc_standard_deviation=", read(result.simulation_summary_path, String))
        @test occursin("attempted_moves=3", read(result.simulation_summary_path, String))
        @test occursin("preliminary_blocking_obstacle_count=8", read(result.simulation_summary_path, String))
        @test occursin("\"input_role\": \"confirmed_roi_pgm\"", read(result.mpc_config_path, String))
        @test occursin("\"configuration_model\": \"mpc_base_configuration\"", read(result.mpc_config_path, String))
        @test occursin("\"lx\": 5.0", read(result.mpc_config_path, String))
        @test occursin("\"ly\": 5.0", read(result.mpc_config_path, String))
        @test occursin("\"lz\": 1", read(result.mpc_config_path, String))
        @test occursin("\"n0\": 10.0", read(result.mpc_config_path, String))
        @test occursin("\"mpc_particle_model\": \"continuous_position_maxwellian_velocity\"", read(result.mpc_config_path, String))
        @test occursin("\"mpc_particle_count\": 90", read(result.mpc_config_path, String))
        @test occursin("\"mpc_streaming_model\": \"free_translation_periodic_boundaries_bounce_back\"", read(result.mpc_config_path, String))
        @test occursin("\"mpc_collision_model\": \"multiparticle_collision_by_cell\"", read(result.mpc_config_path, String))
        @test occursin("\"mpc_collision_particle_count\": 90", read(result.mpc_config_path, String))
        @test occursin("\"mpc_concentration_model\": \"particles_per_cell_snapshot\"", read(result.mpc_config_path, String))
        @test occursin("\"mpc_concentration_aggregation\": \"mean_across_realizations\"", read(result.mpc_config_path, String))
        @test occursin("\"mpc_concentration_realizations\": 2", read(result.mpc_config_path, String))
        @test occursin("\"mpc_concentration_realization_seeds\": [42, 10049]", read(result.mpc_config_path, String))
        @test occursin("\"mpc_concentration_snapshot_count\": 2", read(result.mpc_config_path, String))
        @test occursin("\"velocity_autocorrelation_model\": \"green_kubo_xy\"", read(result.mpc_config_path, String))
        @test occursin("\"velocity_autocorrelation_aggregation\": \"mean_across_realizations\"", read(result.mpc_config_path, String))
        @test occursin("\"velocity_autocorrelation_realizations\": 2", read(result.mpc_config_path, String))
        @test occursin("\"velocity_autocorrelation_requested_labeled_particles\": 15", read(result.mpc_config_path, String))
        @test occursin("\"velocity_autocorrelation_labeled_particle_count\": 15", read(result.mpc_config_path, String))
        @test occursin("\"velocity_autocorrelation_requested_initial_time_count\": 2", read(result.mpc_config_path, String))
        @test occursin("\"velocity_autocorrelation_realization_mdc_values\"", read(result.mpc_config_path, String))
        @test occursin("\"diffusion_metric_model\": \"mdc_normalized_against_theoretical_reference\"", read(result.mpc_config_path, String))
        @test occursin("\"diffusion_metric_mdc0\"", read(result.mpc_config_path, String))
        @test occursin("\"diffusion_metric_mdc_standard_deviation\"", read(result.mpc_config_path, String))
        @test occursin("\"obstacle_count\": 9", read(result.mpc_config_path, String))
        @test occursin("\"radius_model\": \"cylindrical_obstacles_from_pgm_intensity\"", read(result.mpc_config_path, String))
        @test occursin("\"output_times\": [0, 3]", read(result.mpc_config_path, String))
        @test occursin("\"status\": \"preliminary_results_ready\"", read(result.metrics_path, String))
        @test occursin("center_z", read(result.obstacles_path, String))
        @test occursin("preliminary_blocking", read(result.obstacles_path, String))
        @test occursin("x\ty\tintensity\tnormalized_intensity\tradius\tis_domain\tpreliminary_blocking", read(result.obstacle_radius_matrix_path, String))
        @test startswith(read(result.obstacle_radius_map_path, String), "P2")
        @test occursin("bucket\tcount", read(result.obstacle_radius_histogram_path, String))
        @test occursin("id\tx\ty\tz\tvx\tvy\tvz\tmass\tspecies\tlabeled", read(result.mpc_initial_particles_path, String))
        @test occursin("# target_particle_count=90", read(result.mpc_initial_particles_path, String))
        @test occursin("id\tx\ty\tz\tvx\tvy\tvz\tmass\tspecies\tlabeled", read(result.mpc_streamed_particles_path, String))
        @test occursin("obstacle_collision_count=", read(result.mpc_streaming_summary_path, String))
        @test occursin("domain_boundary_collision_count=", read(result.mpc_streaming_summary_path, String))
        @test occursin("id\tx\ty\tz\tvx\tvy\tvz\tmass\tspecies\tlabeled", read(result.mpc_collided_particles_path, String))
        @test occursin("mpc_collision_model=multiparticle_collision_by_cell", read(result.mpc_collision_summary_path, String))
        @test occursin("cell_x\tcell_y\tparticle_count", read(result.mpc_cell_collisions_path, String))
        @test occursin("captured_output_times=0,3", read(result.mpc_concentration_summary_path, String))
        @test occursin("snapshot_t_0_particle_sum=90", read(result.mpc_concentration_summary_path, String))
        @test occursin("time\tx\ty\tconcentration", read(result.mpc_concentration_times_path, String))
        @test startswith(read(result.mpc_concentration_initial_map_path, String), "P2")
        @test startswith(read(result.mpc_high_concentration_initial_map_path, String), "P2")
        @test occursin("lag\ttime\tcv", read(result.velocity_autocorrelation_path, String))
        @test occursin("mdc=", read(result.velocity_autocorrelation_summary_path, String))
        @test occursin("realization\tseed\tlabeled_particle_count", read(result.velocity_autocorrelation_realizations_path, String))
        @test occursin("\"mdc_star\"", read(result.diffusion_metrics_json_path, String))
        @test occursin("metric_model\treference_origin", read(result.diffusion_metrics_tsv_path, String))
        @test occursin("MDC* = MDC / MDC0", read(result.diffusion_metrics_summary_path, String))
        @test startswith(read(result.domain_mask_path, String), "P2")
        @test startswith(read(result.density_map_path, String), "P2")
    end
end
