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
            "--output-times",
            "0,-1",
        ])
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
        @test occursin("attempted_moves=3", read(result.simulation_summary_path, String))
        @test occursin("preliminary_blocking_obstacle_count=8", read(result.simulation_summary_path, String))
        @test occursin("\"input_role\": \"confirmed_roi_pgm\"", read(result.mpc_config_path, String))
        @test occursin("\"configuration_model\": \"mpc_base_configuration\"", read(result.mpc_config_path, String))
        @test occursin("\"lx\": 5.0", read(result.mpc_config_path, String))
        @test occursin("\"ly\": 5.0", read(result.mpc_config_path, String))
        @test occursin("\"lz\": 1", read(result.mpc_config_path, String))
        @test occursin("\"n0\": 10.0", read(result.mpc_config_path, String))
        @test occursin("\"obstacle_count\": 9", read(result.mpc_config_path, String))
        @test occursin("\"radius_model\": \"cylindrical_obstacles_from_pgm_intensity\"", read(result.mpc_config_path, String))
        @test occursin("\"output_times\": [0, 3]", read(result.mpc_config_path, String))
        @test occursin("\"status\": \"preliminary_results_ready\"", read(result.metrics_path, String))
        @test occursin("center_z", read(result.obstacles_path, String))
        @test occursin("preliminary_blocking", read(result.obstacles_path, String))
        @test occursin("x\ty\tintensity\tnormalized_intensity\tradius\tis_domain\tpreliminary_blocking", read(result.obstacle_radius_matrix_path, String))
        @test startswith(read(result.obstacle_radius_map_path, String), "P2")
        @test occursin("bucket\tcount", read(result.obstacle_radius_histogram_path, String))
        @test startswith(read(result.domain_mask_path, String), "P2")
        @test startswith(read(result.density_map_path, String), "P2")
    end
end
