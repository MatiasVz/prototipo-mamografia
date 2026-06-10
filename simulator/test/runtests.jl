using Test
using MammographySimulation

@testset "MammographySimulation CLI base" begin
    mktempdir() do dir
        input_path = joinpath(dir, "simulation_input.pgm")
        output_dir = joinpath(dir, "results")

        write(input_path, "P2\n1 1\n255\n0\n")

        config = SimulationRunConfig(
            input_path = input_path,
            output_dir = output_dir,
            seed = 42,
            steps = 0,
        )

        result = run_case(config)

        @test isfile(result.log_path)
        @test isfile(result.config_path)
        @test occursin("status=base_structure_ready", read(result.log_path, String))
    end
end
