module MammographySimulation

using Dates

export SimulationRunConfig, parse_cli_args, run_case, cli_main

Base.@kwdef struct SimulationRunConfig
    input_path::String
    output_dir::String
    seed::Int = 1234
    steps::Int = 0
end

const USAGE = """
Uso:
  julia --project=simulator simulator/scripts/run_case.jl --input <archivo.pgm> --output <directorio> [--seed <entero>] [--steps <entero>]

Opciones:
  --input   Ruta del archivo PGM preparado para simulacion.
  --output  Directorio donde se escribiran los resultados.
  --seed    Semilla reproducible para etapas posteriores. Por defecto: 1234.
  --steps   Numero de pasos de simulacion. Por defecto: 0.
  --help    Muestra esta ayuda.
"""

const VALUE_OPTIONS = Set(["--input", "--output", "--seed", "--steps"])

function parse_cli_args(args::Vector{String})
    if any(arg -> arg in ("--help", "-h"), args)
        return nothing
    end

    options = Dict{String,String}()
    index = 1

    while index <= length(args)
        arg = args[index]

        if startswith(arg, "--") && occursin("=", arg)
            key, value = split(arg, "=", limit = 2)
            if !(key in VALUE_OPTIONS)
                throw(ArgumentError("Opcion no reconocida: $(key)"))
            end
            options[key] = value
            index += 1
            continue
        end

        if arg in VALUE_OPTIONS
            if index == length(args)
                throw(ArgumentError("La opcion $(arg) requiere un valor."))
            end

            options[arg] = args[index + 1]
            index += 2
            continue
        end

        throw(ArgumentError("Opcion no reconocida: $(arg)"))
    end

    input_path = get(options, "--input", "")
    output_dir = get(options, "--output", "")

    if isempty(input_path)
        throw(ArgumentError("Debe indicar --input con la ruta del archivo PGM."))
    end

    if isempty(output_dir)
        throw(ArgumentError("Debe indicar --output con el directorio de resultados."))
    end

    seed = parse_integer_option(get(options, "--seed", "1234"), "--seed")
    steps = parse_integer_option(get(options, "--steps", "0"), "--steps")

    if steps < 0
        throw(ArgumentError("La opcion --steps no puede ser negativa."))
    end

    return SimulationRunConfig(
        input_path = input_path,
        output_dir = output_dir,
        seed = seed,
        steps = steps,
    )
end

function run_case(config::SimulationRunConfig)
    input_path = abspath(config.input_path)
    output_dir = abspath(config.output_dir)

    if !isfile(input_path)
        throw(ArgumentError("No se encontro el archivo de entrada: $(input_path)"))
    end

    mkpath(output_dir)

    timestamp = Dates.format(Dates.now(), dateformat"yyyy-mm-ddTHH:MM:SS")
    log_path = joinpath(output_dir, "simulation.log")
    config_path = joinpath(output_dir, "simulation_config.txt")

    open(log_path, "w") do io
        println(io, "MammographySimulation")
        println(io, "status=base_structure_ready")
        println(io, "created_at=$(timestamp)")
        println(io, "input_path=$(input_path)")
        println(io, "output_dir=$(output_dir)")
        println(io, "seed=$(config.seed)")
        println(io, "steps=$(config.steps)")
        println(io, "message=Estructura base creada. La lectura PGM y la simulacion se implementaran en issues posteriores.")
    end

    open(config_path, "w") do io
        println(io, "input_path=$(input_path)")
        println(io, "output_dir=$(output_dir)")
        println(io, "seed=$(config.seed)")
        println(io, "steps=$(config.steps)")
        println(io, "created_at=$(timestamp)")
    end

    return (log_path = log_path, config_path = config_path)
end

function cli_main(args::Vector{String} = ARGS)
    try
        config = parse_cli_args(args)

        if config === nothing
            print(USAGE)
            return 0
        end

        result = run_case(config)
        println("Simulador Julia inicial ejecutado correctamente.")
        println("log_path=$(result.log_path)")
        println("config_path=$(result.config_path)")
        return 0
    catch error
        println(stderr, "Error: $(error)")
        println(stderr)
        println(stderr, USAGE)
        return 1
    end
end

function parse_integer_option(value::String, option_name::String)
    try
        return parse(Int, value)
    catch
        throw(ArgumentError("La opcion $(option_name) debe ser un entero."))
    end
end

end
