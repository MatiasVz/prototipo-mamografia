module MammographySimulation

using Dates

export PgmImage,
    SimulationObstacle,
    SimulationSpace,
    SimulationRunConfig,
    read_pgm,
    build_simulation_space,
    parse_cli_args,
    run_case,
    cli_main

struct PgmImage
    width::Int
    height::Int
    max_gray::Int
    pixels::Matrix{Int}
end

struct SimulationObstacle
    x::Int
    y::Int
    center_x::Float64
    center_y::Float64
    intensity::Int
    normalized_intensity::Float64
    radius::Float64
end

struct SimulationSpace
    width::Int
    height::Int
    max_gray::Int
    obstacle_threshold::Int
    normalized_intensities::Matrix{Float64}
    obstacles::Vector{SimulationObstacle}
end

const DEFAULT_OBSTACLE_THRESHOLD = 1

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
    pgm_image = read_pgm(input_path)
    simulation_space = build_simulation_space(pgm_image)

    mkpath(output_dir)

    timestamp = Dates.format(Dates.now(), dateformat"yyyy-mm-ddTHH:MM:SS")
    log_path = joinpath(output_dir, "simulation.log")
    config_path = joinpath(output_dir, "simulation_config.txt")
    summary_path = joinpath(output_dir, "input_summary.txt")
    space_summary_path = joinpath(output_dir, "space_summary.txt")
    obstacles_path = joinpath(output_dir, "obstacles.tsv")

    open(log_path, "w") do io
        println(io, "MammographySimulation")
        println(io, "status=simulation_space_ready")
        println(io, "created_at=$(timestamp)")
        println(io, "input_path=$(input_path)")
        println(io, "output_dir=$(output_dir)")
        println(io, "width=$(pgm_image.width)")
        println(io, "height=$(pgm_image.height)")
        println(io, "max_gray=$(pgm_image.max_gray)")
        println(io, "obstacle_count=$(length(simulation_space.obstacles))")
        println(io, "obstacle_threshold=$(simulation_space.obstacle_threshold)")
        println(io, "seed=$(config.seed)")
        println(io, "steps=$(config.steps)")
        println(io, "message=PGM convertido a espacio de simulacion. La dinamica mesoscopica se implementara en issues posteriores.")
    end

    open(config_path, "w") do io
        println(io, "input_path=$(input_path)")
        println(io, "output_dir=$(output_dir)")
        println(io, "width=$(pgm_image.width)")
        println(io, "height=$(pgm_image.height)")
        println(io, "max_gray=$(pgm_image.max_gray)")
        println(io, "obstacle_threshold=$(simulation_space.obstacle_threshold)")
        println(io, "seed=$(config.seed)")
        println(io, "steps=$(config.steps)")
        println(io, "created_at=$(timestamp)")
    end

    open(summary_path, "w") do io
        println(io, "width=$(pgm_image.width)")
        println(io, "height=$(pgm_image.height)")
        println(io, "max_gray=$(pgm_image.max_gray)")
        println(io, "min_intensity=$(minimum(pgm_image.pixels))")
        println(io, "max_intensity=$(maximum(pgm_image.pixels))")
        println(io, "pixel_count=$(length(pgm_image.pixels))")
    end

    write_space_summary(space_summary_path, simulation_space)
    write_obstacles_tsv(obstacles_path, simulation_space.obstacles)

    return (
        log_path = log_path,
        config_path = config_path,
        summary_path = summary_path,
        space_summary_path = space_summary_path,
        obstacles_path = obstacles_path,
        image = pgm_image,
        space = simulation_space,
    )
end

function cli_main(args::Vector{String} = ARGS)
    try
        config = parse_cli_args(args)

        if config === nothing
            print(USAGE)
            return 0
        end

        result = run_case(config)
        println("Conversion de PGM a espacio de simulacion ejecutada correctamente.")
        println("log_path=$(result.log_path)")
        println("config_path=$(result.config_path)")
        println("summary_path=$(result.summary_path)")
        println("space_summary_path=$(result.space_summary_path)")
        println("obstacles_path=$(result.obstacles_path)")
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

function read_pgm(path::AbstractString)
    if !isfile(path)
        throw(ArgumentError("No se encontro el archivo PGM: $(abspath(path))"))
    end

    bytes = read(path)

    magic, index = read_pgm_token(bytes, 1)
    if !(magic in ("P2", "P5"))
        throw(ArgumentError("Formato PGM no soportado. Se esperaba P2 o P5 y se encontro $(magic)."))
    end

    width_token, index = read_pgm_token(bytes, index)
    height_token, index = read_pgm_token(bytes, index)
    max_gray_token, index = read_pgm_token(bytes, index)

    width = parse_pgm_integer(width_token, "ancho")
    height = parse_pgm_integer(height_token, "alto")
    max_gray = parse_pgm_integer(max_gray_token, "valor maximo de gris")

    validate_pgm_header(width, height, max_gray)

    pixel_count = width * height
    values = if magic == "P2"
        read_ascii_pgm_pixels(bytes, index, pixel_count, max_gray)
    else
        read_binary_pgm_pixels(bytes, index, pixel_count, max_gray)
    end

    pixels = reshape(values, width, height)'

    return PgmImage(width, height, max_gray, Matrix{Int}(pixels))
end

function build_simulation_space(
    image::PgmImage;
    obstacle_threshold::Int = DEFAULT_OBSTACLE_THRESHOLD,
)
    if !(1 <= obstacle_threshold <= image.max_gray)
        throw(ArgumentError("El umbral de obstaculos debe estar entre 1 y max_gray."))
    end

    normalized_intensities = Float64.(image.pixels) ./ image.max_gray
    obstacles = SimulationObstacle[]

    for y_index in 1:image.height
        for x_index in 1:image.width
            intensity = image.pixels[y_index, x_index]

            if intensity >= obstacle_threshold
                x = x_index - 1
                y = y_index - 1
                normalized_intensity = normalized_intensities[y_index, x_index]
                radius = obstacle_radius(intensity, image.max_gray)

                push!(
                    obstacles,
                    SimulationObstacle(
                        x,
                        y,
                        x + 0.5,
                        y + 0.5,
                        intensity,
                        normalized_intensity,
                        radius,
                    ),
                )
            end
        end
    end

    return SimulationSpace(
        image.width,
        image.height,
        image.max_gray,
        obstacle_threshold,
        normalized_intensities,
        obstacles,
    )
end

function obstacle_radius(intensity::Int, max_gray::Int)
    # Mirrors the mammography radius idea used by the C reference while allowing arbitrary PGM max_gray values.
    return 0.5 - (intensity / (max_gray + 1)) * 0.5
end

function write_space_summary(path::AbstractString, space::SimulationSpace)
    cell_count = space.width * space.height
    obstacle_count = length(space.obstacles)
    obstacle_fraction = obstacle_count / cell_count

    open(path, "w") do io
        println(io, "width=$(space.width)")
        println(io, "height=$(space.height)")
        println(io, "max_gray=$(space.max_gray)")
        println(io, "cell_count=$(cell_count)")
        println(io, "obstacle_threshold=$(space.obstacle_threshold)")
        println(io, "obstacle_count=$(obstacle_count)")
        println(io, "obstacle_fraction=$(obstacle_fraction)")
        println(io, "normalized_min=$(minimum(space.normalized_intensities))")
        println(io, "normalized_max=$(maximum(space.normalized_intensities))")
        println(io, "radius_model=mammography_c_reference")

        if isempty(space.obstacles)
            println(io, "radius_min=")
            println(io, "radius_max=")
        else
            radii = [obstacle.radius for obstacle in space.obstacles]
            println(io, "radius_min=$(minimum(radii))")
            println(io, "radius_max=$(maximum(radii))")
        end
    end
end

function write_obstacles_tsv(path::AbstractString, obstacles::Vector{SimulationObstacle})
    open(path, "w") do io
        println(io, "x\ty\tcenter_x\tcenter_y\tintensity\tnormalized_intensity\tradius")

        for obstacle in obstacles
            println(
                io,
                "$(obstacle.x)\t$(obstacle.y)\t$(obstacle.center_x)\t$(obstacle.center_y)\t$(obstacle.intensity)\t$(obstacle.normalized_intensity)\t$(obstacle.radius)",
            )
        end
    end
end

function read_ascii_pgm_pixels(bytes::Vector{UInt8}, index::Int, pixel_count::Int, max_gray::Int)
    values = Vector{Int}(undef, pixel_count)

    for position in 1:pixel_count
        token, index = read_pgm_token(bytes, index)
        value = parse_pgm_integer(token, "intensidad")
        validate_pgm_pixel(value, max_gray)
        values[position] = value
    end

    trailing_index = skip_pgm_whitespace_and_comments(bytes, index)
    if trailing_index <= length(bytes)
        throw(ArgumentError("El archivo PGM contiene datos adicionales despues de los pixeles esperados."))
    end

    return values
end

function read_binary_pgm_pixels(bytes::Vector{UInt8}, index::Int, pixel_count::Int, max_gray::Int)
    index = skip_single_binary_separator(bytes, index)
    bytes_per_pixel = max_gray <= 255 ? 1 : 2
    expected_bytes = pixel_count * bytes_per_pixel
    available_bytes = length(bytes) - index + 1

    if available_bytes < expected_bytes
        throw(ArgumentError("El archivo PGM binario no contiene todos los pixeles esperados."))
    end

    if available_bytes > expected_bytes
        throw(ArgumentError("El archivo PGM binario contiene datos adicionales despues de los pixeles esperados."))
    end

    values = Vector{Int}(undef, pixel_count)

    if bytes_per_pixel == 1
        for position in 1:pixel_count
            value = Int(bytes[index + position - 1])
            validate_pgm_pixel(value, max_gray)
            values[position] = value
        end
    else
        cursor = index
        for position in 1:pixel_count
            value = Int(bytes[cursor]) * 256 + Int(bytes[cursor + 1])
            validate_pgm_pixel(value, max_gray)
            values[position] = value
            cursor += 2
        end
    end

    return values
end

function read_pgm_token(bytes::Vector{UInt8}, index::Int)
    index = skip_pgm_whitespace_and_comments(bytes, index)

    if index > length(bytes)
        throw(ArgumentError("Archivo PGM incompleto."))
    end

    start_index = index
    while index <= length(bytes) && !is_pgm_whitespace(bytes[index]) && bytes[index] != UInt8('#')
        index += 1
    end

    if start_index == index
        throw(ArgumentError("No se pudo leer un token valido del archivo PGM."))
    end

    return String(bytes[start_index:index - 1]), index
end

function skip_pgm_whitespace_and_comments(bytes::Vector{UInt8}, index::Int)
    while index <= length(bytes)
        if is_pgm_whitespace(bytes[index])
            index += 1
            continue
        end

        if bytes[index] == UInt8('#')
            index += 1
            while index <= length(bytes) && !(bytes[index] in (UInt8('\n'), UInt8('\r')))
                index += 1
            end
            continue
        end

        break
    end

    return index
end

function skip_single_binary_separator(bytes::Vector{UInt8}, index::Int)
    if index > length(bytes) || !is_pgm_whitespace(bytes[index])
        throw(ArgumentError("El encabezado PGM binario debe terminar con un separador de espacio."))
    end

    return index + 1
end

function parse_pgm_integer(value::String, field_name::String)
    try
        return parse(Int, value)
    catch
        throw(ArgumentError("El campo $(field_name) del PGM debe ser un entero."))
    end
end

function validate_pgm_header(width::Int, height::Int, max_gray::Int)
    if width <= 0
        throw(ArgumentError("El ancho del PGM debe ser mayor a cero."))
    end

    if height <= 0
        throw(ArgumentError("El alto del PGM debe ser mayor a cero."))
    end

    if !(1 <= max_gray <= 65535)
        throw(ArgumentError("El valor maximo de gris debe estar entre 1 y 65535."))
    end
end

function validate_pgm_pixel(value::Int, max_gray::Int)
    if !(0 <= value <= max_gray)
        throw(ArgumentError("Intensidad fuera de rango: $(value)."))
    end
end

function is_pgm_whitespace(byte::UInt8)
    return byte in (UInt8(' '), UInt8('\t'), UInt8('\n'), UInt8('\r'), UInt8('\v'), UInt8('\f'))
end

end
