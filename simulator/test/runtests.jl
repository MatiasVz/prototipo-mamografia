using Test
using MammographySimulation

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
    image = PgmImage(
        2,
        2,
        255,
        [0 64; 128 255],
    )

    space = build_simulation_space(image)

    @test space.width == 2
    @test space.height == 2
    @test space.max_gray == 255
    @test space.obstacle_threshold == 1
    @test size(space.normalized_intensities) == (2, 2)
    @test space.normalized_intensities[1, 1] == 0.0
    @test space.normalized_intensities[2, 2] == 1.0
    @test length(space.obstacles) == 3

    first_obstacle = space.obstacles[1]
    last_obstacle = space.obstacles[end]

    @test first_obstacle.x == 1
    @test first_obstacle.y == 0
    @test first_obstacle.center_x == 1.5
    @test first_obstacle.center_y == 0.5
    @test first_obstacle.intensity == 64
    @test first_obstacle.radius == 0.375

    @test last_obstacle.x == 1
    @test last_obstacle.y == 1
    @test last_obstacle.intensity == 255
    @test last_obstacle.radius ≈ 0.001953125

    @test_throws ArgumentError build_simulation_space(image; obstacle_threshold = 0)
end

@testset "Minimal sequential simulation" begin
    image = PgmImage(
        3,
        2,
        255,
        [0 255 0; 0 0 255],
    )

    space = build_simulation_space(image)

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
    @test length(result_a.particles) == 2
    @test result_a.attempted_moves == 10
    @test result_a.collision_count >= 0
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

@testset "Preliminary simulation results" begin
    image = PgmImage(
        3,
        2,
        255,
        [0 255 0; 0 0 255],
    )

    space = build_simulation_space(image)
    simulation = run_minimal_simulation(
        space;
        seed = 7,
        steps = 5,
        particle_density = 0.5,
    )

    mktempdir() do dir
        preliminary_results = generate_preliminary_results(dir, simulation, space)

        @test isfile(preliminary_results.metrics_path)
        @test isfile(preliminary_results.density_map_path)
        @test isfile(preliminary_results.density_matrix_path)

        metrics_content = read(preliminary_results.metrics_path, String)
        density_map_content = read(preliminary_results.density_map_path, String)
        density_matrix_content = read(preliminary_results.density_matrix_path, String)

        @test preliminary_results.metrics.status == "preliminary_results_ready"
        @test preliminary_results.metrics.width == 3
        @test preliminary_results.metrics.height == 2
        @test preliminary_results.metrics.obstacle_count == 2
        @test occursin("\"status\": \"preliminary_results_ready\"", metrics_content)
        @test occursin("\"collision_rate\"", metrics_content)
        @test startswith(density_map_content, "P2")
        @test occursin("3 2", density_map_content)
        @test occursin("x\ty\tvisits\tdensity_value\tis_obstacle", density_matrix_content)
    end
end

@testset "MammographySimulation CLI base" begin
    mktempdir() do dir
        input_path = joinpath(dir, "simulation_input.pgm")
        output_dir = joinpath(dir, "results")

        write(input_path, "P2\n2 2\n255\n0 0\n0 255\n")

        config = SimulationRunConfig(
            input_path = input_path,
            output_dir = output_dir,
            seed = 42,
            steps = 3,
            particle_density = 0.5,
        )

        result = run_case(config)

        @test isfile(result.log_path)
        @test isfile(result.config_path)
        @test isfile(result.summary_path)
        @test isfile(result.space_summary_path)
        @test isfile(result.obstacles_path)
        @test isfile(result.simulation_summary_path)
        @test isfile(result.simulation_state_path)
        @test isfile(result.visit_counts_path)
        @test isfile(result.metrics_path)
        @test isfile(result.density_map_path)
        @test isfile(result.density_matrix_path)
        @test occursin("status=preliminary_results_ready", read(result.log_path, String))
        @test occursin("width=2", read(result.summary_path, String))
        @test occursin("obstacle_count=1", read(result.space_summary_path, String))
        @test occursin("particle_count=2", read(result.simulation_summary_path, String))
        @test occursin("attempted_moves=6", read(result.simulation_summary_path, String))
        @test occursin("\"status\": \"preliminary_results_ready\"", read(result.metrics_path, String))
        @test startswith(read(result.density_map_path, String), "P2")
    end
end
