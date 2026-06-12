module MammographySimulation

using Dates
using Random

export PgmImage,
    MpcModelConfig,
    MpcParticle,
    MpcParticleInitialization,
    SimulationObstacle,
    SimulationParticle,
    PreliminarySimulationMetrics,
    PreliminarySimulationResults,
    SimulationResult,
    SimulationSpace,
    SimulationRunConfig,
    read_pgm,
    build_simulation_space,
    initialize_mpc_particles,
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
    center_z::Float64
    intensity::Int
    normalized_intensity::Float64
    radius::Float64
    height::Float64
    preliminary_blocking::Bool
end

struct SimulationSpace
    width::Int
    height::Int
    cell_length::Float64
    lx::Float64
    ly::Float64
    lz::Int
    max_gray::Int
    tissue_threshold::Int
    obstacle_threshold::Int
    domain_mask::BitMatrix
    normalized_intensities::Matrix{Float64}
    obstacles::Vector{SimulationObstacle}
end

mutable struct SimulationParticle
    id::Int
    x::Int
    y::Int
end

struct MpcParticle
    id::Int
    x::Float64
    y::Float64
    z::Float64
    vx::Float64
    vy::Float64
    vz::Float64
    mass::Float64
    species::String
    labeled::Bool
end

struct MpcParticleInitialization
    seed::Int
    target_particle_count::Int
    domain_volume::Float64
    velocity_sigma::Float64
    rejected_samples::Int
    particles::Vector{MpcParticle}
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
    domain_cell_count::Int
    excluded_background_count::Int
    obstacle_count::Int
    preliminary_blocking_obstacle_count::Int
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
    domain_mask_path::String
    density_map_path::String
    density_matrix_path::String
    metrics::PreliminarySimulationMetrics
end

const DEFAULT_TISSUE_THRESHOLD_RATIO = 0.03
const DEFAULT_OBSTACLE_THRESHOLD_RATIO = 0.85
const SIMULATION_ENGINE_PRELIMINARY = "sequential_minimal_random_walk"
const MPC_CONFIGURATION_MODEL = "mpc_base_configuration"
const DEFAULT_MPC_INPUT_ROLE = "confirmed_roi_pgm"
const DEFAULT_MPC_CELL_LENGTH = 1.0
const DEFAULT_MPC_LZ = 1
const DEFAULT_MPC_N0 = 10.0
const DEFAULT_MPC_MASS = 1.0
const DEFAULT_MPC_KBT = 1.0
const DEFAULT_MPC_TAU = 1.0
const DEFAULT_MPC_ROTATION_ANGLE = pi / 2
const DEFAULT_MPC_ROTATION_POLICY = "random_sign_plus_minus_angle"
const DEFAULT_MPC_REALIZATIONS = 1
const DEFAULT_MPC_LABELED_PARTICLES = 0
const DEFAULT_MPC_OUTPUT_TIMES = (0, 100, 500)
const DEFAULT_MPC_GRID_SHIFT_ENABLED = false
const DEFAULT_MPC_GRID_SHIFT_DECISION = "disabled_initially_to_match_article_conditions"

Base.@kwdef struct MpcModelConfig
    input_role::String = DEFAULT_MPC_INPUT_ROLE
    cell_length::Float64 = DEFAULT_MPC_CELL_LENGTH
    lz::Int = DEFAULT_MPC_LZ
    n0::Float64 = DEFAULT_MPC_N0
    mass::Float64 = DEFAULT_MPC_MASS
    kbt::Float64 = DEFAULT_MPC_KBT
    tau::Float64 = DEFAULT_MPC_TAU
    rotation_angle::Float64 = DEFAULT_MPC_ROTATION_ANGLE
    rotation_policy::String = DEFAULT_MPC_ROTATION_POLICY
    realizations::Int = DEFAULT_MPC_REALIZATIONS
    labeled_particles::Int = DEFAULT_MPC_LABELED_PARTICLES
    output_times::Vector{Int} = collect(DEFAULT_MPC_OUTPUT_TIMES)
    grid_shift_enabled::Bool = DEFAULT_MPC_GRID_SHIFT_ENABLED
    grid_shift_decision::String = DEFAULT_MPC_GRID_SHIFT_DECISION
end

Base.@kwdef struct SimulationRunConfig
    input_path::String
    output_dir::String
    seed::Int = 1234
    steps::Int = 10
    particle_density::Float64 = 0.25
    mpc_config::MpcModelConfig = MpcModelConfig()
end

const USAGE = """
Uso:
  julia --project=simulator simulator/scripts/run_case.jl --input <roi_confirmada.pgm> --output <directorio> [opciones]

Opciones:
  --input              Ruta de la ROI confirmada convertida a PGM.
  --output             Directorio donde se escribiran los resultados.
  --seed               Semilla reproducible. Por defecto: 1234.
  --steps              Numero de pasos de simulacion. Por defecto: 10.
  --density            Densidad preliminar usada por el motor secuencial actual. Por defecto: 0.25.
  --n0                 Densidad media MPC de particulas por celda. Por defecto: 10.
  --mass               Masa reducida de particula MPC. Por defecto: 1.
  --kbt                Temperatura reducida kBT. Por defecto: 1.
  --tau                Paso temporal reducido. Por defecto: 1.
  --rotation-angle     Angulo de rotacion MPC en radianes. Por defecto: pi/2.
  --realizations       Numero de realizaciones estadisticas. Por defecto: 1.
  --labeled-particles  Particulas etiquetadas para autocorrelacion. Por defecto: 0.
  --output-times       Tiempos de salida separados por coma. Por defecto: 0,100,500.
  --grid-shift         true/false. Por defecto: false.
  --help               Muestra esta ayuda.
"""

const VALUE_OPTIONS = Set([
    "--input",
    "--output",
    "--seed",
    "--steps",
    "--density",
    "--n0",
    "--mass",
    "--kbt",
    "--tau",
    "--rotation-angle",
    "--realizations",
    "--labeled-particles",
    "--output-times",
    "--grid-shift",
])

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
    mpc_config = parse_mpc_config(options)

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
        mpc_config = mpc_config,
    )
end

function run_case(config::SimulationRunConfig)
    validate_mpc_config(config.mpc_config)

    input_path = abspath(config.input_path)
    output_dir = abspath(config.output_dir)
    pgm_image = read_pgm(input_path)
    simulation_space = build_simulation_space(pgm_image; mpc_config = config.mpc_config)
    mpc_initialization = initialize_mpc_particles(
        simulation_space,
        config.mpc_config;
        seed = config.seed,
    )
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
    mpc_config_path = joinpath(output_dir, "mpc_config.json")
    summary_path = joinpath(output_dir, "input_summary.txt")
    space_summary_path = joinpath(output_dir, "space_summary.txt")
    obstacles_path = joinpath(output_dir, "obstacles.tsv")
    obstacle_radius_matrix_path = joinpath(output_dir, "obstacle_radius_matrix.tsv")
    obstacle_radius_map_path = joinpath(output_dir, "obstacle_radius_map.pgm")
    obstacle_radius_histogram_path = joinpath(output_dir, "obstacle_radius_histogram.tsv")
    mpc_initial_particles_path = joinpath(output_dir, "mpc_initial_particles.tsv")
    simulation_summary_path = joinpath(output_dir, "simulation_summary.txt")
    simulation_state_path = joinpath(output_dir, "simulation_state.tsv")
    visit_counts_path = joinpath(output_dir, "visit_counts.tsv")

    open(log_path, "w") do io
        println(io, "MammographySimulation")
        println(io, "status=preliminary_results_ready")
        println(io, "created_at=$(timestamp)")
        println(io, "input_path=$(input_path)")
        println(io, "output_dir=$(output_dir)")
        println(io, "input_role=$(config.mpc_config.input_role)")
        println(io, "configuration_model=$(MPC_CONFIGURATION_MODEL)")
        println(io, "execution_engine=$(SIMULATION_ENGINE_PRELIMINARY)")
        println(io, "lx=$(mpc_box_lx(simulation_space, config.mpc_config))")
        println(io, "ly=$(mpc_box_ly(simulation_space, config.mpc_config))")
        println(io, "lz=$(config.mpc_config.lz)")
        println(io, "width=$(pgm_image.width)")
        println(io, "height=$(pgm_image.height)")
        println(io, "max_gray=$(pgm_image.max_gray)")
        println(io, "tissue_threshold=$(simulation_space.tissue_threshold)")
        println(io, "obstacle_count=$(length(simulation_space.obstacles))")
        println(io, "preliminary_blocking_obstacle_count=$(count_preliminary_blocking_obstacles(simulation_space))")
        println(io, "obstacle_threshold=$(simulation_space.obstacle_threshold)")
        println(io, "domain_cell_count=$(count_domain_cells(simulation_space))")
        println(io, "excluded_background_count=$(count_excluded_background_cells(simulation_space))")
        println(io, "seed=$(config.seed)")
        println(io, "steps=$(config.steps)")
        println(io, "particle_density=$(config.particle_density)")
        println(io, "n0=$(config.mpc_config.n0)")
        println(io, "mass=$(config.mpc_config.mass)")
        println(io, "kbt=$(config.mpc_config.kbt)")
        println(io, "tau=$(config.mpc_config.tau)")
        println(io, "rotation_angle=$(config.mpc_config.rotation_angle)")
        println(io, "rotation_policy=$(config.mpc_config.rotation_policy)")
        println(io, "realizations=$(config.mpc_config.realizations)")
        println(io, "labeled_particles=$(config.mpc_config.labeled_particles)")
        println(io, "output_times=$(join(config.mpc_config.output_times, ","))")
        println(io, "grid_shift_enabled=$(config.mpc_config.grid_shift_enabled)")
        println(io, "grid_shift_decision=$(config.mpc_config.grid_shift_decision)")
        println(io, "particle_count=$(length(simulation_result.particles))")
        println(io, "mpc_particle_count=$(length(mpc_initialization.particles))")
        println(io, "mpc_domain_volume=$(mpc_initialization.domain_volume)")
        println(io, "mpc_velocity_sigma=$(mpc_initialization.velocity_sigma)")
        println(io, "mpc_rejected_samples=$(mpc_initialization.rejected_samples)")
        println(io, "attempted_moves=$(simulation_result.attempted_moves)")
        println(io, "collision_count=$(simulation_result.collision_count)")
        println(io, "message=Simulacion minima secuencial ejecutada y resultados preliminares generados.")
    end

    open(config_path, "w") do io
        println(io, "input_path=$(input_path)")
        println(io, "output_dir=$(output_dir)")
        println(io, "input_role=$(config.mpc_config.input_role)")
        println(io, "configuration_model=$(MPC_CONFIGURATION_MODEL)")
        println(io, "execution_engine=$(SIMULATION_ENGINE_PRELIMINARY)")
        println(io, "cell_length=$(config.mpc_config.cell_length)")
        println(io, "lx=$(mpc_box_lx(simulation_space, config.mpc_config))")
        println(io, "ly=$(mpc_box_ly(simulation_space, config.mpc_config))")
        println(io, "lz=$(config.mpc_config.lz)")
        println(io, "width=$(pgm_image.width)")
        println(io, "height=$(pgm_image.height)")
        println(io, "max_gray=$(pgm_image.max_gray)")
        println(io, "tissue_threshold=$(simulation_space.tissue_threshold)")
        println(io, "obstacle_threshold=$(simulation_space.obstacle_threshold)")
        println(io, "seed=$(config.seed)")
        println(io, "steps=$(config.steps)")
        println(io, "particle_density=$(config.particle_density)")
        println(io, "n0=$(config.mpc_config.n0)")
        println(io, "mass=$(config.mpc_config.mass)")
        println(io, "kbt=$(config.mpc_config.kbt)")
        println(io, "tau=$(config.mpc_config.tau)")
        println(io, "rotation_angle=$(config.mpc_config.rotation_angle)")
        println(io, "rotation_policy=$(config.mpc_config.rotation_policy)")
        println(io, "realizations=$(config.mpc_config.realizations)")
        println(io, "labeled_particles=$(config.mpc_config.labeled_particles)")
        println(io, "output_times=$(join(config.mpc_config.output_times, ","))")
        println(io, "grid_shift_enabled=$(config.mpc_config.grid_shift_enabled)")
        println(io, "grid_shift_decision=$(config.mpc_config.grid_shift_decision)")
        println(io, "created_at=$(timestamp)")
    end

    write_mpc_config_json(
        mpc_config_path,
        config,
        pgm_image,
        simulation_space,
        timestamp;
        mpc_initialization = mpc_initialization,
    )
    open(summary_path, "w") do io
        println(io, "width=$(pgm_image.width)")
        println(io, "height=$(pgm_image.height)")
        println(io, "max_gray=$(pgm_image.max_gray)")
        println(io, "min_intensity=$(minimum(pgm_image.pixels))")
        println(io, "max_intensity=$(maximum(pgm_image.pixels))")
        println(io, "pixel_count=$(length(pgm_image.pixels))")
    end

    write_space_summary(space_summary_path, simulation_space; mpc_config = config.mpc_config)
    write_obstacles_tsv(obstacles_path, simulation_space.obstacles)
    write_obstacle_radius_matrix_tsv(obstacle_radius_matrix_path, simulation_space)
    write_obstacle_radius_map_pgm(obstacle_radius_map_path, simulation_space)
    write_obstacle_radius_histogram_tsv(obstacle_radius_histogram_path, simulation_space)
    write_mpc_initial_particles_tsv(mpc_initial_particles_path, mpc_initialization)
    write_simulation_summary(
        simulation_summary_path,
        simulation_result,
        simulation_space;
        mpc_initialization = mpc_initialization,
    )
    write_simulation_state(simulation_state_path, simulation_result.particles)
    write_visit_counts(visit_counts_path, simulation_result.visit_counts)
    preliminary_results = generate_preliminary_results(output_dir, simulation_result, simulation_space)

    return (
        log_path = log_path,
        config_path = config_path,
        mpc_config_path = mpc_config_path,
        summary_path = summary_path,
        space_summary_path = space_summary_path,
        obstacles_path = obstacles_path,
        obstacle_radius_matrix_path = obstacle_radius_matrix_path,
        obstacle_radius_map_path = obstacle_radius_map_path,
        obstacle_radius_histogram_path = obstacle_radius_histogram_path,
        mpc_initial_particles_path = mpc_initial_particles_path,
        simulation_summary_path = simulation_summary_path,
        simulation_state_path = simulation_state_path,
        visit_counts_path = visit_counts_path,
        metrics_path = preliminary_results.metrics_path,
        domain_mask_path = preliminary_results.domain_mask_path,
        density_map_path = preliminary_results.density_map_path,
        density_matrix_path = preliminary_results.density_matrix_path,
        image = pgm_image,
        space = simulation_space,
        mpc_initialization = mpc_initialization,
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
        println("mpc_config_path=$(result.mpc_config_path)")
        println("summary_path=$(result.summary_path)")
        println("space_summary_path=$(result.space_summary_path)")
        println("obstacles_path=$(result.obstacles_path)")
        println("obstacle_radius_matrix_path=$(result.obstacle_radius_matrix_path)")
        println("obstacle_radius_map_path=$(result.obstacle_radius_map_path)")
        println("obstacle_radius_histogram_path=$(result.obstacle_radius_histogram_path)")
        println("mpc_initial_particles_path=$(result.mpc_initial_particles_path)")
        println("simulation_summary_path=$(result.simulation_summary_path)")
        println("simulation_state_path=$(result.simulation_state_path)")
        println("visit_counts_path=$(result.visit_counts_path)")
        println("metrics_path=$(result.metrics_path)")
        println("domain_mask_path=$(result.domain_mask_path)")
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

function parse_integer_option(value::AbstractString, option_name::String)
    try
        return parse(Int, value)
    catch
        throw(ArgumentError("La opcion $(option_name) debe ser un entero."))
    end
end

function parse_float_option(value::AbstractString, option_name::String)
    try
        return parse(Float64, value)
    catch
        throw(ArgumentError("La opcion $(option_name) debe ser un numero decimal."))
    end
end

function parse_bool_option(value::AbstractString, option_name::String)
    normalized = lowercase(strip(value))

    if normalized in ("true", "1", "yes", "si")
        return true
    end

    if normalized in ("false", "0", "no")
        return false
    end

    throw(ArgumentError("La opcion $(option_name) debe ser true o false."))
end

function parse_output_times_option(value::String)
    stripped = strip(value)

    if isempty(stripped)
        return Int[]
    end

    output_times = Int[]

    for token in split(stripped, ",")
        output_time = parse_integer_option(strip(token), "--output-times")

        if output_time < 0
            throw(ArgumentError("La opcion --output-times no puede contener tiempos negativos."))
        end

        push!(output_times, output_time)
    end

    return output_times
end

function parse_mpc_config(options::Dict{String,String})
    config = MpcModelConfig(
        n0 = parse_float_option(get(options, "--n0", string(DEFAULT_MPC_N0)), "--n0"),
        mass = parse_float_option(get(options, "--mass", string(DEFAULT_MPC_MASS)), "--mass"),
        kbt = parse_float_option(get(options, "--kbt", string(DEFAULT_MPC_KBT)), "--kbt"),
        tau = parse_float_option(get(options, "--tau", string(DEFAULT_MPC_TAU)), "--tau"),
        rotation_angle = parse_float_option(
            get(options, "--rotation-angle", string(DEFAULT_MPC_ROTATION_ANGLE)),
            "--rotation-angle",
        ),
        realizations = parse_integer_option(
            get(options, "--realizations", string(DEFAULT_MPC_REALIZATIONS)),
            "--realizations",
        ),
        labeled_particles = parse_integer_option(
            get(options, "--labeled-particles", string(DEFAULT_MPC_LABELED_PARTICLES)),
            "--labeled-particles",
        ),
        output_times = parse_output_times_option(
            get(options, "--output-times", join(DEFAULT_MPC_OUTPUT_TIMES, ",")),
        ),
        grid_shift_enabled = parse_bool_option(
            get(options, "--grid-shift", string(DEFAULT_MPC_GRID_SHIFT_ENABLED)),
            "--grid-shift",
        ),
    )

    validate_mpc_config(config)

    return config
end

function validate_mpc_config(config::MpcModelConfig)
    if config.input_role != DEFAULT_MPC_INPUT_ROLE
        throw(ArgumentError("La entrada MPC debe ser una ROI confirmada convertida a PGM."))
    end

    if config.cell_length <= 0
        throw(ArgumentError("El lado de celda MPC debe ser mayor que cero."))
    end

    if config.lz != DEFAULT_MPC_LZ
        throw(ArgumentError("La configuracion base usa una caja plana con Lz = 1."))
    end

    if config.n0 <= 0
        throw(ArgumentError("La densidad media MPC n0 debe ser mayor que cero."))
    end

    if config.mass <= 0
        throw(ArgumentError("La masa reducida MPC debe ser mayor que cero."))
    end

    if config.kbt <= 0
        throw(ArgumentError("La temperatura reducida kBT debe ser mayor que cero."))
    end

    if config.tau <= 0
        throw(ArgumentError("El paso temporal tau debe ser mayor que cero."))
    end

    if config.rotation_angle == 0
        throw(ArgumentError("El angulo de rotacion MPC no puede ser cero."))
    end

    if config.realizations < 1
        throw(ArgumentError("Debe existir al menos una realizacion MPC."))
    end

    if config.labeled_particles < 0
        throw(ArgumentError("El numero de particulas etiquetadas no puede ser negativo."))
    end

    if any(<(0), config.output_times)
        throw(ArgumentError("Los tiempos de salida no pueden ser negativos."))
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
    tissue_threshold::Union{Nothing,Int} = nothing,
    obstacle_threshold::Union{Nothing,Int} = nothing,
    mpc_config::MpcModelConfig = MpcModelConfig(),
)
    validate_mpc_config(mpc_config)

    resolved_tissue_threshold = resolve_tissue_threshold(image.max_gray, tissue_threshold)
    resolved_obstacle_threshold = resolve_obstacle_threshold(
        image.max_gray,
        obstacle_threshold,
        resolved_tissue_threshold,
    )

    if !(1 <= resolved_tissue_threshold <= image.max_gray)
        throw(ArgumentError("El umbral de tejido debe estar entre 1 y max_gray."))
    end

    if !(1 <= resolved_obstacle_threshold <= image.max_gray)
        throw(ArgumentError("El umbral de obstaculos debe estar entre 1 y max_gray."))
    end

    normalized_intensities = Float64.(image.pixels) ./ image.max_gray
    domain_mask = detect_breast_domain_mask(image.pixels, resolved_tissue_threshold)
    obstacles = SimulationObstacle[]
    preliminary_blocking_radius = obstacle_radius(resolved_obstacle_threshold, image.max_gray)

    for y_index in 1:image.height
        for x_index in 1:image.width
            if !domain_mask[y_index, x_index]
                continue
            end

            intensity = image.pixels[y_index, x_index]
            x = x_index - 1
            y = y_index - 1
            normalized_intensity = normalized_intensities[y_index, x_index]
            radius = obstacle_radius(intensity, image.max_gray)
            preliminary_blocking = radius >= preliminary_blocking_radius

            push!(
                obstacles,
                SimulationObstacle(
                    x,
                    y,
                    (x + 0.5) * mpc_config.cell_length,
                    (y + 0.5) * mpc_config.cell_length,
                    mpc_config.lz / 2,
                    intensity,
                    normalized_intensity,
                    radius * mpc_config.cell_length,
                    mpc_config.lz,
                    preliminary_blocking,
                ),
            )
        end
    end

    return SimulationSpace(
        image.width,
        image.height,
        mpc_config.cell_length,
        image.width * mpc_config.cell_length,
        image.height * mpc_config.cell_length,
        mpc_config.lz,
        image.max_gray,
        resolved_tissue_threshold,
        resolved_obstacle_threshold,
        domain_mask,
        normalized_intensities,
        obstacles,
    )
end

function initialize_mpc_particles(
    space::SimulationSpace,
    config::MpcModelConfig;
    seed::Int = 1234,
)
    validate_mpc_config(config)

    target_particle_count = determine_mpc_particle_count(space, config)
    domain_cells = collect_domain_cells(space.domain_mask)
    velocity_sigma = sqrt(config.kbt / config.mass)
    rng = Random.MersenneTwister(seed)
    particles = MpcParticle[]
    rejected_samples = 0
    max_attempts = max(1000, target_particle_count * 1000)
    attempts = 0

    if isempty(domain_cells) && target_particle_count > 0
        throw(ArgumentError("No existen celdas de dominio para inicializar particulas MPC."))
    end

    while length(particles) < target_particle_count
        attempts += 1

        if attempts > max_attempts
            throw(ArgumentError("No se pudieron ubicar particulas MPC fuera de los obstaculos cilindricos."))
        end

        cell_x, cell_y = rand(rng, domain_cells)
        x = (cell_x + rand(rng)) * space.cell_length
        y = (cell_y + rand(rng)) * space.cell_length
        z = rand(rng) * space.lz

        if point_inside_cell_obstacle(space, x, y, cell_x, cell_y)
            rejected_samples += 1
            continue
        end

        particle_id = length(particles) + 1
        vx = randn(rng) * velocity_sigma
        vy = randn(rng) * velocity_sigma
        vz = randn(rng) * velocity_sigma
        labeled = particle_id <= min(config.labeled_particles, target_particle_count)

        push!(
            particles,
            MpcParticle(
                particle_id,
                x,
                y,
                z,
                vx,
                vy,
                vz,
                config.mass,
                "fluid",
                labeled,
            ),
        )
    end

    return MpcParticleInitialization(
        seed,
        target_particle_count,
        mpc_domain_volume(space),
        velocity_sigma,
        rejected_samples,
        particles,
    )
end

function determine_mpc_particle_count(space::SimulationSpace, config::MpcModelConfig)
    volume = mpc_domain_volume(space)

    if volume <= 0
        return 0
    end

    return max(1, round(Int, config.n0 * volume))
end

function mpc_domain_volume(space::SimulationSpace)
    return count_domain_cells(space) * space.cell_length^2 * space.lz
end

function collect_domain_cells(domain_mask::BitMatrix)
    height, width = size(domain_mask)
    cells = Tuple{Int,Int}[]

    for y_index in 1:height
        for x_index in 1:width
            if domain_mask[y_index, x_index]
                push!(cells, (x_index - 1, y_index - 1))
            end
        end
    end

    return cells
end

function point_inside_cell_obstacle(
    space::SimulationSpace,
    x::Float64,
    y::Float64,
    cell_x::Int,
    cell_y::Int,
)
    obstacle = obstacle_at_cell(space, cell_x, cell_y)

    if obstacle === nothing || obstacle.radius <= 0
        return false
    end

    dx = x - obstacle.center_x
    dy = y - obstacle.center_y

    return dx^2 + dy^2 < obstacle.radius^2
end

function obstacle_at_cell(space::SimulationSpace, cell_x::Int, cell_y::Int)
    for obstacle in space.obstacles
        if obstacle.x == cell_x && obstacle.y == cell_y
            return obstacle
        end
    end

    return nothing
end

function resolve_tissue_threshold(max_gray::Int, tissue_threshold::Union{Nothing,Int})
    if tissue_threshold !== nothing
        return tissue_threshold
    end

    return clamp(round(Int, max_gray * DEFAULT_TISSUE_THRESHOLD_RATIO), 1, max_gray)
end

function resolve_obstacle_threshold(
    max_gray::Int,
    obstacle_threshold::Union{Nothing,Int},
    tissue_threshold::Int,
)
    if obstacle_threshold !== nothing
        return obstacle_threshold
    end

    return clamp(round(Int, max_gray * DEFAULT_OBSTACLE_THRESHOLD_RATIO), tissue_threshold, max_gray)
end

function detect_breast_domain_mask(pixels::Matrix{Int}, tissue_threshold::Int)
    tissue_candidates = pixels .>= tissue_threshold
    component_mask = largest_connected_component(tissue_candidates)

    if count(component_mask) == 0
        throw(ArgumentError("No se detecto una region mamaria valida en la imagen PGM."))
    end

    return fill_internal_background(component_mask)
end

function largest_connected_component(mask::BitMatrix)
    height, width = size(mask)
    visited = falses(height, width)
    largest_component = falses(height, width)
    largest_size = 0

    for y_index in 1:height
        for x_index in 1:width
            if !mask[y_index, x_index] || visited[y_index, x_index]
                continue
            end

            component_cells = flood_component(mask, visited, x_index, y_index)

            if length(component_cells) > largest_size
                largest_size = length(component_cells)
                largest_component .= false

                for (cell_x, cell_y) in component_cells
                    largest_component[cell_y, cell_x] = true
                end
            end
        end
    end

    return largest_component
end

function flood_component(mask::BitMatrix, visited::BitMatrix, start_x::Int, start_y::Int)
    height, width = size(mask)
    queue = Tuple{Int,Int}[(start_x, start_y)]
    cells = Tuple{Int,Int}[]
    visited[start_y, start_x] = true
    cursor = 1

    while cursor <= length(queue)
        x_index, y_index = queue[cursor]
        cursor += 1
        push!(cells, (x_index, y_index))

        for (neighbor_x, neighbor_y) in neighboring_cells(x_index, y_index, width, height)
            if mask[neighbor_y, neighbor_x] && !visited[neighbor_y, neighbor_x]
                visited[neighbor_y, neighbor_x] = true
                push!(queue, (neighbor_x, neighbor_y))
            end
        end
    end

    return cells
end

function fill_internal_background(component_mask::BitMatrix)
    height, width = size(component_mask)
    exterior_background = falses(height, width)
    queue = Tuple{Int,Int}[]

    for x_index in 1:width
        enqueue_exterior_cell!(queue, exterior_background, component_mask, x_index, 1)
        enqueue_exterior_cell!(queue, exterior_background, component_mask, x_index, height)
    end

    for y_index in 1:height
        enqueue_exterior_cell!(queue, exterior_background, component_mask, 1, y_index)
        enqueue_exterior_cell!(queue, exterior_background, component_mask, width, y_index)
    end

    cursor = 1

    while cursor <= length(queue)
        x_index, y_index = queue[cursor]
        cursor += 1

        for (neighbor_x, neighbor_y) in neighboring_cells(x_index, y_index, width, height)
            enqueue_exterior_cell!(
                queue,
                exterior_background,
                component_mask,
                neighbor_x,
                neighbor_y,
            )
        end
    end

    return component_mask .| .!exterior_background
end

function enqueue_exterior_cell!(
    queue::Vector{Tuple{Int,Int}},
    exterior_background::BitMatrix,
    component_mask::BitMatrix,
    x_index::Int,
    y_index::Int,
)
    if component_mask[y_index, x_index] || exterior_background[y_index, x_index]
        return
    end

    exterior_background[y_index, x_index] = true
    push!(queue, (x_index, y_index))
end

function neighboring_cells(x_index::Int, y_index::Int, width::Int, height::Int)
    neighbors = Tuple{Int,Int}[]

    if x_index > 1
        push!(neighbors, (x_index - 1, y_index))
    end

    if x_index < width
        push!(neighbors, (x_index + 1, y_index))
    end

    if y_index > 1
        push!(neighbors, (x_index, y_index - 1))
    end

    if y_index < height
        push!(neighbors, (x_index, y_index + 1))
    end

    return neighbors
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
    free_cells = collect_free_cells(obstacle_grid, space.domain_mask)
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

            if !space.domain_mask[next_y + 1, next_x + 1] || obstacle_grid[next_y + 1, next_x + 1]
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
        obstacle_grid[obstacle.y + 1, obstacle.x + 1] = obstacle.preliminary_blocking
    end

    return obstacle_grid
end

function collect_free_cells(obstacle_grid::BitMatrix, domain_mask::BitMatrix)
    height, width = size(obstacle_grid)
    free_cells = Tuple{Int,Int}[]

    for y_index in 1:height
        for x_index in 1:width
            if domain_mask[y_index, x_index] && !obstacle_grid[y_index, x_index]
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

function mpc_box_lx(space::SimulationSpace, config::MpcModelConfig)
    return space.lx
end

function mpc_box_ly(space::SimulationSpace, config::MpcModelConfig)
    return space.ly
end

function write_mpc_config_json(
    path::AbstractString,
    run_config::SimulationRunConfig,
    image::PgmImage,
    space::SimulationSpace,
    timestamp::String;
    mpc_initialization::Union{Nothing,MpcParticleInitialization} = nothing,
)
    config = run_config.mpc_config
    fields = Any[
        ("created_at", timestamp),
        ("input_role", config.input_role),
        ("configuration_model", MPC_CONFIGURATION_MODEL),
        ("execution_engine", SIMULATION_ENGINE_PRELIMINARY),
        ("simulation_note", "MPC parameters configured; full MPC dynamics implemented in later issues."),
        ("input_width", image.width),
        ("input_height", image.height),
        ("input_max_gray", image.max_gray),
        ("lx", mpc_box_lx(space, config)),
        ("ly", mpc_box_ly(space, config)),
        ("lz", config.lz),
        ("cell_length", config.cell_length),
        ("n0", config.n0),
        ("mass", config.mass),
        ("kbt", config.kbt),
        ("tau", config.tau),
        ("rotation_angle", config.rotation_angle),
        ("rotation_policy", config.rotation_policy),
        ("realizations", config.realizations),
        ("labeled_particles", config.labeled_particles),
        ("output_times", config.output_times),
        ("grid_shift_enabled", config.grid_shift_enabled),
        ("grid_shift_decision", config.grid_shift_decision),
        ("seed", run_config.seed),
        ("steps", run_config.steps),
        ("preliminary_particle_density", run_config.particle_density),
        ("tissue_threshold", space.tissue_threshold),
        ("obstacle_threshold", space.obstacle_threshold),
        ("domain_cell_count", count_domain_cells(space)),
        ("obstacle_count", length(space.obstacles)),
        ("preliminary_blocking_obstacle_count", count_preliminary_blocking_obstacles(space)),
        ("radius_model", "cylindrical_obstacles_from_pgm_intensity"),
        ("radius_formula", "radius = 0.5 * cell_length * (1 - intensity / (max_gray + 1))"),
        ("radius_denominator", space.max_gray + 1),
    ]

    if mpc_initialization !== nothing
        append!(
            fields,
            [
                ("mpc_particle_model", "continuous_position_maxwellian_velocity"),
                ("mpc_particle_count", length(mpc_initialization.particles)),
                ("mpc_target_particle_count", mpc_initialization.target_particle_count),
                ("mpc_domain_volume", mpc_initialization.domain_volume),
                ("mpc_velocity_sigma", mpc_initialization.velocity_sigma),
                ("mpc_rejected_samples", mpc_initialization.rejected_samples),
            ],
        )
    end

    write_key_value_json(path, fields)
end

function write_key_value_json(path::AbstractString, fields)
    open(path, "w") do io
        println(io, "{")

        for (index, (key, value)) in enumerate(fields)
            suffix = index == length(fields) ? "" : ","
            println(io, "  \"$(key)\": $(json_value(value))$(suffix)")
        end

        println(io, "}")
    end
end

function write_space_summary(
    path::AbstractString,
    space::SimulationSpace;
    mpc_config::MpcModelConfig = MpcModelConfig(),
)
    cell_count = space.width * space.height
    domain_cell_count = count_domain_cells(space)
    excluded_background_count = count_excluded_background_cells(space)
    obstacle_count = length(space.obstacles)
    preliminary_blocking_obstacle_count = count_preliminary_blocking_obstacles(space)
    obstacle_fraction = safe_ratio(obstacle_count, domain_cell_count)
    preliminary_blocking_fraction = safe_ratio(preliminary_blocking_obstacle_count, domain_cell_count)
    domain_fraction = safe_ratio(domain_cell_count, cell_count)

    open(path, "w") do io
        println(io, "width=$(space.width)")
        println(io, "height=$(space.height)")
        println(io, "input_role=$(mpc_config.input_role)")
        println(io, "configuration_model=$(MPC_CONFIGURATION_MODEL)")
        println(io, "execution_engine=$(SIMULATION_ENGINE_PRELIMINARY)")
        println(io, "cell_length=$(mpc_config.cell_length)")
        println(io, "lx=$(mpc_box_lx(space, mpc_config))")
        println(io, "ly=$(mpc_box_ly(space, mpc_config))")
        println(io, "lz=$(mpc_config.lz)")
        println(io, "max_gray=$(space.max_gray)")
        println(io, "cell_count=$(cell_count)")
        println(io, "tissue_threshold=$(space.tissue_threshold)")
        println(io, "domain_cell_count=$(domain_cell_count)")
        println(io, "excluded_background_count=$(excluded_background_count)")
        println(io, "domain_fraction=$(domain_fraction)")
        println(io, "obstacle_threshold=$(space.obstacle_threshold)")
        println(io, "obstacle_count=$(obstacle_count)")
        println(io, "cylinder_obstacle_count=$(obstacle_count)")
        println(io, "preliminary_blocking_obstacle_count=$(preliminary_blocking_obstacle_count)")
        println(io, "obstacle_fraction=$(obstacle_fraction)")
        println(io, "preliminary_blocking_fraction=$(preliminary_blocking_fraction)")
        println(io, "normalized_min=$(minimum(space.normalized_intensities))")
        println(io, "normalized_max=$(maximum(space.normalized_intensities))")
        println(io, "radius_model=cylindrical_obstacles_from_pgm_intensity")
        println(io, "radius_formula=0.5 * cell_length * (1 - intensity / (max_gray + 1))")
        println(io, "radius_denominator=$(space.max_gray + 1)")
        println(io, "cylinder_height=$(space.lz)")

        if isempty(space.obstacles)
            println(io, "radius_min=")
            println(io, "radius_max=")
            println(io, "radius_mean=")
        else
            radii = [obstacle.radius for obstacle in space.obstacles]
            println(io, "radius_min=$(minimum(radii))")
            println(io, "radius_max=$(maximum(radii))")
            println(io, "radius_mean=$(sum(radii) / length(radii))")
            for (label, count_value) in radius_histogram(space.obstacles)
                println(io, "radius_bucket_$(label)=$(count_value)")
            end
        end
    end
end

function write_obstacles_tsv(path::AbstractString, obstacles::Vector{SimulationObstacle})
    open(path, "w") do io
        println(io, "x\ty\tcenter_x\tcenter_y\tcenter_z\tintensity\tnormalized_intensity\tradius\theight\tpreliminary_blocking")

        for obstacle in obstacles
            println(
                io,
                "$(obstacle.x)\t$(obstacle.y)\t$(obstacle.center_x)\t$(obstacle.center_y)\t$(obstacle.center_z)\t$(obstacle.intensity)\t$(obstacle.normalized_intensity)\t$(obstacle.radius)\t$(obstacle.height)\t$(obstacle.preliminary_blocking)",
            )
        end
    end
end

function write_obstacle_radius_matrix_tsv(path::AbstractString, space::SimulationSpace)
    radius_grid = obstacle_radius_grid(space)
    blocking_grid = preliminary_blocking_grid(space)

    open(path, "w") do io
        println(io, "x\ty\tintensity\tnormalized_intensity\tradius\tis_domain\tpreliminary_blocking")

        for y_index in 1:space.height
            for x_index in 1:space.width
                intensity = space.normalized_intensities[y_index, x_index] * space.max_gray
                println(
                    io,
                    "$(x_index - 1)\t$(y_index - 1)\t$(round(Int, intensity))\t$(space.normalized_intensities[y_index, x_index])\t$(radius_grid[y_index, x_index])\t$(space.domain_mask[y_index, x_index])\t$(blocking_grid[y_index, x_index])",
                )
            end
        end
    end
end

function write_obstacle_radius_map_pgm(path::AbstractString, space::SimulationSpace)
    radius_values = build_obstacle_radius_map_values(space)
    height, width = size(radius_values)

    open(path, "w") do io
        println(io, "P2")
        println(io, "# Mapa de radios de obstaculos cilindricos generado por MammographySimulation")
        println(io, "$(width) $(height)")
        println(io, "255")

        for y_index in 1:height
            println(io, join(vec(radius_values[y_index, :]), " "))
        end
    end
end

function write_obstacle_radius_histogram_tsv(path::AbstractString, space::SimulationSpace)
    open(path, "w") do io
        println(io, "bucket\tcount")

        for (label, count_value) in radius_histogram(space.obstacles)
            println(io, "$(label)\t$(count_value)")
        end
    end
end

function write_mpc_initial_particles_tsv(
    path::AbstractString,
    initialization::MpcParticleInitialization,
)
    open(path, "w") do io
        println(io, "# seed=$(initialization.seed)")
        println(io, "# target_particle_count=$(initialization.target_particle_count)")
        println(io, "# domain_volume=$(initialization.domain_volume)")
        println(io, "# velocity_sigma=$(initialization.velocity_sigma)")
        println(io, "# rejected_samples=$(initialization.rejected_samples)")
        println(io, "id\tx\ty\tz\tvx\tvy\tvz\tmass\tspecies\tlabeled")

        for particle in initialization.particles
            println(
                io,
                "$(particle.id)\t$(particle.x)\t$(particle.y)\t$(particle.z)\t$(particle.vx)\t$(particle.vy)\t$(particle.vz)\t$(particle.mass)\t$(particle.species)\t$(particle.labeled)",
            )
        end
    end
end

function write_simulation_summary(
    path::AbstractString,
    result::SimulationResult,
    space::SimulationSpace;
    mpc_initialization::Union{Nothing,MpcParticleInitialization} = nothing,
)
    free_cell_count = count_free_cells(space)

    open(path, "w") do io
        println(io, "steps=$(result.steps)")
        println(io, "seed=$(result.seed)")
        println(io, "particle_density=$(result.particle_density)")
        println(io, "particle_count=$(length(result.particles))")
        println(io, "cylinder_obstacle_count=$(length(space.obstacles))")
        println(io, "preliminary_blocking_obstacle_count=$(count_preliminary_blocking_obstacles(space))")
        if mpc_initialization !== nothing
            println(io, "mpc_particle_model=continuous_position_maxwellian_velocity")
            println(io, "mpc_particle_count=$(length(mpc_initialization.particles))")
            println(io, "mpc_target_particle_count=$(mpc_initialization.target_particle_count)")
            println(io, "mpc_domain_volume=$(mpc_initialization.domain_volume)")
            println(io, "mpc_velocity_sigma=$(mpc_initialization.velocity_sigma)")
            println(io, "mpc_rejected_samples=$(mpc_initialization.rejected_samples)")
        end
        println(io, "free_cell_count=$(free_cell_count)")
        println(io, "attempted_moves=$(result.attempted_moves)")
        println(io, "collision_count=$(result.collision_count)")
        println(io, "visited_cell_count=$(count(>(0), result.visit_counts))")
        println(io, "visit_count_total=$(sum(result.visit_counts))")
        println(io, "configuration_model=$(MPC_CONFIGURATION_MODEL)")
        println(io, "execution_engine=$(SIMULATION_ENGINE_PRELIMINARY)")
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

function count_domain_cells(space::SimulationSpace)
    return count(space.domain_mask)
end

function count_excluded_background_cells(space::SimulationSpace)
    return space.width * space.height - count_domain_cells(space)
end

function count_free_cells(space::SimulationSpace)
    obstacle_grid = build_obstacle_grid(space)
    free_cell_count = 0

    for y_index in axes(space.domain_mask, 1)
        for x_index in axes(space.domain_mask, 2)
            if space.domain_mask[y_index, x_index] && !obstacle_grid[y_index, x_index]
                free_cell_count += 1
            end
        end
    end

    return free_cell_count
end

function count_preliminary_blocking_obstacles(space::SimulationSpace)
    return count(obstacle -> obstacle.preliminary_blocking, space.obstacles)
end

function obstacle_radius_grid(space::SimulationSpace)
    radius_grid = zeros(Float64, space.height, space.width)

    for obstacle in space.obstacles
        radius_grid[obstacle.y + 1, obstacle.x + 1] = obstacle.radius
    end

    return radius_grid
end

function preliminary_blocking_grid(space::SimulationSpace)
    return build_obstacle_grid(space)
end

function is_preliminary_blocking_cell(space::SimulationSpace, x_index::Int, y_index::Int)
    if !space.domain_mask[y_index, x_index]
        return false
    end

    return preliminary_blocking_grid(space)[y_index, x_index]
end

function build_obstacle_radius_map_values(space::SimulationSpace)
    radius_grid = obstacle_radius_grid(space)
    max_radius = maximum(radius_grid)
    radius_values = zeros(Int, size(radius_grid))

    if max_radius == 0
        return radius_values
    end

    for index in eachindex(radius_grid)
        radius_values[index] = round(Int, radius_grid[index] / max_radius * 255)
    end

    return radius_values
end

function radius_histogram(obstacles::Vector{SimulationObstacle})
    buckets = [
        ("0_00_0_10", 0.0, 0.10),
        ("0_10_0_20", 0.10, 0.20),
        ("0_20_0_30", 0.20, 0.30),
        ("0_30_0_40", 0.30, 0.40),
        ("0_40_0_50", 0.40, Inf),
    ]

    return [
        (
            label,
            count(obstacle -> lower <= obstacle.radius < upper, obstacles),
        )
        for (label, lower, upper) in buckets
    ]
end

function generate_preliminary_results(
    output_dir::AbstractString,
    result::SimulationResult,
    space::SimulationSpace,
)
    mkpath(output_dir)

    metrics = build_preliminary_metrics(result, space)
    metrics_path = joinpath(output_dir, "metrics.json")
    domain_mask_path = joinpath(output_dir, "domain_mask.pgm")
    density_map_path = joinpath(output_dir, "density_map.pgm")
    density_matrix_path = joinpath(output_dir, "density_matrix.tsv")

    write_metrics_json(metrics_path, metrics)
    write_domain_mask_pgm(domain_mask_path, space.domain_mask)
    write_density_map_pgm(density_map_path, result.visit_counts)
    write_density_matrix_tsv(density_matrix_path, result.visit_counts, space)

    return PreliminarySimulationResults(
        metrics_path,
        domain_mask_path,
        density_map_path,
        density_matrix_path,
        metrics,
    )
end

function build_preliminary_metrics(result::SimulationResult, space::SimulationSpace)
    cell_count = space.width * space.height
    domain_cell_count = count_domain_cells(space)
    excluded_background_count = count_excluded_background_cells(space)
    obstacle_count = length(space.obstacles)
    preliminary_blocking_obstacle_count = count_preliminary_blocking_obstacles(space)
    free_cell_count = count_free_cells(space)
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
        domain_cell_count,
        excluded_background_count,
        obstacle_count,
        preliminary_blocking_obstacle_count,
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
        safe_ratio(visit_count_total, domain_cell_count),
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
        ("domain_cell_count", metrics.domain_cell_count),
        ("excluded_background_count", metrics.excluded_background_count),
        ("obstacle_count", metrics.obstacle_count),
        ("preliminary_blocking_obstacle_count", metrics.preliminary_blocking_obstacle_count),
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

function write_domain_mask_pgm(path::AbstractString, domain_mask::BitMatrix)
    height, width = size(domain_mask)

    open(path, "w") do io
        println(io, "P2")
        println(io, "# Mascara del dominio mamario detectado por MammographySimulation")
        println(io, "$(width) $(height)")
        println(io, "255")

        for y_index in 1:height
            row = [domain_mask[y_index, x_index] ? 255 : 0 for x_index in 1:width]
            println(io, join(row, " "))
        end
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
        println(io, "x\ty\tvisits\tdensity_value\tis_domain\tis_obstacle")

        for y_index in axes(visit_counts, 1)
            for x_index in axes(visit_counts, 2)
                println(
                    io,
                    "$(x_index - 1)\t$(y_index - 1)\t$(visit_counts[y_index, x_index])\t$(density_values[y_index, x_index])\t$(space.domain_mask[y_index, x_index])\t$(obstacle_grid[y_index, x_index])",
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

function json_value(value::AbstractVector{<:Integer})
    return "[" * join(string.(value), ", ") * "]"
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
