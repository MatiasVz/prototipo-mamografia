module MammographySimulation

using Dates
using Random

export PgmImage,
    SimulationObstacle,
    SimulationParticle,
    PreliminarySimulationMetrics,
    PreliminarySimulationResults,
    SimulationResult,
    SimulationSpace,
    SimulationRunConfig,
    read_pgm,
    build_simulation_space,
    run_minimal_simulation,
    generate_preliminary_results,
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

mutable struct SimulationParticle
    id::Int
    x::Int
    y::Int
end

struct SimulationResult
    steps::Int
    seed::Int
    particle_density::Float64
    particles::Vector{SimulationParticle}
    visit_counts::Matrix{Int}
    attempted_moves::Int
    collision_count::Int
end

struct PreliminarySimulationMetrics
    status::String
    simulation_model::String
    width::Int
    height::Int
    cell_count::Int
    obstacle_count::Int
    free_cell_count::Int
    particle_count::Int
    steps::Int
    seed::Int
    particle_density::Float64
    attempted_moves::Int
    collision_count::Int
    collision_rate::Float64
    visited_cell_count::Int
    visit_count_total::Int
    max_visits::Int
    mean_visits_per_cell::Float64
    mean_visits_per_free_cell::Float64
end

struct PreliminarySimulationResults
    metrics_path::String
    density_map_path::String
    density_matrix_path::String
    metrics::PreliminarySimulationMetrics
end

const DEFAULT_OBSTACLE_THRESHOLD = 1

Base.@kwdef struct SimulationRunConfig
    input_path::String
    output_dir::String
    seed::Int = 1234
    steps::Int = 10
    particle_density::Float64 = 0.25
end

const USAGE = """
Uso:
  julia --project=simulator simulator/scripts/run_case.jl --input <archivo.pgm> --output <directorio> [--seed <entero>] [--steps <entero>] [--density <decimal>]

Opciones:
  --input    Ruta del archivo PGM preparado para simulacion.
  --output   Directorio donde se escribiran los resultados.
  --seed     Semilla reproducible para etapas posteriores. Por defecto: 1234.
  --steps    Numero de pasos de simulacion. Por defecto: 10.
  --density  Densidad inicial de particulas sobre celdas libres. Por defecto: 0.25.
  --help     Muestra esta ayuda.
"""

const VALUE_OPTIONS = Set(["--input", "--output", "--seed", "--steps", "--density"])

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
    steps = parse_integer_option(get(options, "--steps", "10"), "--steps")
    particle_density = parse_float_option(get(options, "--density", "0.25"), "--density")

    if steps < 0
        throw(ArgumentError("La opcion --steps no puede ser negativa."))
    end

    if !(0.0 <= particle_density <= 1.0)
        throw(ArgumentError("La opcion --density debe estar entre 0.0 y 1.0."))
    end

    return SimulationRunConfig(
        input_path = input_path,
        output_dir = output_dir,
        seed = seed,
        steps = steps,
        particle_density = particle_density,
    )
end

function run_case(config::SimulationRunConfig)
    input_path = abspath(config.input_path)
    output_dir = abspath(config.output_dir)
    pgm_image = read_pgm(input_path)
    simulation_space = build_simulation_space(pgm_image)
    simulation_result = run_minimal_simulation(
        simulation_space;
        seed = config.seed,
        steps = config.steps,
        particle_density = config.particle_density,
    )

    mkpath(output_dir)

    timestamp = Dates.format(Dates.now(), dateformat"yyyy-mm-ddTHH:MM:SS")
    log_path = joinpath(output_dir, "simulation.log")
    config_path = joinpath(output_dir, "simulation_config.txt")
    summary_path = joinpath(output_dir, "input_summary.txt")
    space_summary_path = joinpath(output_dir, "space_summary.txt")
    obstacles_path = joinpath(output_dir, "obstacles.tsv")
    simulation_summary_path = joinpath(output_dir, "simulation_summary.txt")
    simulation_state_path = joinpath(output_dir, "simulation_state.tsv")
    visit_counts_path = joinpath(output_dir, "visit_counts.tsv")

    open(log_path, "w") do io
        println(io, "MammographySimulation")
        println(io, "status=preliminary_results_ready")
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
        println(io, "particle_density=$(config.particle_density)")
        println(io, "particle_count=$(length(simulation_result.particles))")
        println(io, "attempted_moves=$(simulation_result.attempted_moves)")
        println(io, "collision_count=$(simulation_result.collision_count)")
        println(io, "message=Simulacion minima secuencial ejecutada y resultados preliminares generados.")
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
        println(io, "particle_density=$(config.particle_density)")
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
    write_simulation_summary(simulation_summary_path, simulation_result, simulation_space)
    write_simulation_state(simulation_state_path, simulation_result.particles)
    write_visit_counts(visit_counts_path, simulation_result.visit_counts)
    preliminary_results = generate_preliminary_results(output_dir, simulation_result, simulation_space)

    return (
        log_path = log_path,
        config_path = config_path,
        summary_path = summary_path,
        space_summary_path = space_summary_path,
        obstacles_path = obstacles_path,
        simulation_summary_path = simulation_summary_path,
        simulation_state_path = simulation_state_path,
        visit_counts_path = visit_counts_path,
        metrics_path = preliminary_results.metrics_path,
        density_map_path = preliminary_results.density_map_path,
        density_matrix_path = preliminary_results.density_matrix_path,
        image = pgm_image,
        space = simulation_space,
        simulation = simulation_result,
        preliminary_results = preliminary_results,
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
        println("Simulacion mesoscopica minima ejecutada correctamente.")
        println("log_path=$(result.log_path)")
        println("config_path=$(result.config_path)")
        println("summary_path=$(result.summary_path)")
        println("space_summary_path=$(result.space_summary_path)")
        println("obstacles_path=$(result.obstacles_path)")
        println("simulation_summary_path=$(result.simulation_summary_path)")
        println("simulation_state_path=$(result.simulation_state_path)")
        println("visit_counts_path=$(result.visit_counts_path)")
        println("metrics_path=$(result.metrics_path)")
        println("density_map_path=$(result.density_map_path)")
        println("density_matrix_path=$(result.density_matrix_path)")
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

function parse_float_option(value::String, option_name::String)
    try
        return parse(Float64, value)
    catch
        throw(ArgumentError("La opcion $(option_name) debe ser un numero decimal."))
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

function run_minimal_simulation(
    space::SimulationSpace;
    seed::Int = 1234,
    steps::Int = 10,
    particle_density::Float64 = 0.25,
)
    if steps < 0
        throw(ArgumentError("El numero de pasos de simulacion no puede ser negativo."))
    end

    if !(0.0 <= particle_density <= 1.0)
        throw(ArgumentError("La densidad inicial de particulas debe estar entre 0.0 y 1.0."))
    end

    rng = Random.MersenneTwister(seed)
    obstacle_grid = build_obstacle_grid(space)
    free_cells = collect_free_cells(obstacle_grid)
    particle_count = determine_particle_count(length(free_cells), particle_density)
    particles = initialize_particles(free_cells, particle_count, rng)
    visit_counts = zeros(Int, space.height, space.width)

    for particle in particles
        visit_counts[particle.y + 1, particle.x + 1] += 1
    end

    attempted_moves = 0
    collision_count = 0
    directions = ((1, 0), (-1, 0), (0, 1), (0, -1))

    for _step in 1:steps
        for particle in particles
            dx, dy = directions[rand(rng, 1:length(directions))]
            next_x = mod(particle.x + dx, space.width)
            next_y = mod(particle.y + dy, space.height)

            attempted_moves += 1

            if obstacle_grid[next_y + 1, next_x + 1]
                collision_count += 1
            else
                particle.x = next_x
                particle.y = next_y
                visit_counts[particle.y + 1, particle.x + 1] += 1
            end
        end
    end

    return SimulationResult(
        steps,
        seed,
        particle_density,
        particles,
        visit_counts,
        attempted_moves,
        collision_count,
    )
end

function build_obstacle_grid(space::SimulationSpace)
    obstacle_grid = falses(space.height, space.width)

    for obstacle in space.obstacles
        obstacle_grid[obstacle.y + 1, obstacle.x + 1] = true
    end

    return obstacle_grid
end

function collect_free_cells(obstacle_grid::BitMatrix)
    height, width = size(obstacle_grid)
    free_cells = Tuple{Int,Int}[]

    for y_index in 1:height
        for x_index in 1:width
            if !obstacle_grid[y_index, x_index]
                push!(free_cells, (x_index - 1, y_index - 1))
            end
        end
    end

    return free_cells
end

function determine_particle_count(free_cell_count::Int, particle_density::Float64)
    if free_cell_count == 0 || particle_density == 0.0
        return 0
    end

    return min(free_cell_count, max(1, round(Int, free_cell_count * particle_density)))
end

function initialize_particles(free_cells::Vector{Tuple{Int,Int}}, particle_count::Int, rng::Random.AbstractRNG)
    if particle_count == 0
        return SimulationParticle[]
    end

    selected_cells = Random.shuffle(rng, free_cells)[1:particle_count]

    return [
        SimulationParticle(index, x, y)
        for (index, (x, y)) in enumerate(selected_cells)
    ]
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

function write_simulation_summary(path::AbstractString, result::SimulationResult, space::SimulationSpace)
    free_cell_count = space.width * space.height - length(space.obstacles)

    open(path, "w") do io
        println(io, "steps=$(result.steps)")
        println(io, "seed=$(result.seed)")
        println(io, "particle_density=$(result.particle_density)")
        println(io, "particle_count=$(length(result.particles))")
        println(io, "free_cell_count=$(free_cell_count)")
        println(io, "attempted_moves=$(result.attempted_moves)")
        println(io, "collision_count=$(result.collision_count)")
        println(io, "visited_cell_count=$(count(>(0), result.visit_counts))")
        println(io, "visit_count_total=$(sum(result.visit_counts))")
        println(io, "simulation_model=sequential_minimal_random_walk")
    end
end

function write_simulation_state(path::AbstractString, particles::Vector{SimulationParticle})
    open(path, "w") do io
        println(io, "id\tx\ty")

        for particle in particles
            println(io, "$(particle.id)\t$(particle.x)\t$(particle.y)")
        end
    end
end

function write_visit_counts(path::AbstractString, visit_counts::Matrix{Int})
    open(path, "w") do io
        println(io, "x\ty\tvisits")

        for y_index in axes(visit_counts, 1)
            for x_index in axes(visit_counts, 2)
                println(io, "$(x_index - 1)\t$(y_index - 1)\t$(visit_counts[y_index, x_index])")
            end
        end
    end
end

function generate_preliminary_results(
    output_dir::AbstractString,
    result::SimulationResult,
    space::SimulationSpace,
)
    mkpath(output_dir)

    metrics = build_preliminary_metrics(result, space)
    metrics_path = joinpath(output_dir, "metrics.json")
    density_map_path = joinpath(output_dir, "density_map.pgm")
    density_matrix_path = joinpath(output_dir, "density_matrix.tsv")

    write_metrics_json(metrics_path, metrics)
    write_density_map_pgm(density_map_path, result.visit_counts)
    write_density_matrix_tsv(density_matrix_path, result.visit_counts, space)

    return PreliminarySimulationResults(
        metrics_path,
        density_map_path,
        density_matrix_path,
        metrics,
    )
end

function build_preliminary_metrics(result::SimulationResult, space::SimulationSpace)
    cell_count = space.width * space.height
    obstacle_count = length(space.obstacles)
    free_cell_count = cell_count - obstacle_count
    particle_count = length(result.particles)
    visited_cell_count = count(>(0), result.visit_counts)
    visit_count_total = sum(result.visit_counts)
    max_visits = maximum(result.visit_counts)

    return PreliminarySimulationMetrics(
        "preliminary_results_ready",
        "sequential_minimal_random_walk",
        space.width,
        space.height,
        cell_count,
        obstacle_count,
        free_cell_count,
        particle_count,
        result.steps,
        result.seed,
        result.particle_density,
        result.attempted_moves,
        result.collision_count,
        safe_ratio(result.collision_count, result.attempted_moves),
        visited_cell_count,
        visit_count_total,
        max_visits,
        safe_ratio(visit_count_total, cell_count),
        safe_ratio(visit_count_total, free_cell_count),
    )
end

function write_metrics_json(path::AbstractString, metrics::PreliminarySimulationMetrics)
    fields = [
        ("status", metrics.status),
        ("simulation_model", metrics.simulation_model),
        ("width", metrics.width),
        ("height", metrics.height),
        ("cell_count", metrics.cell_count),
        ("obstacle_count", metrics.obstacle_count),
        ("free_cell_count", metrics.free_cell_count),
        ("particle_count", metrics.particle_count),
        ("steps", metrics.steps),
        ("seed", metrics.seed),
        ("particle_density", metrics.particle_density),
        ("attempted_moves", metrics.attempted_moves),
        ("collision_count", metrics.collision_count),
        ("collision_rate", metrics.collision_rate),
        ("visited_cell_count", metrics.visited_cell_count),
        ("visit_count_total", metrics.visit_count_total),
        ("max_visits", metrics.max_visits),
        ("mean_visits_per_cell", metrics.mean_visits_per_cell),
        ("mean_visits_per_free_cell", metrics.mean_visits_per_free_cell),
    ]

    open(path, "w") do io
        println(io, "{")

        for (index, (key, value)) in enumerate(fields)
            suffix = index == length(fields) ? "" : ","
            println(io, "  \"$(key)\": $(json_value(value))$(suffix)")
        end

        println(io, "}")
    end
end

function write_density_map_pgm(path::AbstractString, visit_counts::Matrix{Int})
    density_values = build_density_values(visit_counts)
    height, width = size(density_values)

    open(path, "w") do io
        println(io, "P2")
        println(io, "# Mapa de densidad preliminar generado por MammographySimulation")
        println(io, "$(width) $(height)")
        println(io, "255")

        for y_index in 1:height
            println(io, join(vec(density_values[y_index, :]), " "))
        end
    end
end

function write_density_matrix_tsv(
    path::AbstractString,
    visit_counts::Matrix{Int},
    space::SimulationSpace,
)
    density_values = build_density_values(visit_counts)
    obstacle_grid = build_obstacle_grid(space)

    open(path, "w") do io
        println(io, "x\ty\tvisits\tdensity_value\tis_obstacle")

        for y_index in axes(visit_counts, 1)
            for x_index in axes(visit_counts, 2)
                println(
                    io,
                    "$(x_index - 1)\t$(y_index - 1)\t$(visit_counts[y_index, x_index])\t$(density_values[y_index, x_index])\t$(obstacle_grid[y_index, x_index])",
                )
            end
        end
    end
end

function build_density_values(visit_counts::Matrix{Int})
    max_visits = maximum(visit_counts)
    density_values = zeros(Int, size(visit_counts))

    if max_visits == 0
        return density_values
    end

    for index in eachindex(visit_counts)
        density_values[index] = round(Int, visit_counts[index] / max_visits * 255)
    end

    return density_values
end

function safe_ratio(numerator::Real, denominator::Real)
    if denominator == 0
        return 0.0
    end

    return numerator / denominator
end

function json_value(value::String)
    escaped = replace(value, "\\" => "\\\\", "\"" => "\\\"", "\n" => "\\n")
    return "\"$(escaped)\""
end

function json_value(value::Integer)
    return string(value)
end

function json_value(value::AbstractFloat)
    if !isfinite(value)
        return "null"
    end

    return string(value)
end

function json_value(value::Bool)
    return value ? "true" : "false"
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
