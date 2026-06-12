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
    @test bounced.boundary_crossing_count_x == 0
    @test isapprox(bounced_particle.x, 1.0; atol = 1.0e-8)
    @test isapprox(bounced_particle.y, 5.0; atol = 1.0e-8)
    @test isapprox(bounced_particle.vx, -4.0)
    @test isapprox(bounced_particle.vy, -0.0)
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

    mktempdir() do dir
        outputs = MammographySimulation.write_mpc_concentration_outputs(
            dir,
            concentration,
            space,
        )

        @test isfile(outputs.summary_path)
        @test isfile(outputs.times_path)
        @test isfile(outputs.initial_map_path)
        @test isfile(outputs.final_map_path)
        @test isfile(outputs.initial_high_map_path)
        @test isfile(outputs.final_high_map_path)
        @test length(outputs.time_map_paths) == 3
        @test all(isfile, outputs.time_map_paths)
        @test all(isfile, outputs.time_high_map_paths)
        @test occursin("captured_output_times=0,1,2", read(outputs.summary_path, String))
        @test occursin("skipped_output_times=5", read(outputs.summary_path, String))
        @test occursin("snapshot_t_0_particle_sum=3", read(outputs.summary_path, String))
        @test occursin("time\tx\ty\tconcentration", read(outputs.times_path, String))
        @test startswith(read(outputs.initial_map_path, String), "P2")
        @test startswith(read(outputs.initial_high_map_path, String), "P2")
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

    mktempdir() do dir
        outputs = MammographySimulation.write_velocity_autocorrelation_outputs(
            dir,
            autocorrelation,
        )

        @test isfile(outputs.autocorrelation_path)
        @test isfile(outputs.summary_path)
        @test isfile(outputs.realizations_path)
        @test occursin("lag\ttime\tcv\tcv_average_xy", read(outputs.autocorrelation_path, String))
        @test occursin("mdc=1.25", read(outputs.summary_path, String))
        @test occursin("realization\tseed\tlabeled_particle_count", read(outputs.realizations_path, String))
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
        @test occursin("mpc_concentration_captured_output_times=0,3", read(result.simulation_summary_path, String))
        @test occursin("velocity_autocorrelation_model=green_kubo_xy", read(result.simulation_summary_path, String))
        @test occursin("velocity_autocorrelation_labeled_particle_count=15", read(result.simulation_summary_path, String))
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
        @test occursin("\"mpc_concentration_snapshot_count\": 2", read(result.mpc_config_path, String))
        @test occursin("\"velocity_autocorrelation_model\": \"green_kubo_xy\"", read(result.mpc_config_path, String))
        @test occursin("\"velocity_autocorrelation_labeled_particle_count\": 15", read(result.mpc_config_path, String))
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
        @test startswith(read(result.domain_mask_path, String), "P2")
        @test startswith(read(result.density_map_path, String), "P2")
    end
end
