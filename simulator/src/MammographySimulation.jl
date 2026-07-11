module MammographySimulation

using Dates
using Random

export PgmImage,
    MpcModelConfig,
    MpcCollisionResult,
    MpcConcentrationResult,
    MpcConcentrationSnapshot,
    MpcComparableDiffusionMetrics,
    MpcParticle,
    MpcParticleInitialization,
    MpcStreamingResult,
    MpcVelocityAutocorrelationResult,
    SimulationObstacle,
    SimulationParticle,
    SyntheticValidationCase,
    SyntheticValidationResult,
    PreliminarySimulationMetrics,
    PreliminarySimulationResults,
    SimulationResult,
    SimulationSpace,
    SimulationRunConfig,
    read_pgm,
    build_simulation_space,
    build_mpc_concentration_grid,
    build_synthetic_validation_case,
    calculate_mpc_velocity_autocorrelation,
    calculate_mdc_star,
    calculate_theoretical_mdc0,
    calculate_velocity_autocorrelation,
    collide_mpc_particles,
    generate_mpc_concentration_maps,
    generate_synthetic_validation_cases,
    initialize_mpc_particles,
    stream_mpc_particles,
    synthetic_validation_case_names,
    validate_synthetic_cases,
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

mutable struct MpcParticle
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

struct MpcStreamingResult
    steps::Int
    tau::Float64
    particle_count::Int
    obstacle_collision_count::Int
    domain_boundary_collision_count::Int
    boundary_crossing_count_x::Int
    boundary_crossing_count_y::Int
    completed_intervals::Int
    particles::Vector{MpcParticle}
end

struct MpcCollisionResult
    seed::Int
    rotation_angle::Float64
    active_cell_count::Int
    collision_cell_count::Int
    singleton_cell_count::Int
    particle_count::Int
    max_particles_per_cell::Int
    particles::Vector{MpcParticle}
    cell_statistics::Vector{NamedTuple}
end

struct MpcConcentrationSnapshot
    time::Int
    density_grid::Matrix{Float64}
    high_concentration_mask::BitMatrix
    particle_count::Float64
    max_concentration::Float64
    high_concentration_cell_count::Int
end

struct MpcConcentrationResult
    requested_output_times::Vector{Int}
    captured_output_times::Vector{Int}
    realization_count::Int
    realization_seeds::Vector{Int}
    expected_density::Float64
    high_concentration_threshold::Float64
    particle_count::Float64
    snapshots::Vector{MpcConcentrationSnapshot}
    representative_realization_index::Int
    representative_seed::Int
    representative_snapshots::Vector{MpcConcentrationSnapshot}
end

struct MpcVelocityAutocorrelationResult
    steps::Int
    trajectory_steps::Int
    tau::Float64
    dimension::Int
    realization_count::Int
    requested_labeled_particles::Int
    labeled_particle_count::Int
    requested_initial_time_count::Int
    initial_times::Vector{Int}
    realization_seeds::Vector{Int}
    cv_values::Vector{Float64}
    normalized_cv_values::Vector{Float64}
    sample_counts::Vector{Int}
    mdc::Float64
    characteristic_time::Union{Nothing,Float64}
    realization_mdc_values::Vector{Float64}
    realization_cv0_values::Vector{Float64}
    realization_cv_final_values::Vector{Float64}
    realization_sample_counts::Vector{Int}
end

struct MpcComparableDiffusionMetrics
    metric_model::String
    reference_origin::String
    purpose_note::String
    units::String
    mdc::Float64
    mdc0::Float64
    mdc_star::Float64
    mdc_standard_deviation::Float64
    mdc_standard_error::Float64
    realization_mdc_values::Vector{Float64}
    realization_mdc_star_values::Vector{Float64}
    mdc_star_standard_deviation::Float64
    mdc_star_standard_error::Float64
    n0::Float64
    mass::Float64
    kbt::Float64
    tau::Float64
    realizations::Int
    labeled_particle_count::Int
    initial_time_count::Int
    characteristic_time::Union{Nothing,Float64}
end

struct SyntheticValidationCase
    name::String
    description::String
    image::PgmImage
    expected_domain_cell_count::Int
    expected_preliminary_blocking_obstacle_count::Int
    expected_notes::String
end

struct SyntheticValidationResult
    case_name::String
    status::String
    input_path::String
    output_dir::String
    expected_domain_cell_count::Int
    actual_domain_cell_count::Int
    expected_preliminary_blocking_obstacle_count::Int
    actual_preliminary_blocking_obstacle_count::Int
    mpc_particle_count::Int
    concentration_particle_sum::Int
    particle_conservation_ok::Bool
    mdc::Float64
    mdc0::Float64
    mdc_star::Float64
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
const DOMAIN_MASK_MODEL = "largest_connected_tissue_component_with_internal_hole_fill"
const SIMULATION_ENGINE_PRELIMINARY = "sequential_minimal_random_walk"
const SIMULATION_ENGINE_MPC = "multiparticle_collision_dynamics"
const MPC_CONFIGURATION_MODEL = "mpc_base_configuration"
const DEFAULT_SIMULATION_STEPS = 100
const DEFAULT_MPC_INPUT_ROLE = "confirmed_roi_pgm"
const DEFAULT_MPC_CELL_LENGTH = 1.0
const DEFAULT_MPC_LZ = 1
const DEFAULT_MPC_N0 = 10.0
const DEFAULT_MPC_MASS = 1.0
const DEFAULT_MPC_KBT = 1.0
const DEFAULT_MPC_TAU = 1.0
const DEFAULT_MPC_ROTATION_ANGLE = pi / 2
const DEFAULT_MPC_ROTATION_POLICY = "random_axis_xyz_and_random_sign_plus_minus_angle"
const DEFAULT_MPC_REALIZATIONS = 3
const DEFAULT_MPC_LABELED_PARTICLES = 500
const DEFAULT_MPC_CORRELATION_INITIAL_TIMES = 50
const DEFAULT_MPC_OUTPUT_TIMES = (0, 100)
const DEFAULT_MPC_GRID_SHIFT_ENABLED = false
const DEFAULT_MPC_GRID_SHIFT_DECISION = "disabled_initially_to_match_article_conditions"
const SIMULATION_BOX_VISUALIZATION_FILENAME = "simulation_box_3d.png"
const SIMULATION_BOX_VISUALIZATION_MODEL = "reproducible_cell_section_with_cylinders_particles_and_directions"
const SIMULATION_BOX_VISUALIZATION_MAX_COLUMNS = 12
const SIMULATION_BOX_VISUALIZATION_MAX_ROWS = 8
const SIMULATION_BOX_VISUALIZATION_MAX_CYLINDERS = 96
const SIMULATION_BOX_VISUALIZATION_MAX_PARTICLES = 80
const SIMULATION_BOX_VISUALIZATION_MAX_DIRECTIONS = 40
const DEFAULT_SYNTHETIC_VALIDATION_CASES = (
    "free_field",
    "central_obstacle",
    "intensity_pattern",
    "clear_dark_channel",
    "synthetic_roi",
)

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
    correlation_initial_times::Int = DEFAULT_MPC_CORRELATION_INITIAL_TIMES
    output_times::Vector{Int} = collect(DEFAULT_MPC_OUTPUT_TIMES)
    grid_shift_enabled::Bool = DEFAULT_MPC_GRID_SHIFT_ENABLED
    grid_shift_decision::String = DEFAULT_MPC_GRID_SHIFT_DECISION
end

Base.@kwdef struct SimulationRunConfig
    input_path::String
    output_dir::String
    seed::Int = 1234
    steps::Int = DEFAULT_SIMULATION_STEPS
    mpc_config::MpcModelConfig = MpcModelConfig()
end

const USAGE = """
Uso:
  julia --project=simulator simulator/scripts/run_case.jl --input <roi_confirmada.pgm> --output <directorio> [opciones]

Opciones:
  --input              Ruta de la ROI confirmada convertida a PGM.
  --output             Directorio donde se escribiran los resultados.
  --seed               Semilla reproducible. Por defecto: 1234.
  --steps              Horizonte de correlacion y pasos de salida. Por defecto: 100.
  --n0                 Densidad media MPC de particulas por celda. Por defecto: 10.
  --mass               Masa reducida de particula MPC. Por defecto: 1.
  --kbt                Temperatura reducida kBT. Por defecto: 1.
  --tau                Paso temporal reducido. Por defecto: 1.
  --rotation-angle     Angulo de rotacion MPC en radianes. Por defecto: pi/2.
  --realizations       Numero de realizaciones estadisticas. Por defecto: 3.
  --labeled-particles  Particulas etiquetadas para autocorrelacion. Por defecto: 500.
  --correlation-initial-times  Numero de tiempos iniciales para Cv(t). Por defecto: 50.
  --output-times       Tiempos de salida separados por coma. Por defecto: 0,100.
  --grid-shift         true/false. Por defecto: false.
  --help               Muestra esta ayuda.
"""

const VALUE_OPTIONS = Set([
    "--input",
    "--output",
    "--seed",
    "--steps",
    "--n0",
    "--mass",
    "--kbt",
    "--tau",
    "--rotation-angle",
    "--realizations",
    "--labeled-particles",
    "--correlation-initial-times",
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
    steps = parse_integer_option(get(options, "--steps", string(DEFAULT_SIMULATION_STEPS)), "--steps")
    mpc_config = parse_mpc_config(options)

    if steps < 0
        throw(ArgumentError("La opcion --steps no puede ser negativa."))
    end

    return SimulationRunConfig(
        input_path = input_path,
        output_dir = output_dir,
        seed = seed,
        steps = steps,
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
    mpc_streaming = stream_mpc_particles(
        mpc_initialization,
        simulation_space,
        config.mpc_config;
        steps = config.steps,
    )
    mpc_collision = collide_mpc_particles(
        mpc_streaming,
        simulation_space,
        config.mpc_config;
        seed = config.seed,
    )
    mpc_concentration = generate_mpc_concentration_maps(
        mpc_initialization,
        simulation_space,
        config.mpc_config;
        steps = config.steps,
        seed = config.seed,
    )
    mpc_velocity_autocorrelation = calculate_mpc_velocity_autocorrelation(
        simulation_space,
        config.mpc_config;
        steps = config.steps,
        seed = config.seed,
    )
    mpc_diffusion_metrics = build_comparable_diffusion_metrics(
        mpc_velocity_autocorrelation,
        config.mpc_config,
    )
    mkpath(output_dir)
    for legacy_filename in (
        "metrics.json",
        "density_map.pgm",
        "density_matrix.tsv",
        "simulation_state.tsv",
        "visit_counts.tsv",
        "mpc_concentration_initial.pgm",
        "mpc_concentration_final.pgm",
        "mpc_high_concentration_initial.pgm",
        "mpc_high_concentration_final.pgm",
    )
        rm(joinpath(output_dir, legacy_filename); force = true)
    end

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
    simulation_box_visualization_path = joinpath(output_dir, SIMULATION_BOX_VISUALIZATION_FILENAME)
    simulation_box_visualization_metadata_path = joinpath(
        output_dir,
        "simulation_box_visualization.txt",
    )
    mpc_initial_particles_path = joinpath(output_dir, "mpc_initial_particles.tsv")
    mpc_streamed_particles_path = joinpath(output_dir, "mpc_streamed_particles.tsv")
    mpc_streaming_summary_path = joinpath(output_dir, "mpc_streaming_summary.txt")
    mpc_collided_particles_path = joinpath(output_dir, "mpc_collided_particles.tsv")
    mpc_collision_summary_path = joinpath(output_dir, "mpc_collision_summary.txt")
    mpc_cell_collisions_path = joinpath(output_dir, "mpc_cell_collisions.tsv")
    simulation_summary_path = joinpath(output_dir, "simulation_summary.txt")
    domain_mask_path = joinpath(output_dir, "domain_mask.pgm")

    open(log_path, "w") do io
        println(io, "MammographySimulation")
        println(io, "status=mpc_results_ready")
        println(io, "created_at=$(timestamp)")
        println(io, "input_path=$(input_path)")
        println(io, "output_dir=$(output_dir)")
        println(io, "input_role=$(config.mpc_config.input_role)")
        println(io, "configuration_model=$(MPC_CONFIGURATION_MODEL)")
        println(io, "execution_engine=$(SIMULATION_ENGINE_MPC)")
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
        println(io, "n0=$(config.mpc_config.n0)")
        println(io, "mass=$(config.mpc_config.mass)")
        println(io, "kbt=$(config.mpc_config.kbt)")
        println(io, "tau=$(config.mpc_config.tau)")
        println(io, "rotation_angle=$(config.mpc_config.rotation_angle)")
        println(io, "rotation_policy=$(config.mpc_config.rotation_policy)")
        println(io, "realizations=$(config.mpc_config.realizations)")
        println(io, "labeled_particles=$(config.mpc_config.labeled_particles)")
        println(io, "correlation_initial_times=$(config.mpc_config.correlation_initial_times)")
        println(io, "output_times=$(join(config.mpc_config.output_times, ","))")
        println(io, "grid_shift_enabled=$(config.mpc_config.grid_shift_enabled)")
        println(io, "grid_shift_decision=$(config.mpc_config.grid_shift_decision)")
        println(io, "mpc_particle_count=$(length(mpc_initialization.particles))")
        println(io, "mpc_domain_volume=$(mpc_initialization.domain_volume)")
        println(io, "mpc_velocity_sigma=$(mpc_initialization.velocity_sigma)")
        println(io, "mpc_rejected_samples=$(mpc_initialization.rejected_samples)")
        println(io, "simulation_box_visualization_model=$(SIMULATION_BOX_VISUALIZATION_MODEL)")
        println(io, "simulation_box_visualization_file=$(SIMULATION_BOX_VISUALIZATION_FILENAME)")
        println(io, "mpc_streaming_obstacle_collision_count=$(mpc_streaming.obstacle_collision_count)")
        println(io, "mpc_streaming_domain_boundary_collision_count=$(mpc_streaming.domain_boundary_collision_count)")
        println(io, "mpc_streaming_boundary_crossing_count_x=$(mpc_streaming.boundary_crossing_count_x)")
        println(io, "mpc_streaming_boundary_crossing_count_y=$(mpc_streaming.boundary_crossing_count_y)")
        println(io, "mpc_collision_active_cell_count=$(mpc_collision.active_cell_count)")
        println(io, "mpc_collision_cell_count=$(mpc_collision.collision_cell_count)")
        println(io, "mpc_collision_particle_count=$(mpc_collision.particle_count)")
        println(io, "mpc_concentration_model=particles_per_cell_snapshot")
        println(io, "mpc_concentration_aggregation=mean_across_realizations")
        println(io, "mpc_concentration_realizations=$(mpc_concentration.realization_count)")
        println(io, "mpc_concentration_realization_seeds=$(join(mpc_concentration.realization_seeds, ","))")
        println(io, "mpc_concentration_requested_output_times=$(join(mpc_concentration.requested_output_times, ","))")
        println(io, "mpc_concentration_captured_output_times=$(join(mpc_concentration.captured_output_times, ","))")
        println(io, "mpc_concentration_expected_density_n0=$(mpc_concentration.expected_density)")
        println(io, "mpc_concentration_high_threshold=$(mpc_concentration.high_concentration_threshold)")
        println(io, "mpc_concentration_snapshot_count=$(length(mpc_concentration.snapshots))")
        println(io, "mpc_concentration_representative_realization_index=$(mpc_concentration.representative_realization_index)")
        println(io, "mpc_concentration_representative_seed=$(mpc_concentration.representative_seed)")
        println(io, "velocity_autocorrelation_model=green_kubo_xy")
        println(io, "velocity_autocorrelation_dimension=$(mpc_velocity_autocorrelation.dimension)")
        println(io, "velocity_autocorrelation_requested_labeled_particles=$(mpc_velocity_autocorrelation.requested_labeled_particles)")
        println(io, "velocity_autocorrelation_labeled_particle_count=$(mpc_velocity_autocorrelation.labeled_particle_count)")
        println(io, "velocity_autocorrelation_requested_initial_time_count=$(mpc_velocity_autocorrelation.requested_initial_time_count)")
        println(io, "velocity_autocorrelation_initial_times=$(join(mpc_velocity_autocorrelation.initial_times, ","))")
        println(io, "velocity_autocorrelation_mdc=$(mpc_velocity_autocorrelation.mdc)")
        println(io, "diffusion_metric_model=$(mpc_diffusion_metrics.metric_model)")
        println(io, "diffusion_metric_mdc=$(mpc_diffusion_metrics.mdc)")
        println(io, "diffusion_metric_mdc0=$(mpc_diffusion_metrics.mdc0)")
        println(io, "diffusion_metric_mdc_star=$(mpc_diffusion_metrics.mdc_star)")
        println(io, "diffusion_metric_mdc_standard_deviation=$(mpc_diffusion_metrics.mdc_standard_deviation)")
        println(io, "diffusion_metric_units=$(mpc_diffusion_metrics.units)")
        println(io, "diffusion_metric_reference_origin=$(mpc_diffusion_metrics.reference_origin)")
        println(io, "message=Simulacion MPC ejecutada y mapas generados desde posiciones de particulas.")
    end

    open(config_path, "w") do io
        println(io, "input_path=$(input_path)")
        println(io, "output_dir=$(output_dir)")
        println(io, "input_role=$(config.mpc_config.input_role)")
        println(io, "configuration_model=$(MPC_CONFIGURATION_MODEL)")
        println(io, "execution_engine=$(SIMULATION_ENGINE_MPC)")
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
        println(io, "n0=$(config.mpc_config.n0)")
        println(io, "mass=$(config.mpc_config.mass)")
        println(io, "kbt=$(config.mpc_config.kbt)")
        println(io, "tau=$(config.mpc_config.tau)")
        println(io, "rotation_angle=$(config.mpc_config.rotation_angle)")
        println(io, "rotation_policy=$(config.mpc_config.rotation_policy)")
        println(io, "realizations=$(config.mpc_config.realizations)")
        println(io, "labeled_particles=$(config.mpc_config.labeled_particles)")
        println(io, "correlation_initial_times=$(config.mpc_config.correlation_initial_times)")
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
        mpc_streaming = mpc_streaming,
        mpc_collision = mpc_collision,
        mpc_concentration = mpc_concentration,
        mpc_velocity_autocorrelation = mpc_velocity_autocorrelation,
        mpc_diffusion_metrics = mpc_diffusion_metrics,
        simulation_box_visualization_path = simulation_box_visualization_path,
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
    write_domain_mask_pgm(domain_mask_path, simulation_space.domain_mask)
    write_obstacles_tsv(obstacles_path, simulation_space.obstacles)
    write_obstacle_radius_matrix_tsv(obstacle_radius_matrix_path, simulation_space)
    write_obstacle_radius_map_pgm(obstacle_radius_map_path, simulation_space)
    write_obstacle_radius_histogram_tsv(obstacle_radius_histogram_path, simulation_space)
    write_simulation_box_visualization_png(
        simulation_box_visualization_path,
        simulation_space,
        mpc_initialization,
        metadata_path = simulation_box_visualization_metadata_path,
    )
    write_mpc_initial_particles_tsv(mpc_initial_particles_path, mpc_initialization)
    write_mpc_streamed_particles_tsv(mpc_streamed_particles_path, mpc_streaming)
    write_mpc_streaming_summary(mpc_streaming_summary_path, mpc_streaming)
    write_mpc_collided_particles_tsv(mpc_collided_particles_path, mpc_collision)
    write_mpc_collision_summary(mpc_collision_summary_path, mpc_collision)
    write_mpc_cell_collisions_tsv(mpc_cell_collisions_path, mpc_collision)
    mpc_concentration_outputs = write_mpc_concentration_outputs(
        output_dir,
        mpc_concentration,
        simulation_space,
    )
    velocity_autocorrelation_outputs = write_velocity_autocorrelation_outputs(
        output_dir,
        mpc_velocity_autocorrelation,
    )
    diffusion_metrics_outputs = write_comparable_diffusion_metrics_outputs(
        output_dir,
        mpc_diffusion_metrics,
    )
    write_simulation_summary(
        simulation_summary_path,
        config,
        simulation_space;
        mpc_initialization = mpc_initialization,
        mpc_streaming = mpc_streaming,
        mpc_collision = mpc_collision,
        mpc_concentration = mpc_concentration,
        mpc_velocity_autocorrelation = mpc_velocity_autocorrelation,
        mpc_diffusion_metrics = mpc_diffusion_metrics,
        simulation_box_visualization_path = simulation_box_visualization_path,
        simulation_box_visualization_metadata_path = simulation_box_visualization_metadata_path,
    )

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
        simulation_box_visualization_path = simulation_box_visualization_path,
        simulation_box_visualization_metadata_path = simulation_box_visualization_metadata_path,
        mpc_initial_particles_path = mpc_initial_particles_path,
        mpc_streamed_particles_path = mpc_streamed_particles_path,
        mpc_streaming_summary_path = mpc_streaming_summary_path,
        mpc_collided_particles_path = mpc_collided_particles_path,
        mpc_collision_summary_path = mpc_collision_summary_path,
        mpc_cell_collisions_path = mpc_cell_collisions_path,
        mpc_concentration_summary_path = mpc_concentration_outputs.summary_path,
        mpc_concentration_times_path = mpc_concentration_outputs.times_path,
        mpc_concentration_representative_initial_map_path = mpc_concentration_outputs.representative_initial_map_path,
        mpc_concentration_representative_final_map_path = mpc_concentration_outputs.representative_final_map_path,
        mpc_concentration_mean_initial_map_path = mpc_concentration_outputs.mean_initial_map_path,
        mpc_concentration_mean_final_map_path = mpc_concentration_outputs.mean_final_map_path,
        mpc_high_concentration_mean_initial_map_path = mpc_concentration_outputs.mean_initial_high_map_path,
        mpc_high_concentration_mean_final_map_path = mpc_concentration_outputs.mean_final_high_map_path,
        mpc_concentration_representative_time_map_paths = mpc_concentration_outputs.representative_time_map_paths,
        mpc_concentration_mean_time_map_paths = mpc_concentration_outputs.mean_time_map_paths,
        mpc_high_concentration_mean_time_map_paths = mpc_concentration_outputs.mean_time_high_map_paths,
        velocity_autocorrelation_path = velocity_autocorrelation_outputs.autocorrelation_path,
        velocity_autocorrelation_summary_path = velocity_autocorrelation_outputs.summary_path,
        velocity_autocorrelation_realizations_path = velocity_autocorrelation_outputs.realizations_path,
        diffusion_metrics_json_path = diffusion_metrics_outputs.json_path,
        diffusion_metrics_tsv_path = diffusion_metrics_outputs.tsv_path,
        diffusion_metrics_summary_path = diffusion_metrics_outputs.summary_path,
        simulation_summary_path = simulation_summary_path,
        domain_mask_path = domain_mask_path,
        image = pgm_image,
        space = simulation_space,
        mpc_initialization = mpc_initialization,
        mpc_streaming = mpc_streaming,
        mpc_collision = mpc_collision,
        mpc_concentration = mpc_concentration,
        mpc_velocity_autocorrelation = mpc_velocity_autocorrelation,
        mpc_diffusion_metrics = mpc_diffusion_metrics,
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
        println("Simulacion mesoscopica MPC ejecutada correctamente.")
        println("log_path=$(result.log_path)")
        println("config_path=$(result.config_path)")
        println("mpc_config_path=$(result.mpc_config_path)")
        println("summary_path=$(result.summary_path)")
        println("space_summary_path=$(result.space_summary_path)")
        println("obstacles_path=$(result.obstacles_path)")
        println("obstacle_radius_matrix_path=$(result.obstacle_radius_matrix_path)")
        println("obstacle_radius_map_path=$(result.obstacle_radius_map_path)")
        println("obstacle_radius_histogram_path=$(result.obstacle_radius_histogram_path)")
        println("simulation_box_visualization_path=$(result.simulation_box_visualization_path)")
        println("simulation_box_visualization_metadata_path=$(result.simulation_box_visualization_metadata_path)")
        println("mpc_initial_particles_path=$(result.mpc_initial_particles_path)")
        println("mpc_streamed_particles_path=$(result.mpc_streamed_particles_path)")
        println("mpc_streaming_summary_path=$(result.mpc_streaming_summary_path)")
        println("mpc_collided_particles_path=$(result.mpc_collided_particles_path)")
        println("mpc_collision_summary_path=$(result.mpc_collision_summary_path)")
        println("mpc_cell_collisions_path=$(result.mpc_cell_collisions_path)")
        println("mpc_concentration_summary_path=$(result.mpc_concentration_summary_path)")
        println("mpc_concentration_times_path=$(result.mpc_concentration_times_path)")
        println("mpc_concentration_representative_initial_map_path=$(result.mpc_concentration_representative_initial_map_path)")
        println("mpc_concentration_representative_final_map_path=$(result.mpc_concentration_representative_final_map_path)")
        println("mpc_concentration_mean_initial_map_path=$(result.mpc_concentration_mean_initial_map_path)")
        println("mpc_concentration_mean_final_map_path=$(result.mpc_concentration_mean_final_map_path)")
        println("mpc_high_concentration_mean_initial_map_path=$(result.mpc_high_concentration_mean_initial_map_path)")
        println("mpc_high_concentration_mean_final_map_path=$(result.mpc_high_concentration_mean_final_map_path)")
        println("velocity_autocorrelation_path=$(result.velocity_autocorrelation_path)")
        println("velocity_autocorrelation_summary_path=$(result.velocity_autocorrelation_summary_path)")
        println("velocity_autocorrelation_realizations_path=$(result.velocity_autocorrelation_realizations_path)")
        println("diffusion_metrics_json_path=$(result.diffusion_metrics_json_path)")
        println("diffusion_metrics_tsv_path=$(result.diffusion_metrics_tsv_path)")
        println("diffusion_metrics_summary_path=$(result.diffusion_metrics_summary_path)")
        println("simulation_summary_path=$(result.simulation_summary_path)")
        println("domain_mask_path=$(result.domain_mask_path)")
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
        correlation_initial_times = parse_integer_option(
            get(
                options,
                "--correlation-initial-times",
                string(DEFAULT_MPC_CORRELATION_INITIAL_TIMES),
            ),
            "--correlation-initial-times",
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

    if config.correlation_initial_times < 1
        throw(ArgumentError("Debe existir al menos un tiempo inicial para la autocorrelacion."))
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

function stream_mpc_particles(
    initialization::MpcParticleInitialization,
    space::SimulationSpace,
    config::MpcModelConfig;
    steps::Int = 1,
)
    if steps < 0
        throw(ArgumentError("El numero de pasos de streaming MPC no puede ser negativo."))
    end

    particles = copy_mpc_particles(initialization.particles)
    # Acumuladores atomicos: el loop de particulas se reparte entre varios threads y cada
    # uno suma sus colisiones de forma segura (sin condiciones de carrera).
    obstacle_collisions = Threads.Atomic{Int}(0)
    domain_boundary_collisions = Threads.Atomic{Int}(0)
    boundary_crossings_x = Threads.Atomic{Int}(0)
    boundary_crossings_y = Threads.Atomic{Int}(0)

    for _step in 1:steps
        # El loop de pasos es serial: cada paso depende de las posiciones del anterior.
        # Pero dentro de un paso cada particula avanza de forma independiente (solo muta su
        # propio estado y lee `space`, que es de solo lectura), asi que repartimos las
        # particulas entre los threads disponibles. La cantidad de threads la define el
        # arranque de Julia (--threads), configurable con SIMULATION_CPU_THREADS.
        Threads.@threads for index in eachindex(particles)
            collisions, domain_collisions, crossings_x, crossings_y = stream_single_mpc_particle!(
                particles[index],
                space,
                config.tau,
            )
            Threads.atomic_add!(obstacle_collisions, collisions)
            Threads.atomic_add!(domain_boundary_collisions, domain_collisions)
            Threads.atomic_add!(boundary_crossings_x, crossings_x)
            Threads.atomic_add!(boundary_crossings_y, crossings_y)
        end
    end

    obstacle_collision_count = obstacle_collisions[]
    domain_boundary_collision_count = domain_boundary_collisions[]
    boundary_crossing_count_x = boundary_crossings_x[]
    boundary_crossing_count_y = boundary_crossings_y[]

    return MpcStreamingResult(
        steps,
        config.tau,
        length(particles),
        obstacle_collision_count,
        domain_boundary_collision_count,
        boundary_crossing_count_x,
        boundary_crossing_count_y,
        steps,
        particles,
    )
end

function copy_mpc_particles(particles::Vector{MpcParticle})
    return [
        MpcParticle(
            particle.id,
            particle.x,
            particle.y,
            particle.z,
            particle.vx,
            particle.vy,
            particle.vz,
            particle.mass,
            particle.species,
            particle.labeled,
        )
        for particle in particles
    ]
end

function stream_single_mpc_particle!(
    particle::MpcParticle,
    space::SimulationSpace,
    tau::Float64,
)
    remaining_time = tau
    obstacle_collisions = 0
    domain_boundary_collisions = 0
    boundary_crossings_x = 0
    boundary_crossings_y = 0
    event_limit = 1000
    event_count = 0
    epsilon = 1.0e-9

    while remaining_time > epsilon
        event_count += 1

        if event_count > event_limit
            throw(ArgumentError("Se supero el limite de eventos durante el streaming MPC."))
        end

        boundary_time, boundary_axis = next_periodic_boundary_event(particle, space, remaining_time)
        collision_time, _obstacle = next_cylinder_collision_event(particle, space, remaining_time)

        if collision_time !== nothing && collision_time <= boundary_time + epsilon
            advance_mpc_particle!(particle, collision_time)
            apply_periodic_boundaries!(particle, space)
            particle.vx = -particle.vx
            particle.vy = -particle.vy
            particle.vz = -particle.vz
            obstacle_collisions += 1
            remaining_time -= collision_time
            domain_boundary_collisions += advance_mpc_particle_guarded!(
                particle,
                space,
                min(epsilon, remaining_time),
            )
            remaining_time -= min(epsilon, max(remaining_time, 0.0))
            continue
        end

        if boundary_axis !== nothing && boundary_time <= remaining_time + epsilon
            domain_boundary_collisions += advance_mpc_particle_guarded!(
                particle,
                space,
                boundary_time,
            )

            if boundary_axis == :x
                boundary_crossings_x += 1
            elseif boundary_axis == :y
                boundary_crossings_y += 1
            end

            remaining_time -= boundary_time
            continue
        end

        domain_boundary_collisions += advance_mpc_particle_guarded!(
            particle,
            space,
            remaining_time,
        )
        remaining_time = 0.0
    end

    return obstacle_collisions, domain_boundary_collisions, boundary_crossings_x, boundary_crossings_y
end

function advance_mpc_particle!(particle::MpcParticle, delta_time::Float64)
    particle.x += particle.vx * delta_time
    particle.y += particle.vy * delta_time
    particle.z += particle.vz * delta_time
end

function advance_mpc_particle_guarded!(
    particle::MpcParticle,
    space::SimulationSpace,
    delta_time::Float64,
)
    if delta_time <= 0
        return 0
    end

    max_displacement = max(abs(particle.vx * delta_time), abs(particle.vy * delta_time))
    substep_length = max(space.cell_length / 2, eps(Float64))
    substeps = max(1, ceil(Int, max_displacement / substep_length))
    sub_delta_time = delta_time / substeps
    domain_boundary_collisions = 0

    for _substep in 1:substeps
        previous_x = particle.x
        previous_y = particle.y
        previous_z = particle.z

        advance_mpc_particle!(particle, sub_delta_time)
        apply_periodic_boundaries!(particle, space)

        if particle_inside_excluded_background(particle, space)
            particle.x = previous_x
            particle.y = previous_y
            particle.z = previous_z
            particle.vx = -particle.vx
            particle.vy = -particle.vy
            domain_boundary_collisions += 1
            break
        end
    end

    return domain_boundary_collisions
end

function particle_inside_excluded_background(particle::MpcParticle, space::SimulationSpace)
    cell_x, cell_y = particle_cell_indices(particle, space)
    return !space.domain_mask[cell_y + 1, cell_x + 1]
end

function apply_periodic_boundaries!(particle::MpcParticle, space::SimulationSpace)
    particle.x = wrap_coordinate(particle.x, space.lx)
    particle.y = wrap_coordinate(particle.y, space.ly)

    if space.lz > 0
        particle.z = wrap_coordinate(particle.z, space.lz)
    end
end

function wrap_coordinate(value::Float64, length::Real)
    wrapped = mod(value, float(length))

    if isapprox(wrapped, float(length); atol = 1.0e-12)
        return 0.0
    end

    return wrapped
end

function next_periodic_boundary_event(
    particle::MpcParticle,
    space::SimulationSpace,
    max_time::Float64,
)
    epsilon = 1.0e-12
    best_time = max_time + 1
    best_axis = nothing

    x_time = time_to_periodic_boundary(particle.x, particle.vx, space.lx)
    y_time = time_to_periodic_boundary(particle.y, particle.vy, space.ly)

    if x_time !== nothing && epsilon < x_time <= max_time + epsilon && x_time < best_time
        best_time = x_time
        best_axis = :x
    end

    if y_time !== nothing && epsilon < y_time <= max_time + epsilon && y_time < best_time
        best_time = y_time
        best_axis = :y
    end

    if best_axis === nothing
        return Inf, nothing
    end

    return best_time, best_axis
end

function time_to_periodic_boundary(position::Float64, velocity::Float64, length::Real)
    if velocity > 0
        return (float(length) - position) / velocity
    elseif velocity < 0
        return position / -velocity
    end

    return nothing
end

function next_cylinder_collision_event(
    particle::MpcParticle,
    space::SimulationSpace,
    max_time::Float64,
)
    best_time = nothing
    best_obstacle = nothing
    epsilon = 1.0e-10

    for obstacle in space.obstacles
        if obstacle.radius <= 0
            continue
        end

        collision_time = ray_circle_collision_time(
            particle.x,
            particle.y,
            particle.vx,
            particle.vy,
            obstacle.center_x,
            obstacle.center_y,
            obstacle.radius,
        )

        if collision_time === nothing
            continue
        end

        if epsilon < collision_time <= max_time + epsilon &&
            (best_time === nothing || collision_time < best_time)
            best_time = collision_time
            best_obstacle = obstacle
        end
    end

    return best_time, best_obstacle
end

function ray_circle_collision_time(
    x::Float64,
    y::Float64,
    vx::Float64,
    vy::Float64,
    center_x::Float64,
    center_y::Float64,
    radius::Float64,
)
    a = vx^2 + vy^2

    if a == 0
        return nothing
    end

    dx = x - center_x
    dy = y - center_y
    b = 2 * (dx * vx + dy * vy)
    c = dx^2 + dy^2 - radius^2
    discriminant = b^2 - 4 * a * c

    if discriminant < 0
        return nothing
    end

    root = sqrt(discriminant)
    candidate_a = (-b - root) / (2 * a)
    candidate_b = (-b + root) / (2 * a)

    # Elige el menor tiempo positivo sin construir un arreglo. Esta funcion se ejecuta
    # miles de millones de veces durante el streaming, y la version anterior alocaba un
    # vector por llamada, saturando el recolector de basura. Equivale exactamente a
    # minimum(filter(c -> c > 0, (candidate_a, candidate_b))).
    best = nothing
    if candidate_a > 0
        best = candidate_a
    end
    if candidate_b > 0 && (best === nothing || candidate_b < best)
        best = candidate_b
    end

    return best
end

function collide_mpc_particles(
    streaming::MpcStreamingResult,
    space::SimulationSpace,
    config::MpcModelConfig;
    seed::Int = 1234,
)
    particles = copy_mpc_particles(streaming.particles)
    cell_groups = group_particle_indices_by_cell(particles, space)
    rng = Random.MersenneTwister(seed)
    cell_statistics = NamedTuple[]
    collision_cell_count = 0
    singleton_cell_count = 0
    max_particles_per_cell = 0

    for (cell, particle_indices) in sort(collect(cell_groups), by = item -> item[1])
        cell_x, cell_y = cell
        cell_particle_count = length(particle_indices)
        max_particles_per_cell = max(max_particles_per_cell, cell_particle_count)

        if cell_particle_count == 1
            singleton_cell_count += 1
        else
            collision_cell_count += 1
        end

        center_vx, center_vy, center_vz = center_of_mass_velocity(particles, particle_indices)
        signed_rotation_angle = cell_particle_count > 1 ? random_rotation_angle(rng, config) : 0.0
        rotation_axis = cell_particle_count > 1 ? random_rotation_axis(rng) : :none

        if cell_particle_count > 1
            rotate_relative_velocities!(
                particles,
                particle_indices,
                center_vx,
                center_vy,
                center_vz,
                signed_rotation_angle,
                rotation_axis,
            )
        end

        center_vx_after, center_vy_after, center_vz_after = center_of_mass_velocity(
            particles,
            particle_indices,
        )

        push!(
            cell_statistics,
            (
                cell_x = cell_x,
                cell_y = cell_y,
                particle_count = cell_particle_count,
                center_vx_before = center_vx,
                center_vy_before = center_vy,
                center_vz_before = center_vz,
                center_vx_after = center_vx_after,
                center_vy_after = center_vy_after,
                center_vz_after = center_vz_after,
                rotation_angle = signed_rotation_angle,
                rotation_axis = String(rotation_axis),
            ),
        )
    end

    return MpcCollisionResult(
        seed,
        config.rotation_angle,
        length(cell_groups),
        collision_cell_count,
        singleton_cell_count,
        length(particles),
        max_particles_per_cell,
        particles,
        cell_statistics,
    )
end

function group_particle_indices_by_cell(particles::Vector{MpcParticle}, space::SimulationSpace)
    groups = Dict{Tuple{Int,Int},Vector{Int}}()

    for (index, particle) in enumerate(particles)
        cell = particle_cell_indices(particle, space)

        if !haskey(groups, cell)
            groups[cell] = Int[]
        end

        push!(groups[cell], index)
    end

    return groups
end

function particle_cell_indices(particle::MpcParticle, space::SimulationSpace)
    cell_x = clamp(floor(Int, particle.x / space.cell_length), 0, space.width - 1)
    cell_y = clamp(floor(Int, particle.y / space.cell_length), 0, space.height - 1)

    return (cell_x, cell_y)
end

function center_of_mass_velocity(particles::Vector{MpcParticle}, particle_indices::Vector{Int})
    total_mass = sum(particles[index].mass for index in particle_indices)

    if total_mass == 0
        throw(ArgumentError("La masa total de una celda MPC no puede ser cero."))
    end

    center_vx = sum(particles[index].mass * particles[index].vx for index in particle_indices) / total_mass
    center_vy = sum(particles[index].mass * particles[index].vy for index in particle_indices) / total_mass
    center_vz = sum(particles[index].mass * particles[index].vz for index in particle_indices) / total_mass

    return center_vx, center_vy, center_vz
end

function random_rotation_angle(rng::Random.AbstractRNG, config::MpcModelConfig)
    return (rand(rng, Bool) ? 1.0 : -1.0) * config.rotation_angle
end

function random_rotation_axis(rng::Random.AbstractRNG)
    return rand(rng, (:x, :y, :z))
end

function rotate_relative_velocities!(
    particles::Vector{MpcParticle},
    particle_indices::Vector{Int},
    center_vx::Float64,
    center_vy::Float64,
    center_vz::Float64,
    signed_rotation_angle::Float64,
    rotation_axis::Symbol,
)
    cos_angle = cos(signed_rotation_angle)
    sin_angle = sin(signed_rotation_angle)

    for index in particle_indices
        particle = particles[index]
        relative_vx = particle.vx - center_vx
        relative_vy = particle.vy - center_vy
        relative_vz = particle.vz - center_vz

        rotated_vx, rotated_vy, rotated_vz = rotate_velocity_about_axis(
            relative_vx,
            relative_vy,
            relative_vz,
            cos_angle,
            sin_angle,
            rotation_axis,
        )

        particle.vx = center_vx + rotated_vx
        particle.vy = center_vy + rotated_vy
        particle.vz = center_vz + rotated_vz
    end
end

function rotate_velocity_about_axis(
    vx::Float64,
    vy::Float64,
    vz::Float64,
    cos_angle::Float64,
    sin_angle::Float64,
    axis::Symbol,
)
    if axis == :x
        return vx, cos_angle * vy - sin_angle * vz, sin_angle * vy + cos_angle * vz
    elseif axis == :y
        return cos_angle * vx + sin_angle * vz, vy, -sin_angle * vx + cos_angle * vz
    elseif axis == :z
        return cos_angle * vx - sin_angle * vy, sin_angle * vx + cos_angle * vy, vz
    end

    throw(ArgumentError("El eje de rotacion MPC debe ser x, y o z."))
end

function generate_mpc_concentration_maps(
    initialization::MpcParticleInitialization,
    space::SimulationSpace,
    config::MpcModelConfig;
    steps::Int = 1,
    seed::Int = 1234,
)
    if steps < 0
        throw(ArgumentError("El numero de pasos para mapas de concentracion MPC no puede ser negativo."))
    end

    validate_mpc_config(config)

    requested_output_times, captured_output_times = normalize_mpc_output_times(
        config.output_times,
        steps,
    )
    captured_output_set = Set(captured_output_times)
    density_sums = Dict(
        time => zeros(Float64, space.height, space.width)
        for time in captured_output_times
    )
    realization_seeds = Int[]
    particle_count_sum = 0.0
    representative_density_grids = Dict{Int,Matrix{Float64}}()

    for realization_index in 1:config.realizations
        realization_seed = seed + (realization_index - 1) * 10007
        realization_initialization = realization_index == 1 ? initialization : initialize_mpc_particles(
            space,
            config;
            seed = realization_seed,
        )
        particles = copy_mpc_particles(realization_initialization.particles)

        push!(realization_seeds, realization_seed)
        particle_count_sum += length(realization_initialization.particles)

        if 0 in captured_output_set
            density_grid = build_mpc_concentration_grid(particles, space)
            density_sums[0] .+= density_grid
            if realization_index == 1
                representative_density_grids[0] = copy(density_grid)
            end
        end

        for step in 1:steps
            step_initialization = MpcParticleInitialization(
                realization_initialization.seed,
                length(particles),
                realization_initialization.domain_volume,
                realization_initialization.velocity_sigma,
                realization_initialization.rejected_samples,
                particles,
            )
            step_streaming = stream_mpc_particles(
                step_initialization,
                space,
                config;
                steps = 1,
            )
            step_collision = collide_mpc_particles(
                step_streaming,
                space,
                config;
                seed = realization_seed + step,
            )
            particles = copy_mpc_particles(step_collision.particles)

            if step in captured_output_set
                density_grid = build_mpc_concentration_grid(particles, space)
                density_sums[step] .+= density_grid
                if realization_index == 1
                    representative_density_grids[step] = copy(density_grid)
                end
            end
        end
    end

    snapshots = [
        build_mpc_concentration_snapshot_from_grid(
            time,
            density_sums[time] ./ config.realizations,
            space,
            config,
        )
        for time in captured_output_times
    ]
    representative_snapshots = [
        build_mpc_concentration_snapshot_from_grid(
            time,
            representative_density_grids[time],
            space,
            config,
        )
        for time in captured_output_times
    ]

    return MpcConcentrationResult(
        requested_output_times,
        captured_output_times,
        config.realizations,
        realization_seeds,
        config.n0,
        high_concentration_threshold(config),
        particle_count_sum / config.realizations,
        snapshots,
        1,
        first(realization_seeds),
        representative_snapshots,
    )
end

function normalize_mpc_output_times(output_times::Vector{Int}, steps::Int)
    requested_output_times = sort(unique(output_times))
    captured_output_times = Int[0]

    for output_time in requested_output_times
        if 0 <= output_time <= steps && !(output_time in captured_output_times)
            push!(captured_output_times, output_time)
        end
    end

    if !(steps in captured_output_times)
        push!(captured_output_times, steps)
    end

    return requested_output_times, sort(unique(captured_output_times))
end

function build_mpc_concentration_snapshot(
    time::Int,
    particles::Vector{MpcParticle},
    space::SimulationSpace,
    config::MpcModelConfig,
)
    density_grid = build_mpc_concentration_grid(particles, space)

    return build_mpc_concentration_snapshot_from_grid(
        time,
        density_grid,
        space,
        config,
    )
end

function build_mpc_concentration_snapshot_from_grid(
    time::Int,
    density_grid::Matrix{Float64},
    space::SimulationSpace,
    config::MpcModelConfig,
)
    high_mask = BitMatrix((density_grid .> high_concentration_threshold(config)) .& space.domain_mask)

    return MpcConcentrationSnapshot(
        time,
        density_grid,
        high_mask,
        sum(density_grid),
        maximum(density_grid),
        count(high_mask),
    )
end

function build_mpc_concentration_grid(particles::Vector{MpcParticle}, space::SimulationSpace)
    density_grid = zeros(Float64, space.height, space.width)

    for particle in particles
        cell_x, cell_y = particle_cell_indices(particle, space)
        if !space.domain_mask[cell_y + 1, cell_x + 1]
            continue
        end

        density_grid[cell_y + 1, cell_x + 1] += 1.0
    end

    return density_grid
end

function high_concentration_threshold(config::MpcModelConfig)
    return 2.0 * config.n0
end

function calculate_mpc_velocity_autocorrelation(
    space::SimulationSpace,
    config::MpcModelConfig;
    steps::Int = 1,
    seed::Int = 1234,
)
    if steps < 0
        throw(ArgumentError("El numero de pasos para autocorrelacion no puede ser negativo."))
    end

    validate_mpc_config(config)

    histories = Vector{Vector{Matrix{Float64}}}()
    realization_seeds = Int[]
    selected_labeled_ids = Int[]
    trajectory_steps = steps + config.correlation_initial_times - 1

    for realization_index in 1:config.realizations
        realization_seed = seed + (realization_index - 1) * 10007
        initialization = initialize_mpc_particles(space, config; seed = realization_seed)

        if isempty(selected_labeled_ids)
            selected_labeled_ids = select_labeled_particle_ids(initialization, config)
        end

        push!(
            histories,
            simulate_mpc_velocity_history(
                initialization,
                space,
                config;
                steps = trajectory_steps,
                seed = realization_seed,
                particle_ids = selected_labeled_ids,
            ),
        )
        push!(realization_seeds, realization_seed)
    end

    initial_times = select_correlation_initial_times(
        trajectory_steps,
        steps,
        config.correlation_initial_times,
    )

    return calculate_velocity_autocorrelation(
        histories,
        collect(1:length(selected_labeled_ids)),
        initial_times;
        tau = config.tau,
        dimension = 2,
        max_lag = steps,
        realization_seeds = realization_seeds,
        requested_labeled_particles = config.labeled_particles,
        requested_initial_time_count = config.correlation_initial_times,
    )
end

function calculate_velocity_autocorrelation(
    velocity_histories::Vector{Vector{Matrix{Float64}}},
    labeled_particle_ids::Vector{Int},
    initial_times::Vector{Int};
    tau::Float64 = 1.0,
    dimension::Int = 2,
    max_lag::Union{Nothing,Int} = nothing,
    realization_seeds::Vector{Int} = collect(1:length(velocity_histories)),
    requested_labeled_particles::Int = length(labeled_particle_ids),
    requested_initial_time_count::Int = length(initial_times),
)
    if isempty(velocity_histories)
        throw(ArgumentError("Debe existir al menos una realizacion para calcular Cv."))
    end

    if isempty(labeled_particle_ids)
        throw(ArgumentError("Debe existir al menos una particula etiquetada para calcular Cv."))
    end

    if isempty(initial_times)
        throw(ArgumentError("Debe existir al menos un tiempo inicial para calcular Cv."))
    end

    if tau <= 0
        throw(ArgumentError("El paso temporal tau debe ser mayor que cero."))
    end

    if dimension <= 0
        throw(ArgumentError("La dimension efectiva para MDC debe ser mayor que cero."))
    end

    trajectory_steps = minimum(length(history) - 1 for history in velocity_histories)
    latest_initial_time = maximum(initial_times)
    available_max_lag = trajectory_steps - latest_initial_time
    resolved_max_lag = max_lag === nothing ? available_max_lag : max_lag

    if resolved_max_lag < 0 || resolved_max_lag > available_max_lag
        throw(ArgumentError("Todos los tiempos iniciales deben tener una ventana completa de autocorrelacion."))
    end

    cv_sums = zeros(Float64, resolved_max_lag + 1)
    sample_counts = zeros(Int, resolved_max_lag + 1)
    realization_mdc_values = Float64[]
    realization_cv0_values = Float64[]
    realization_cv_final_values = Float64[]
    realization_sample_counts = Int[]

    for history in velocity_histories
        particle_count = size(first(history), 1)
        realization_cv_sums = zeros(Float64, resolved_max_lag + 1)
        realization_counts = zeros(Int, resolved_max_lag + 1)

        for particle_id in labeled_particle_ids
            if !(1 <= particle_id <= particle_count)
                throw(ArgumentError("Una particula etiquetada no existe en el historial de velocidades."))
            end
        end

        for initial_time in initial_times
            if initial_time < 0
                throw(ArgumentError("Los tiempos iniciales de autocorrelacion no pueden ser negativos."))
            end

            if initial_time + resolved_max_lag > length(history) - 1
                throw(ArgumentError("Un tiempo inicial no dispone de la ventana completa solicitada."))
            end

            for lag in 0:resolved_max_lag
                target_time = initial_time + lag

                for particle_id in labeled_particle_ids
                    initial_velocity = history[initial_time + 1][particle_id, :]
                    target_velocity = history[target_time + 1][particle_id, :]
                    cv_sums[lag + 1] += (
                        initial_velocity[1] * target_velocity[1] +
                        initial_velocity[2] * target_velocity[2]
                    )
                    sample_counts[lag + 1] += 1
                    realization_cv_sums[lag + 1] += (
                        initial_velocity[1] * target_velocity[1] +
                        initial_velocity[2] * target_velocity[2]
                    )
                    realization_counts[lag + 1] += 1
                end
            end
        end

        realization_cv_values = [
            sample_count == 0 ? 0.0 : cv_sum / sample_count
            for (cv_sum, sample_count) in zip(realization_cv_sums, realization_counts)
        ]
        push!(
            realization_mdc_values,
            integrate_velocity_autocorrelation(realization_cv_values, tau, dimension),
        )
        push!(realization_cv0_values, first(realization_cv_values))
        push!(realization_cv_final_values, last(realization_cv_values))
        push!(realization_sample_counts, sum(realization_counts))
    end

    cv_values = [
        sample_count == 0 ? 0.0 : cv_sum / sample_count
        for (cv_sum, sample_count) in zip(cv_sums, sample_counts)
    ]
    normalized_cv_values = normalize_velocity_autocorrelation(cv_values)
    mdc = sum(realization_mdc_values) / length(realization_mdc_values)
    characteristic_time = estimate_characteristic_decay_time(normalized_cv_values, tau)

    return MpcVelocityAutocorrelationResult(
        resolved_max_lag,
        trajectory_steps,
        tau,
        dimension,
        length(velocity_histories),
        requested_labeled_particles,
        length(labeled_particle_ids),
        requested_initial_time_count,
        sort(unique(initial_times)),
        realization_seeds,
        cv_values,
        normalized_cv_values,
        sample_counts,
        mdc,
        characteristic_time,
        realization_mdc_values,
        realization_cv0_values,
        realization_cv_final_values,
        realization_sample_counts,
    )
end

function simulate_mpc_velocity_history(
    initialization::MpcParticleInitialization,
    space::SimulationSpace,
    config::MpcModelConfig;
    steps::Int = 1,
    seed::Int = 1234,
    particle_ids::Union{Nothing,Vector{Int}} = nothing,
)
    particles = copy_mpc_particles(initialization.particles)
    selected_particle_ids = particle_ids === nothing ? collect(eachindex(particles)) : particle_ids
    history = Matrix{Float64}[mpc_velocity_matrix(particles, selected_particle_ids)]

    for step in 1:steps
        step_initialization = MpcParticleInitialization(
            initialization.seed,
            length(particles),
            initialization.domain_volume,
            initialization.velocity_sigma,
            initialization.rejected_samples,
            particles,
        )
        step_streaming = stream_mpc_particles(
            step_initialization,
            space,
            config;
            steps = 1,
        )
        step_collision = collide_mpc_particles(
            step_streaming,
            space,
            config;
            seed = seed + step,
        )
        particles = copy_mpc_particles(step_collision.particles)
        push!(history, mpc_velocity_matrix(particles, selected_particle_ids))
    end

    return history
end

function mpc_velocity_matrix(
    particles::Vector{MpcParticle},
    particle_ids::Vector{Int} = collect(eachindex(particles)),
)
    velocities = zeros(Float64, length(particle_ids), 2)

    for (row_index, particle_id) in enumerate(particle_ids)
        if !(1 <= particle_id <= length(particles))
            throw(ArgumentError("Una particula seleccionada no existe para guardar su velocidad."))
        end

        particle = particles[particle_id]
        velocities[row_index, 1] = particle.vx
        velocities[row_index, 2] = particle.vy
    end

    return velocities
end

function select_labeled_particle_ids(
    initialization::MpcParticleInitialization,
    config::MpcModelConfig,
)
    labeled_ids = [
        particle.id
        for particle in initialization.particles
        if particle.labeled
    ]

    if !isempty(labeled_ids)
        return labeled_ids
    end

    fallback_count = min(config.labeled_particles, length(initialization.particles))

    if fallback_count == 0
        fallback_count = min(DEFAULT_MPC_LABELED_PARTICLES, length(initialization.particles))
    end

    return collect(1:fallback_count)
end

function select_correlation_initial_times(
    trajectory_steps::Int,
    max_lag::Int,
    requested_count::Int,
)
    if requested_count < 1
        throw(ArgumentError("Debe existir al menos un tiempo inicial para la autocorrelacion."))
    end

    if trajectory_steps < 0 || max_lag < 0 || max_lag > trajectory_steps
        throw(ArgumentError("La trayectoria no permite el horizonte de autocorrelacion solicitado."))
    end

    available_times = collect(0:(trajectory_steps - max_lag))

    if requested_count >= length(available_times)
        return available_times
    end

    if requested_count == 1
        return [first(available_times)]
    end

    positions = round.(Int, range(1, length(available_times), length = requested_count))

    return sort(unique(available_times[positions]))
end

function normalize_velocity_autocorrelation(cv_values::Vector{Float64})
    if isempty(cv_values) || !isfinite(cv_values[1]) || cv_values[1] <= 0
        throw(ArgumentError("Cv(0) debe ser finito y mayor que cero para normalizar."))
    end

    return cv_values ./ cv_values[1]
end

function integrate_velocity_autocorrelation(
    cv_values::Vector{Float64},
    tau::Float64,
    dimension::Int,
)
    if length(cv_values) <= 1
        return 0.0
    end

    integral = 0.0

    for index in 1:(length(cv_values) - 1)
        integral += 0.5 * (cv_values[index] + cv_values[index + 1]) * tau
    end

    return integral / dimension
end

function estimate_characteristic_decay_time(cv_values::Vector{Float64}, tau::Float64)
    if isempty(cv_values) || cv_values[1] <= 0
        return nothing
    end

    numerator = 0.0
    denominator = 0.0
    normalized_cv = normalize_velocity_autocorrelation(cv_values)

    for lag in 1:(length(normalized_cv) - 1)
        current_cv = normalized_cv[lag + 1]

        if !isfinite(current_cv) || !(0 < current_cv < 1.0)
            break
        end

        time = lag * tau
        numerator += time * log(current_cv)
        denominator += time^2
    end

    if denominator == 0
        return nothing
    end

    slope = numerator / denominator

    if slope >= 0
        return nothing
    end

    return -1 / slope
end

function calculate_theoretical_mdc0(config::MpcModelConfig)
    validate_mpc_config(config)

    denominator = config.n0 - 1 + exp(-config.n0)

    if denominator <= 0
        throw(ArgumentError("La referencia teorica MDC0 tiene denominador invalido."))
    end

    numerator = 2 * config.n0 + 1 - exp(-config.n0)

    return (config.kbt * config.tau / (2 * config.mass)) * (numerator / denominator)
end

function calculate_mdc_star(mdc::Real, mdc0::Real)
    if !isfinite(mdc)
        throw(ArgumentError("MDC debe ser finito para normalizar."))
    end

    if !isfinite(mdc0) || mdc0 <= 0
        throw(ArgumentError("MDC0 debe ser finito y mayor que cero para normalizar."))
    end

    return mdc / mdc0
end

function build_comparable_diffusion_metrics(
    autocorrelation::MpcVelocityAutocorrelationResult,
    config::MpcModelConfig,
)
    mdc0 = calculate_theoretical_mdc0(config)
    mdc_star = calculate_mdc_star(autocorrelation.mdc, mdc0)
    mdc_standard_deviation = standard_deviation(autocorrelation.realization_mdc_values)
    mdc_standard_error = standard_error(autocorrelation.realization_mdc_values)
    realization_mdc_star_values = [
        calculate_mdc_star(realization_mdc, mdc0)
        for realization_mdc in autocorrelation.realization_mdc_values
    ]
    mdc_star_standard_deviation = standard_deviation(realization_mdc_star_values)
    mdc_star_standard_error = standard_error(realization_mdc_star_values)

    return MpcComparableDiffusionMetrics(
        "mdc_normalized_against_theoretical_reference",
        "theoretical_mdc0_without_obstacles",
        "Metrica relativa para prototipo academico/investigativo; no constituye diagnostico clinico.",
        "reduced_mpc_units",
        autocorrelation.mdc,
        mdc0,
        mdc_star,
        mdc_standard_deviation,
        mdc_standard_error,
        autocorrelation.realization_mdc_values,
        realization_mdc_star_values,
        mdc_star_standard_deviation,
        mdc_star_standard_error,
        config.n0,
        config.mass,
        config.kbt,
        config.tau,
        config.realizations,
        autocorrelation.labeled_particle_count,
        length(autocorrelation.initial_times),
        autocorrelation.characteristic_time,
    )
end

function standard_deviation(values::Vector{Float64})
    if length(values) <= 1
        return 0.0
    end

    average = sum(values) / length(values)
    variance = sum((value - average)^2 for value in values) / (length(values) - 1)

    return sqrt(variance)
end

function standard_error(values::Vector{Float64})
    if isempty(values)
        return 0.0
    end

    return standard_deviation(values) / sqrt(length(values))
end

function synthetic_validation_case_names()
    return collect(DEFAULT_SYNTHETIC_VALIDATION_CASES)
end

function build_synthetic_validation_case(name::AbstractString)
    case_name = lowercase(String(name))

    if case_name == "free_field"
        image = PgmImage(8, 8, 255, fill(255, 8, 8))
        return synthetic_validation_case(
            case_name,
            "Dominio completo con intensidad maxima; sirve como referencia sin obstaculos bloqueantes.",
            image,
            "Equivalente conceptual a noObstacles del programa C; los radios derivados son casi nulos.",
        )
    elseif case_name == "central_obstacle"
        pixels = fill(255, 9, 9)
        pixels[4:6, 4:6] .= 0
        image = PgmImage(9, 9, 255, pixels)
        return synthetic_validation_case(
            case_name,
            "Dominio completo con bloque oscuro central para validar rebote contra obstaculo cilindrico.",
            image,
            "Comparable con un obstaculo cilindrico central del programa C.",
        )
    elseif case_name == "intensity_pattern"
        pixels = [
            80 100 120 140 160 180 220 255
            90 110 130 150 170 190 225 255
            100 120 140 160 180 200 230 255
            110 130 150 170 190 210 235 255
            120 140 160 180 200 220 240 255
            130 150 170 190 210 230 245 255
            140 160 180 200 220 235 250 255
            150 170 190 210 225 240 252 255
        ]
        image = PgmImage(8, 8, 255, pixels)
        return synthetic_validation_case(
            case_name,
            "Gradiente simple de intensidades para validar radios y matriz de obstaculos.",
            image,
            "Caso de correspondencia intensidad-radio frente al uso de matrix.in del C.",
        )
    elseif case_name == "clear_dark_channel"
        pixels = fill(80, 8, 10)
        pixels[:, 5:6] .= 255
        pixels[1, :] .= 255
        pixels[end, :] .= 255
        image = PgmImage(10, 8, 255, pixels)
        return synthetic_validation_case(
            case_name,
            "Canal claro vertical rodeado de tejido oscuro para validar caminos de baja obstruccion.",
            image,
            "Sirve para comparar concentracion esperada en zonas con menor radio de obstaculos.",
        )
    elseif case_name == "synthetic_roi"
        pixels = [
            0 0 0 0 0 0 0 0 0 0 0 0
            0 0 70 100 130 150 170 190 180 120 0 0
            0 60 110 150 190 210 230 240 220 160 80 0
            0 80 130 180 220 245 255 250 230 180 90 0
            0 75 120 165 205 235 245 240 210 150 70 0
            0 0 70 110 150 180 200 190 160 100 0 0
            0 0 0 60 90 120 130 110 80 0 0 0
            0 0 0 0 0 0 0 0 0 0 0 0
        ]
        image = PgmImage(12, 8, 255, pixels)
        return synthetic_validation_case(
            case_name,
            "ROI mamaria sintetica no sensible con forma organica e intensidades internas variadas.",
            image,
            "Sustituye una ROI real para pruebas de repositorio sin datos clinicos.",
        )
    end

    throw(ArgumentError("Caso sintetico de validacion no reconocido: $(name)"))
end

function synthetic_validation_case(
    name::String,
    description::String,
    image::PgmImage,
    notes::String,
)
    space = build_simulation_space(image)

    return SyntheticValidationCase(
        name,
        description,
        image,
        count_domain_cells(space),
        count_preliminary_blocking_obstacles(space),
        notes,
    )
end

function generate_synthetic_validation_cases(output_dir::AbstractString)
    mkpath(output_dir)
    cases = [build_synthetic_validation_case(name) for name in synthetic_validation_case_names()]

    for validation_case in cases
        case_dir = joinpath(output_dir, validation_case.name)
        write_synthetic_validation_case(case_dir, validation_case)
    end

    write_validation_cases_index(joinpath(output_dir, "validation_cases.tsv"), cases)

    return cases
end

function validate_synthetic_cases(
    output_dir::AbstractString;
    seed::Int = 1234,
    steps::Int = 5,
    mpc_config::Union{Nothing,MpcModelConfig} = nothing,
)
    if steps < 0
        throw(ArgumentError("El numero de pasos de validacion no puede ser negativo."))
    end

    resolved_config = if mpc_config === nothing
        MpcModelConfig(
            n0 = 1.0,
            labeled_particles = 8,
            correlation_initial_times = 2,
            output_times = [0, steps],
        )
    else
        mpc_config
    end

    validate_mpc_config(resolved_config)
    mkpath(output_dir)
    cases = generate_synthetic_validation_cases(joinpath(output_dir, "cases"))
    results = SyntheticValidationResult[]

    for validation_case in cases
        case_dir = joinpath(output_dir, "cases", validation_case.name)
        input_path = joinpath(case_dir, "input.pgm")
        result_dir = joinpath(case_dir, "results")
        run_result = run_case(
            SimulationRunConfig(
                input_path = input_path,
                output_dir = result_dir,
                seed = seed,
                steps = steps,
                mpc_config = resolved_config,
            ),
        )
        concentration_particle_sum_value = last(run_result.mpc_concentration.snapshots).particle_count
        concentration_particle_sum = round(Int, concentration_particle_sum_value)
        actual_domain_cell_count = count_domain_cells(run_result.space)
        actual_blocking_count = count_preliminary_blocking_obstacles(run_result.space)
        particle_count = length(run_result.mpc_initialization.particles)
        particle_conservation_ok = isapprox(concentration_particle_sum_value, particle_count; atol = 1e-8)
        status = (
            actual_domain_cell_count == validation_case.expected_domain_cell_count &&
            actual_blocking_count == validation_case.expected_preliminary_blocking_obstacle_count &&
            particle_conservation_ok
        ) ? "ok" : "review"

        push!(
            results,
            SyntheticValidationResult(
                validation_case.name,
                status,
                input_path,
                result_dir,
                validation_case.expected_domain_cell_count,
                actual_domain_cell_count,
                validation_case.expected_preliminary_blocking_obstacle_count,
                actual_blocking_count,
                particle_count,
                concentration_particle_sum,
                particle_conservation_ok,
                run_result.mpc_diffusion_metrics.mdc,
                run_result.mpc_diffusion_metrics.mdc0,
                run_result.mpc_diffusion_metrics.mdc_star,
            ),
        )
    end

    write_validation_summary_tsv(joinpath(output_dir, "validation_summary.tsv"), results)
    write_validation_summary_md(joinpath(output_dir, "validation_summary.md"), results)

    return results
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
    mpc_streaming::Union{Nothing,MpcStreamingResult} = nothing,
    mpc_collision::Union{Nothing,MpcCollisionResult} = nothing,
    mpc_concentration::Union{Nothing,MpcConcentrationResult} = nothing,
    mpc_velocity_autocorrelation::Union{Nothing,MpcVelocityAutocorrelationResult} = nothing,
    mpc_diffusion_metrics::Union{Nothing,MpcComparableDiffusionMetrics} = nothing,
    simulation_box_visualization_path::Union{Nothing,String} = nothing,
    simulation_box_visualization_metadata_path::Union{Nothing,String} = nothing,
)
    config = run_config.mpc_config
    fields = Any[
        ("created_at", timestamp),
        ("input_role", config.input_role),
        ("configuration_model", MPC_CONFIGURATION_MODEL),
        ("execution_engine", SIMULATION_ENGINE_MPC),
        ("simulation_note", "MPC dynamics, concentration maps and diffusion metrics generated by the production pipeline."),
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
        ("correlation_initial_times", config.correlation_initial_times),
        ("output_times", config.output_times),
        ("grid_shift_enabled", config.grid_shift_enabled),
        ("grid_shift_decision", config.grid_shift_decision),
        ("seed", run_config.seed),
        ("steps", run_config.steps),
        ("tissue_threshold", space.tissue_threshold),
        ("tissue_threshold_ratio", DEFAULT_TISSUE_THRESHOLD_RATIO),
        ("domain_mask_model", DOMAIN_MASK_MODEL),
        ("domain_mask_exterior_policy", "exclude_background_connected_to_image_border"),
        ("domain_mask_internal_dark_policy", "preserve_enclosed_dark_regions"),
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

    if simulation_box_visualization_path !== nothing
        append!(
            fields,
            [
                ("simulation_box_visualization_model", SIMULATION_BOX_VISUALIZATION_MODEL),
                ("simulation_box_visualization_file", basename(simulation_box_visualization_path)),
                ("simulation_box_visualization_note", "Representacion pseudo-3D del dominio mesoscopico; no es una reconstruccion anatomica 3D real."),
                ("simulation_box_visualization_max_cylinders", SIMULATION_BOX_VISUALIZATION_MAX_CYLINDERS),
                ("simulation_box_visualization_max_particles", SIMULATION_BOX_VISUALIZATION_MAX_PARTICLES),
                ("simulation_box_visualization_max_columns", SIMULATION_BOX_VISUALIZATION_MAX_COLUMNS),
                ("simulation_box_visualization_max_rows", SIMULATION_BOX_VISUALIZATION_MAX_ROWS),
                ("simulation_box_visualization_max_directions", SIMULATION_BOX_VISUALIZATION_MAX_DIRECTIONS),
                ("simulation_box_visualization_metadata_file", "simulation_box_visualization.txt"),
            ],
        )
    end

    if mpc_streaming !== nothing
        append!(
            fields,
            [
                ("mpc_streaming_model", "free_translation_periodic_boundaries_bounce_back"),
                ("mpc_streaming_steps", mpc_streaming.steps),
                ("mpc_streaming_tau", mpc_streaming.tau),
                ("mpc_streaming_obstacle_collision_count", mpc_streaming.obstacle_collision_count),
                ("mpc_streaming_domain_boundary_collision_count", mpc_streaming.domain_boundary_collision_count),
                ("mpc_streaming_boundary_crossing_count_x", mpc_streaming.boundary_crossing_count_x),
                ("mpc_streaming_boundary_crossing_count_y", mpc_streaming.boundary_crossing_count_y),
            ],
        )
    end

    if mpc_collision !== nothing
        append!(
            fields,
            [
                ("mpc_collision_model", "multiparticle_collision_by_cell"),
                ("mpc_collision_seed", mpc_collision.seed),
                ("mpc_collision_rotation_angle", mpc_collision.rotation_angle),
                ("mpc_collision_active_cell_count", mpc_collision.active_cell_count),
                ("mpc_collision_cell_count", mpc_collision.collision_cell_count),
                ("mpc_collision_singleton_cell_count", mpc_collision.singleton_cell_count),
                ("mpc_collision_particle_count", mpc_collision.particle_count),
                ("mpc_collision_max_particles_per_cell", mpc_collision.max_particles_per_cell),
            ],
        )
    end

    if mpc_concentration !== nothing
        append!(
            fields,
            [
                ("mpc_concentration_model", "particles_per_cell_snapshot"),
                ("mpc_concentration_aggregation", "mean_across_realizations"),
                ("mpc_concentration_realizations", mpc_concentration.realization_count),
                ("mpc_concentration_realization_seeds", mpc_concentration.realization_seeds),
                ("mpc_concentration_requested_output_times", mpc_concentration.requested_output_times),
                ("mpc_concentration_captured_output_times", mpc_concentration.captured_output_times),
                ("mpc_concentration_expected_density_n0", mpc_concentration.expected_density),
                ("mpc_concentration_high_threshold", mpc_concentration.high_concentration_threshold),
                ("mpc_concentration_particle_count", mpc_concentration.particle_count),
                ("mpc_concentration_snapshot_count", length(mpc_concentration.snapshots)),
                ("mpc_concentration_representative_realization_index", mpc_concentration.representative_realization_index),
                ("mpc_concentration_representative_seed", mpc_concentration.representative_seed),
                ("mpc_concentration_visual_scale_max", mpc_concentration.high_concentration_threshold),
            ],
        )
    end

    if mpc_velocity_autocorrelation !== nothing
        append!(
            fields,
            [
                ("velocity_autocorrelation_model", "green_kubo_xy"),
                ("velocity_autocorrelation_aggregation", "mean_across_realizations"),
                ("velocity_autocorrelation_dimension", mpc_velocity_autocorrelation.dimension),
                ("velocity_autocorrelation_tau", mpc_velocity_autocorrelation.tau),
                ("velocity_autocorrelation_max_lag", mpc_velocity_autocorrelation.steps),
                ("velocity_autocorrelation_trajectory_steps", mpc_velocity_autocorrelation.trajectory_steps),
                ("velocity_autocorrelation_realizations", mpc_velocity_autocorrelation.realization_count),
                (
                    "velocity_autocorrelation_requested_labeled_particles",
                    mpc_velocity_autocorrelation.requested_labeled_particles,
                ),
                ("velocity_autocorrelation_labeled_particle_count", mpc_velocity_autocorrelation.labeled_particle_count),
                (
                    "velocity_autocorrelation_requested_initial_time_count",
                    mpc_velocity_autocorrelation.requested_initial_time_count,
                ),
                ("velocity_autocorrelation_initial_times", mpc_velocity_autocorrelation.initial_times),
                ("velocity_autocorrelation_realization_mdc_values", mpc_velocity_autocorrelation.realization_mdc_values),
                ("velocity_autocorrelation_mdc", mpc_velocity_autocorrelation.mdc),
                ("velocity_autocorrelation_mdc_standard_deviation", standard_deviation(mpc_velocity_autocorrelation.realization_mdc_values)),
                ("velocity_autocorrelation_mdc_standard_error", standard_error(mpc_velocity_autocorrelation.realization_mdc_values)),
                ("velocity_autocorrelation_characteristic_time", mpc_velocity_autocorrelation.characteristic_time),
            ],
        )
    end

    if mpc_diffusion_metrics !== nothing
        append!(
            fields,
            [
                ("diffusion_metric_model", mpc_diffusion_metrics.metric_model),
                ("diffusion_metric_reference_origin", mpc_diffusion_metrics.reference_origin),
                ("diffusion_metric_units", mpc_diffusion_metrics.units),
                ("diffusion_metric_mdc", mpc_diffusion_metrics.mdc),
                ("diffusion_metric_mdc0", mpc_diffusion_metrics.mdc0),
                ("diffusion_metric_mdc_star", mpc_diffusion_metrics.mdc_star),
                ("diffusion_metric_mdc_standard_deviation", mpc_diffusion_metrics.mdc_standard_deviation),
                ("diffusion_metric_mdc_standard_error", mpc_diffusion_metrics.mdc_standard_error),
                ("diffusion_metric_realization_mdc_star_values", mpc_diffusion_metrics.realization_mdc_star_values),
                ("diffusion_metric_mdc_star_standard_deviation", mpc_diffusion_metrics.mdc_star_standard_deviation),
                ("diffusion_metric_mdc_star_standard_error", mpc_diffusion_metrics.mdc_star_standard_error),
                ("diffusion_metric_purpose_note", mpc_diffusion_metrics.purpose_note),
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
        println(io, "execution_engine=$(SIMULATION_ENGINE_MPC)")
        println(io, "cell_length=$(mpc_config.cell_length)")
        println(io, "lx=$(mpc_box_lx(space, mpc_config))")
        println(io, "ly=$(mpc_box_ly(space, mpc_config))")
        println(io, "lz=$(mpc_config.lz)")
        println(io, "max_gray=$(space.max_gray)")
        println(io, "cell_count=$(cell_count)")
        println(io, "tissue_threshold=$(space.tissue_threshold)")
        println(io, "tissue_threshold_ratio=$(DEFAULT_TISSUE_THRESHOLD_RATIO)")
        println(io, "domain_mask_model=$(DOMAIN_MASK_MODEL)")
        println(io, "domain_mask_exterior_policy=exclude_background_connected_to_image_border")
        println(io, "domain_mask_internal_dark_policy=preserve_enclosed_dark_regions")
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

struct RgbCanvas
    width::Int
    height::Int
    pixels::Vector{UInt8}
end

function write_simulation_box_visualization_png(
    path::AbstractString,
    space::SimulationSpace,
    initialization::MpcParticleInitialization;
    width::Int = 1200,
    height::Int = 820,
    max_cylinders::Int = SIMULATION_BOX_VISUALIZATION_MAX_CYLINDERS,
    max_particles::Int = SIMULATION_BOX_VISUALIZATION_MAX_PARTICLES,
    max_directions::Int = SIMULATION_BOX_VISUALIZATION_MAX_DIRECTIONS,
    metadata_path::Union{Nothing,String} = nothing,
)
    section = select_visualization_section(space)
    canvas = RgbCanvas(width, height, rgb(248, 250, 252))
    projection = visualization_projection(section, space.lz, width, height)
    selected_obstacles = sample_visualization_obstacles(
        obstacles_in_visualization_section(space.obstacles, section),
        max_cylinders,
    )
    selected_particles = sample_visualization_particles(
        particles_in_visualization_section(initialization.particles, section, space.cell_length),
        max_particles,
    )

    draw_visualization_background!(canvas)
    draw_simulation_box_frame!(canvas, section, space, projection)

    for obstacle in selected_obstacles
        draw_obstacle_cylinder!(canvas, obstacle, projection, space.lz, section)
    end

    for (index, particle) in enumerate(selected_particles)
        draw_visualization_particle!(
            canvas,
            particle,
            projection,
            section,
            space.cell_length;
            draw_direction = index <= max_directions,
        )
    end

    write_png_rgb(path, canvas)

    if metadata_path !== nothing
        write_simulation_box_visualization_metadata(
            metadata_path,
            space,
            section,
            selected_obstacles,
            selected_particles,
            max_directions,
        )
    end

    return section
end

function visualization_projection(section, lz::Int, width::Int, height::Int)
    box_extent = max(section.width + section.height, 1)
    unit_x = (width - 160) / box_extent
    unit_y = (height - 190) / (box_extent * 0.46 + max(lz, 1) * 1.6)
    unit = min(unit_x, unit_y)
    origin_x = 80 + section.height * unit
    origin_y = 150.0
    z_scale = clamp(unit * 1.25, 24.0, 82.0)

    return (
        unit = unit,
        origin_x = origin_x,
        origin_y = origin_y,
        z_scale = z_scale,
    )
end

function project_visualization_point(x::Real, y::Real, z::Real, projection)
    screen_x = projection.origin_x + (x - y) * projection.unit
    screen_y = projection.origin_y + (x + y) * projection.unit * 0.46 - z * projection.z_scale

    return round(Int, screen_x), round(Int, screen_y)
end

function draw_visualization_background!(canvas::RgbCanvas)
    for y in 1:canvas.height
        shade = UInt8(clamp(round(Int, 252 - y / canvas.height * 15), 232, 252))
        for x in 1:canvas.width
            set_pixel!(canvas, x, y, (shade, shade, UInt8(255)))
        end
    end
end

function draw_simulation_box_frame!(canvas::RgbCanvas, section, space::SimulationSpace, projection)
    bottom = [
        project_visualization_point(0, 0, 0, projection),
        project_visualization_point(section.width, 0, 0, projection),
        project_visualization_point(section.width, section.height, 0, projection),
        project_visualization_point(0, section.height, 0, projection),
    ]
    top = [
        project_visualization_point(0, 0, space.lz, projection),
        project_visualization_point(section.width, 0, space.lz, projection),
        project_visualization_point(section.width, section.height, space.lz, projection),
        project_visualization_point(0, section.height, space.lz, projection),
    ]

    draw_filled_polygon!(canvas, bottom, rgb(236, 240, 246))
    draw_grid_lines!(canvas, section, projection)

    edge_color = rgb(28, 67, 96)
    light_edge = rgb(119, 145, 166)

    draw_polygon_outline!(canvas, bottom, light_edge; thickness = 2)
    draw_polygon_outline!(canvas, top, edge_color; thickness = 2)

    for index in 1:4
        draw_line!(
            canvas,
            bottom[index][1],
            bottom[index][2],
            top[index][1],
            top[index][2],
            light_edge;
            thickness = 2,
        )
    end
end

function draw_grid_lines!(canvas::RgbCanvas, section, projection)
    grid_color = rgb(186, 199, 214)

    for x in range(0.0, section.width; length = section.column_count + 1)
        x1, y1 = project_visualization_point(x, 0, 0, projection)
        x2, y2 = project_visualization_point(x, section.height, 0, projection)
        draw_line!(canvas, x1, y1, x2, y2, grid_color)
    end

    for y in range(0.0, section.height; length = section.row_count + 1)
        x1, y1 = project_visualization_point(0, y, 0, projection)
        x2, y2 = project_visualization_point(section.width, y, 0, projection)
        draw_line!(canvas, x1, y1, x2, y2, grid_color)
    end
end

function select_visualization_section(
    space::SimulationSpace;
    max_columns::Int = SIMULATION_BOX_VISUALIZATION_MAX_COLUMNS,
    max_rows::Int = SIMULATION_BOX_VISUALIZATION_MAX_ROWS,
)
    if max_columns <= 0 || max_rows <= 0
        throw(ArgumentError("La seccion visual debe contener al menos una celda."))
    end

    if isempty(space.obstacles)
        column_count = min(space.width, max_columns)
        row_count = min(space.height, max_rows)
        return build_visualization_section(space, 0, 0, column_count, row_count)
    end

    min_x, max_x = extrema(obstacle.x for obstacle in space.obstacles)
    min_y, max_y = extrema(obstacle.y for obstacle in space.obstacles)
    column_count = min(max_x - min_x + 1, max_columns)
    row_count = min(max_y - min_y + 1, max_rows)
    center_x = round(Int, (min_x + max_x) / 2)
    center_y = round(Int, (min_y + max_y) / 2)
    x_start = clamp(center_x - div(column_count, 2), min_x, max_x - column_count + 1)
    y_start = clamp(center_y - div(row_count, 2), min_y, max_y - row_count + 1)

    return build_visualization_section(
        space,
        x_start,
        y_start,
        column_count,
        row_count,
    )
end

function build_visualization_section(
    space::SimulationSpace,
    x_start::Int,
    y_start::Int,
    column_count::Int,
    row_count::Int,
)
    return (
        x_start = x_start,
        x_end = x_start + column_count,
        y_start = y_start,
        y_end = y_start + row_count,
        column_count = column_count,
        row_count = row_count,
        width = column_count * space.cell_length,
        height = row_count * space.cell_length,
        x_offset = x_start * space.cell_length,
        y_offset = y_start * space.cell_length,
    )
end

function obstacles_in_visualization_section(
    obstacles::Vector{SimulationObstacle},
    section,
)
    return [
        obstacle
        for obstacle in obstacles
        if section.x_start <= obstacle.x < section.x_end &&
           section.y_start <= obstacle.y < section.y_end
    ]
end

function particles_in_visualization_section(
    particles::Vector{MpcParticle},
    section,
    cell_length::Float64,
)
    x_min = section.x_start * cell_length
    x_max = section.x_end * cell_length
    y_min = section.y_start * cell_length
    y_max = section.y_end * cell_length

    return [
        particle
        for particle in particles
        if x_min <= particle.x < x_max && y_min <= particle.y < y_max
    ]
end

function sample_visualization_obstacles(obstacles::Vector{SimulationObstacle}, max_cylinders::Int)
    if length(obstacles) <= max_cylinders
        return sort(obstacles, by = obstacle -> (obstacle.x + obstacle.y, obstacle.y, obstacle.x))
    end

    stride = max(1, ceil(Int, sqrt(length(obstacles) / max_cylinders)))
    selected = [
        obstacle
        for obstacle in obstacles
        if obstacle.x % stride == 0 && obstacle.y % stride == 0
    ]

    if length(selected) > max_cylinders
        selected = selected[1:max_cylinders]
    end

    return sort(selected, by = obstacle -> (obstacle.x + obstacle.y, obstacle.y, obstacle.x))
end

function sample_visualization_particles(particles::Vector{MpcParticle}, max_particles::Int)
    if length(particles) <= max_particles
        return particles
    end

    stride = max(1, ceil(Int, length(particles) / max_particles))
    sampled = particles[1:stride:end]

    if length(sampled) > max_particles
        return sampled[1:max_particles]
    end

    return sampled
end

function draw_obstacle_cylinder!(
    canvas::RgbCanvas,
    obstacle::SimulationObstacle,
    projection,
    lz::Int,
    section,
)
    local_center_x = obstacle.center_x - section.x_offset
    local_center_y = obstacle.center_y - section.y_offset
    top_x, top_y = project_visualization_point(
        local_center_x,
        local_center_y,
        lz,
        projection,
    )
    bottom_x, bottom_y = project_visualization_point(
        local_center_x,
        local_center_y,
        0,
        projection,
    )
    display_radius = max(0.08, obstacle.radius)
    rx = max(2, round(Int, display_radius * projection.unit))
    ry = max(1, round(Int, rx * 0.42))
    shade = clamp(round(Int, 82 + obstacle.normalized_intensity * 110), 70, 210)
    side_color = rgb(shade, shade, shade)
    top_color = rgb(
        clamp(shade + 38, 0, 255),
        clamp(shade + 38, 0, 255),
        clamp(shade + 38, 0, 255),
    )
    outline_color = rgb(56, 72, 86)

    draw_filled_polygon!(
        canvas,
        [
            (top_x - rx, top_y),
            (top_x + rx, top_y),
            (bottom_x + rx, bottom_y),
            (bottom_x - rx, bottom_y),
        ],
        side_color,
    )
    draw_filled_ellipse!(canvas, bottom_x, bottom_y, rx, ry, rgb(max(shade - 22, 0), max(shade - 22, 0), max(shade - 22, 0)))
    draw_filled_ellipse!(canvas, top_x, top_y, rx, ry, top_color)
    draw_ellipse_outline!(canvas, top_x, top_y, rx, ry, outline_color)
    draw_line!(canvas, top_x - rx, top_y, bottom_x - rx, bottom_y, outline_color)
    draw_line!(canvas, top_x + rx, top_y, bottom_x + rx, bottom_y, outline_color)
end

function draw_visualization_particle!(
    canvas::RgbCanvas,
    particle::MpcParticle,
    projection,
    section,
    cell_length::Float64;
    draw_direction::Bool = true,
)
    local_x = particle.x - section.x_offset
    local_y = particle.y - section.y_offset
    x, y = project_visualization_point(local_x, local_y, particle.z, projection)

    speed_xy = hypot(particle.vx, particle.vy)
    if draw_direction && speed_xy > eps(Float64)
        direction_length = 0.38 * cell_length
        end_x = local_x + particle.vx / speed_xy * direction_length
        end_y = local_y + particle.vy / speed_xy * direction_length
        arrow_x, arrow_y = project_visualization_point(end_x, end_y, particle.z, projection)
        draw_line!(canvas, x, y, arrow_x, arrow_y, rgb(16, 122, 92); thickness = 2)
        draw_filled_circle!(canvas, arrow_x, arrow_y, 2, rgb(16, 122, 92))
    end

    draw_filled_circle!(canvas, x, y, 3, rgb(11, 18, 32))
    draw_filled_circle!(canvas, x - 1, y - 1, 1, rgb(238, 242, 246))
end

function write_simulation_box_visualization_metadata(
    path::AbstractString,
    space::SimulationSpace,
    section,
    obstacles::Vector{SimulationObstacle},
    particles::Vector{MpcParticle},
    max_directions::Int,
)
    full_domain_visualized = length(obstacles) == length(space.obstacles) && all(
        obstacle ->
            section.x_start <= obstacle.x < section.x_end &&
            section.y_start <= obstacle.y < section.y_end,
        space.obstacles,
    )

    open(path, "w") do io
        println(io, "visualization_model=$(SIMULATION_BOX_VISUALIZATION_MODEL)")
        println(io, "selection_policy=centered_domain_bounding_box_deterministic")
        println(io, "visualization_only=true")
        println(io, "simulated_domain_unchanged=true")
        println(io, "full_domain_visualized=$(full_domain_visualized)")
        println(io, "full_domain_width=$(space.width)")
        println(io, "full_domain_height=$(space.height)")
        println(io, "section_x_start=$(section.x_start)")
        println(io, "section_x_end_exclusive=$(section.x_end)")
        println(io, "section_y_start=$(section.y_start)")
        println(io, "section_y_end_exclusive=$(section.y_end)")
        println(io, "section_columns=$(section.column_count)")
        println(io, "section_rows=$(section.row_count)")
        println(io, "section_cell_count=$(section.column_count * section.row_count)")
        println(io, "visualized_cylinder_count=$(length(obstacles))")
        println(io, "visualized_particle_count=$(length(particles))")
        println(io, "visualized_direction_count=$(min(length(particles), max_directions))")
        println(io, "cell_length=$(space.cell_length)")
        println(io, "cylinder_radius_source=simulation_obstacle_radius_matrix")
        println(io, "dark_intensity_policy=larger_radius")
        println(io, "light_intensity_policy=smaller_radius")
        println(io, "background_cells_excluded=true")
        println(io, "legend_cells=projected_grid_lines")
        println(io, "legend_cylinders=gray_obstacles")
        println(io, "legend_particles=black_points")
        println(io, "legend_directions=green_lines")
    end
end

function rgb(red::Integer, green::Integer, blue::Integer)
    return (
        UInt8(clamp(red, 0, 255)),
        UInt8(clamp(green, 0, 255)),
        UInt8(clamp(blue, 0, 255)),
    )
end

function RgbCanvas(width::Int, height::Int, color::NTuple{3,UInt8})
    pixels = Vector{UInt8}(undef, width * height * 3)
    canvas = RgbCanvas(width, height, pixels)
    fill_canvas!(canvas, color)

    return canvas
end

function fill_canvas!(canvas::RgbCanvas, color::NTuple{3,UInt8})
    for y in 1:canvas.height
        for x in 1:canvas.width
            set_pixel!(canvas, x, y, color)
        end
    end
end

function set_pixel!(canvas::RgbCanvas, x::Int, y::Int, color::NTuple{3,UInt8})
    if x < 1 || x > canvas.width || y < 1 || y > canvas.height
        return
    end

    index = ((y - 1) * canvas.width + (x - 1)) * 3 + 1
    canvas.pixels[index] = color[1]
    canvas.pixels[index + 1] = color[2]
    canvas.pixels[index + 2] = color[3]
end

function draw_line!(
    canvas::RgbCanvas,
    x1::Int,
    y1::Int,
    x2::Int,
    y2::Int,
    color::NTuple{3,UInt8};
    thickness::Int = 1,
)
    dx = abs(x2 - x1)
    sx = x1 < x2 ? 1 : -1
    dy = -abs(y2 - y1)
    sy = y1 < y2 ? 1 : -1
    error = dx + dy
    x = x1
    y = y1

    while true
        if thickness <= 1
            set_pixel!(canvas, x, y, color)
        else
            draw_filled_circle!(canvas, x, y, max(1, thickness ÷ 2), color)
        end

        if x == x2 && y == y2
            break
        end

        doubled_error = 2 * error
        if doubled_error >= dy
            error += dy
            x += sx
        end
        if doubled_error <= dx
            error += dx
            y += sy
        end
    end
end

function draw_polygon_outline!(
    canvas::RgbCanvas,
    points::Vector{Tuple{Int,Int}},
    color::NTuple{3,UInt8};
    thickness::Int = 1,
)
    for index in eachindex(points)
        next_index = index == length(points) ? firstindex(points) : index + 1
        draw_line!(
            canvas,
            points[index][1],
            points[index][2],
            points[next_index][1],
            points[next_index][2],
            color;
            thickness = thickness,
        )
    end
end

function draw_filled_polygon!(
    canvas::RgbCanvas,
    points::Vector{Tuple{Int,Int}},
    color::NTuple{3,UInt8},
)
    min_x = max(1, minimum(first.(points)))
    max_x = min(canvas.width, maximum(first.(points)))
    min_y = max(1, minimum(last.(points)))
    max_y = min(canvas.height, maximum(last.(points)))

    for y in min_y:max_y
        for x in min_x:max_x
            if point_in_polygon(x, y, points)
                set_pixel!(canvas, x, y, color)
            end
        end
    end
end

function point_in_polygon(x::Int, y::Int, points::Vector{Tuple{Int,Int}})
    inside = false
    j = length(points)

    for i in eachindex(points)
        xi, yi = points[i]
        xj, yj = points[j]

        if (yi > y) != (yj > y)
            intersection_x = (xj - xi) * (y - yi) / (yj - yi) + xi
            if x < intersection_x
                inside = !inside
            end
        end

        j = i
    end

    return inside
end

function draw_filled_circle!(canvas::RgbCanvas, cx::Int, cy::Int, radius::Int, color::NTuple{3,UInt8})
    radius_squared = radius^2

    for y in (cy - radius):(cy + radius)
        for x in (cx - radius):(cx + radius)
            if (x - cx)^2 + (y - cy)^2 <= radius_squared
                set_pixel!(canvas, x, y, color)
            end
        end
    end
end

function draw_filled_ellipse!(
    canvas::RgbCanvas,
    cx::Int,
    cy::Int,
    rx::Int,
    ry::Int,
    color::NTuple{3,UInt8},
)
    rx_squared = max(rx^2, 1)
    ry_squared = max(ry^2, 1)

    for y in (cy - ry):(cy + ry)
        for x in (cx - rx):(cx + rx)
            if ((x - cx)^2 / rx_squared) + ((y - cy)^2 / ry_squared) <= 1.0
                set_pixel!(canvas, x, y, color)
            end
        end
    end
end

function draw_ellipse_outline!(
    canvas::RgbCanvas,
    cx::Int,
    cy::Int,
    rx::Int,
    ry::Int,
    color::NTuple{3,UInt8},
)
    steps = max(24, round(Int, 2 * pi * max(rx, ry)))
    previous = nothing

    for step in 0:steps
        angle = 2 * pi * step / steps
        point = (
            round(Int, cx + rx * cos(angle)),
            round(Int, cy + ry * sin(angle)),
        )

        if previous !== nothing
            draw_line!(canvas, previous[1], previous[2], point[1], point[2], color)
        end

        previous = point
    end
end

function write_png_rgb(path::AbstractString, canvas::RgbCanvas)
    raw = Vector{UInt8}()
    sizehint!(raw, canvas.height * (canvas.width * 3 + 1))

    for y in 1:canvas.height
        push!(raw, 0x00)
        row_start = ((y - 1) * canvas.width) * 3 + 1
        append!(raw, canvas.pixels[row_start:(row_start + canvas.width * 3 - 1)])
    end

    open(path, "w") do io
        write(io, UInt8[0x89, 0x50, 0x4e, 0x47, 0x0d, 0x0a, 0x1a, 0x0a])
        write_png_chunk(io, "IHDR", png_ihdr_data(canvas.width, canvas.height))
        write_png_chunk(io, "IDAT", zlib_uncompressed(raw))
        write_png_chunk(io, "IEND", UInt8[])
    end
end

function png_ihdr_data(width::Int, height::Int)
    data = UInt8[]
    append_uint32_be!(data, width)
    append_uint32_be!(data, height)
    append!(data, UInt8[0x08, 0x02, 0x00, 0x00, 0x00])

    return data
end

function write_png_chunk(io, chunk_type::String, data::Vector{UInt8})
    type_bytes = collect(codeunits(chunk_type))
    write_uint32_be(io, length(data))
    write(io, type_bytes)
    write(io, data)
    write_uint32_be(io, crc32(vcat(type_bytes, data)))
end

function zlib_uncompressed(data::Vector{UInt8})
    output = UInt8[0x78, 0x01]
    index = 1

    while index <= length(data)
        block_length = min(65535, length(data) - index + 1)
        is_final = index + block_length > length(data)
        push!(output, is_final ? 0x01 : 0x00)
        append_uint16_le!(output, block_length)
        append_uint16_le!(output, 0xffff - block_length)
        append!(output, data[index:(index + block_length - 1)])
        index += block_length
    end

    append_uint32_be!(output, adler32(data))

    return output
end

function write_uint32_be(io, value::Integer)
    write(io, UInt8[
        (value >> 24) & 0xff,
        (value >> 16) & 0xff,
        (value >> 8) & 0xff,
        value & 0xff,
    ])
end

function append_uint32_be!(buffer::Vector{UInt8}, value::Integer)
    push!(buffer, UInt8((value >> 24) & 0xff))
    push!(buffer, UInt8((value >> 16) & 0xff))
    push!(buffer, UInt8((value >> 8) & 0xff))
    push!(buffer, UInt8(value & 0xff))
end

function append_uint16_le!(buffer::Vector{UInt8}, value::Integer)
    push!(buffer, UInt8(value & 0xff))
    push!(buffer, UInt8((value >> 8) & 0xff))
end

function crc32(data::Vector{UInt8})
    crc = UInt32(0xffffffff)

    for byte in data
        crc = xor(crc, UInt32(byte))

        for _ in 1:8
            if (crc & UInt32(0x00000001)) == UInt32(1)
                crc = xor(crc >> 1, UInt32(0xedb88320))
            else
                crc >>= 1
            end
        end
    end

    return ~crc
end

function adler32(data::Vector{UInt8})
    modulo = 65521
    a = 1
    b = 0

    for byte in data
        a = (a + Int(byte)) % modulo
        b = (b + a) % modulo
    end

    return UInt32((b << 16) | a)
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

function write_mpc_streamed_particles_tsv(
    path::AbstractString,
    streaming::MpcStreamingResult,
)
    open(path, "w") do io
        println(io, "# steps=$(streaming.steps)")
        println(io, "# tau=$(streaming.tau)")
        println(io, "# obstacle_collision_count=$(streaming.obstacle_collision_count)")
        println(io, "# domain_boundary_collision_count=$(streaming.domain_boundary_collision_count)")
        println(io, "# boundary_crossing_count_x=$(streaming.boundary_crossing_count_x)")
        println(io, "# boundary_crossing_count_y=$(streaming.boundary_crossing_count_y)")
        println(io, "id\tx\ty\tz\tvx\tvy\tvz\tmass\tspecies\tlabeled")

        for particle in streaming.particles
            println(
                io,
                "$(particle.id)\t$(particle.x)\t$(particle.y)\t$(particle.z)\t$(particle.vx)\t$(particle.vy)\t$(particle.vz)\t$(particle.mass)\t$(particle.species)\t$(particle.labeled)",
            )
        end
    end
end

function write_mpc_streaming_summary(path::AbstractString, streaming::MpcStreamingResult)
    open(path, "w") do io
        println(io, "mpc_streaming_model=free_translation_periodic_boundaries_bounce_back")
        println(io, "steps=$(streaming.steps)")
        println(io, "tau=$(streaming.tau)")
        println(io, "particle_count=$(streaming.particle_count)")
        println(io, "obstacle_collision_count=$(streaming.obstacle_collision_count)")
        println(io, "domain_boundary_collision_count=$(streaming.domain_boundary_collision_count)")
        println(io, "boundary_crossing_count_x=$(streaming.boundary_crossing_count_x)")
        println(io, "boundary_crossing_count_y=$(streaming.boundary_crossing_count_y)")
        println(io, "completed_intervals=$(streaming.completed_intervals)")
    end
end

function write_mpc_collided_particles_tsv(
    path::AbstractString,
    collision::MpcCollisionResult,
)
    open(path, "w") do io
        println(io, "# seed=$(collision.seed)")
        println(io, "# rotation_angle=$(collision.rotation_angle)")
        println(io, "# active_cell_count=$(collision.active_cell_count)")
        println(io, "# collision_cell_count=$(collision.collision_cell_count)")
        println(io, "# singleton_cell_count=$(collision.singleton_cell_count)")
        println(io, "# particle_count=$(collision.particle_count)")
        println(io, "id\tx\ty\tz\tvx\tvy\tvz\tmass\tspecies\tlabeled")

        for particle in collision.particles
            println(
                io,
                "$(particle.id)\t$(particle.x)\t$(particle.y)\t$(particle.z)\t$(particle.vx)\t$(particle.vy)\t$(particle.vz)\t$(particle.mass)\t$(particle.species)\t$(particle.labeled)",
            )
        end
    end
end

function write_mpc_collision_summary(path::AbstractString, collision::MpcCollisionResult)
    open(path, "w") do io
        println(io, "mpc_collision_model=multiparticle_collision_by_cell")
        println(io, "seed=$(collision.seed)")
        println(io, "rotation_angle=$(collision.rotation_angle)")
        println(io, "rotation_policy=$(DEFAULT_MPC_ROTATION_POLICY)")
        println(io, "active_cell_count=$(collision.active_cell_count)")
        println(io, "collision_cell_count=$(collision.collision_cell_count)")
        println(io, "singleton_cell_count=$(collision.singleton_cell_count)")
        println(io, "particle_count=$(collision.particle_count)")
        println(io, "max_particles_per_cell=$(collision.max_particles_per_cell)")
    end
end

function write_mpc_cell_collisions_tsv(path::AbstractString, collision::MpcCollisionResult)
    open(path, "w") do io
        println(
            io,
            "cell_x\tcell_y\tparticle_count\tcenter_vx_before\tcenter_vy_before\tcenter_vz_before\tcenter_vx_after\tcenter_vy_after\tcenter_vz_after\trotation_angle\trotation_axis",
        )

        for cell in collision.cell_statistics
            println(
                io,
                "$(cell.cell_x)\t$(cell.cell_y)\t$(cell.particle_count)\t$(cell.center_vx_before)\t$(cell.center_vy_before)\t$(cell.center_vz_before)\t$(cell.center_vx_after)\t$(cell.center_vy_after)\t$(cell.center_vz_after)\t$(cell.rotation_angle)\t$(cell.rotation_axis)",
            )
        end
    end
end

function write_mpc_concentration_outputs(
    output_dir::AbstractString,
    concentration::MpcConcentrationResult,
    space::SimulationSpace,
)
    summary_path = joinpath(output_dir, "mpc_concentration_summary.txt")
    times_path = joinpath(output_dir, "mpc_concentration_times.tsv")
    representative_initial_map_path = joinpath(output_dir, "mpc_concentration_representative_initial.pgm")
    representative_final_map_path = joinpath(output_dir, "mpc_concentration_representative_final.pgm")
    mean_initial_map_path = joinpath(output_dir, "mpc_concentration_mean_initial.pgm")
    mean_final_map_path = joinpath(output_dir, "mpc_concentration_mean_final.pgm")
    mean_initial_high_map_path = joinpath(output_dir, "mpc_high_concentration_mean_initial.pgm")
    mean_final_high_map_path = joinpath(output_dir, "mpc_high_concentration_mean_final.pgm")
    representative_time_map_paths = String[]
    mean_time_map_paths = String[]
    mean_time_high_map_paths = String[]

    write_mpc_concentration_summary(summary_path, concentration)
    write_mpc_concentration_times_tsv(times_path, concentration, space)

    for (mean_snapshot, representative_snapshot) in zip(
        concentration.snapshots,
        concentration.representative_snapshots,
    )
        representative_time_map_path = joinpath(
            output_dir,
            "mpc_concentration_representative_t_$(representative_snapshot.time).pgm",
        )
        mean_time_map_path = joinpath(output_dir, "mpc_concentration_mean_t_$(mean_snapshot.time).pgm")
        mean_high_map_path = joinpath(output_dir, "mpc_high_concentration_mean_t_$(mean_snapshot.time).pgm")

        write_mpc_concentration_map_pgm(
            representative_time_map_path,
            representative_snapshot,
            space,
            concentration.high_concentration_threshold;
            aggregation = "representative_realization",
        )
        write_mpc_concentration_map_pgm(
            mean_time_map_path,
            mean_snapshot,
            space,
            concentration.high_concentration_threshold;
            aggregation = "mean_across_realizations",
        )
        write_mpc_high_concentration_map_pgm(mean_high_map_path, mean_snapshot, space)
        push!(representative_time_map_paths, representative_time_map_path)
        push!(mean_time_map_paths, mean_time_map_path)
        push!(mean_time_high_map_paths, mean_high_map_path)
    end

    mean_initial_snapshot = first(concentration.snapshots)
    mean_final_snapshot = last(concentration.snapshots)
    representative_initial_snapshot = first(concentration.representative_snapshots)
    representative_final_snapshot = last(concentration.representative_snapshots)
    write_mpc_concentration_map_pgm(representative_initial_map_path, representative_initial_snapshot, space, concentration.high_concentration_threshold; aggregation = "representative_realization")
    write_mpc_concentration_map_pgm(representative_final_map_path, representative_final_snapshot, space, concentration.high_concentration_threshold; aggregation = "representative_realization")
    write_mpc_concentration_map_pgm(mean_initial_map_path, mean_initial_snapshot, space, concentration.high_concentration_threshold; aggregation = "mean_across_realizations")
    write_mpc_concentration_map_pgm(mean_final_map_path, mean_final_snapshot, space, concentration.high_concentration_threshold; aggregation = "mean_across_realizations")
    write_mpc_high_concentration_map_pgm(mean_initial_high_map_path, mean_initial_snapshot, space)
    write_mpc_high_concentration_map_pgm(mean_final_high_map_path, mean_final_snapshot, space)

    return (
        summary_path = summary_path,
        times_path = times_path,
        representative_initial_map_path = representative_initial_map_path,
        representative_final_map_path = representative_final_map_path,
        mean_initial_map_path = mean_initial_map_path,
        mean_final_map_path = mean_final_map_path,
        mean_initial_high_map_path = mean_initial_high_map_path,
        mean_final_high_map_path = mean_final_high_map_path,
        representative_time_map_paths = representative_time_map_paths,
        mean_time_map_paths = mean_time_map_paths,
        mean_time_high_map_paths = mean_time_high_map_paths,
    )
end

function write_mpc_concentration_summary(
    path::AbstractString,
    concentration::MpcConcentrationResult,
)
    skipped_output_times = setdiff(
        concentration.requested_output_times,
        concentration.captured_output_times,
    )

    open(path, "w") do io
        println(io, "mpc_concentration_model=particles_per_cell_snapshot")
        println(io, "aggregation=mean_across_realizations")
        println(io, "representative_aggregation=single_realization")
        println(io, "representative_realization_index=$(concentration.representative_realization_index)")
        println(io, "representative_seed=$(concentration.representative_seed)")
        println(io, "realizations=$(concentration.realization_count)")
        println(io, "realization_seeds=$(join(concentration.realization_seeds, ","))")
        println(io, "requested_output_times=$(join(concentration.requested_output_times, ","))")
        println(io, "captured_output_times=$(join(concentration.captured_output_times, ","))")
        println(io, "skipped_output_times=$(join(skipped_output_times, ","))")
        println(io, "expected_density_n0=$(concentration.expected_density)")
        println(io, "high_concentration_threshold=$(concentration.high_concentration_threshold)")
        println(io, "particle_count=$(compact_numeric_value(concentration.particle_count))")
        println(io, "snapshot_count=$(length(concentration.snapshots))")
        println(io, "domain_mask_applied=true")

        for snapshot in concentration.snapshots
            println(io, "snapshot_t_$(snapshot.time)_particle_sum=$(compact_numeric_value(snapshot.particle_count))")
            println(io, "snapshot_t_$(snapshot.time)_max_concentration=$(compact_numeric_value(snapshot.max_concentration))")
            println(io, "snapshot_t_$(snapshot.time)_high_concentration_cell_count=$(snapshot.high_concentration_cell_count)")
        end
    end
end

function write_mpc_concentration_times_tsv(
    path::AbstractString,
    concentration::MpcConcentrationResult,
    space::SimulationSpace,
)
    radius_grid = obstacle_radius_grid(space)

    open(path, "w") do io
        println(
            io,
            "aggregation\trealization\tseed\ttime\tx\ty\tconcentration\tis_high_concentration\tis_domain\tobstacle_radius",
        )

        datasets = (
            ("mean_across_realizations", 0, 0, concentration.snapshots),
            (
                "representative_realization",
                concentration.representative_realization_index,
                concentration.representative_seed,
                concentration.representative_snapshots,
            ),
        )
        for (aggregation, realization, seed, snapshots) in datasets
            for snapshot in snapshots
                for y_index in axes(snapshot.density_grid, 1)
                    for x_index in axes(snapshot.density_grid, 2)
                    println(
                        io,
                        "$(aggregation)\t$(realization)\t$(seed)\t$(snapshot.time)\t$(x_index - 1)\t$(y_index - 1)\t$(snapshot.density_grid[y_index, x_index])\t$(snapshot.high_concentration_mask[y_index, x_index])\t$(space.domain_mask[y_index, x_index])\t$(radius_grid[y_index, x_index])",
                    )
                    end
                end
            end
        end
    end
end

function write_mpc_concentration_map_pgm(
    path::AbstractString,
    snapshot::MpcConcentrationSnapshot,
    space::SimulationSpace,
    visual_scale_max::Float64;
    aggregation::String,
)
    concentration_values = build_concentration_map_values(
        snapshot.density_grid,
        space.domain_mask,
        visual_scale_max,
    )
    height, width = size(concentration_values)

    open(path, "w") do io
        println(io, "P2")
        println(io, "# Mapa de concentracion MPC t=$(snapshot.time) aggregation=$(aggregation) scale_max=$(visual_scale_max)")
        println(io, "$(width) $(height)")
        println(io, "255")

        for y_index in 1:height
            println(io, join(vec(concentration_values[y_index, :]), " "))
        end
    end
end

function write_mpc_high_concentration_map_pgm(
    path::AbstractString,
    snapshot::MpcConcentrationSnapshot,
    space::SimulationSpace,
)
    height, width = size(snapshot.high_concentration_mask)

    open(path, "w") do io
        println(io, "P2")
        println(io, "# Celdas de alta concentracion MPC t=$(snapshot.time) generado por MammographySimulation")
        println(io, "$(width) $(height)")
        println(io, "255")

        for y_index in 1:height
            row = [
                if !space.domain_mask[y_index, x_index]
                    0
                elseif snapshot.high_concentration_mask[y_index, x_index]
                    255
                else
                    16
                end
                for x_index in 1:width
            ]
            println(io, join(row, " "))
        end
    end
end

function build_concentration_map_values(
    density_grid::AbstractMatrix{<:Real},
    domain_mask::BitMatrix,
    visual_scale_max::Real,
)
    if visual_scale_max <= 0
        throw(ArgumentError("La escala maxima del mapa de concentracion debe ser positiva."))
    end
    concentration_values = zeros(Int, size(density_grid))

    for index in eachindex(density_grid)
        if domain_mask[index]
            normalized_value = clamp(density_grid[index] / visual_scale_max, 0.0, 1.0)
            concentration_values[index] = 16 + round(Int, normalized_value * 239)
        end
    end

    return concentration_values
end

function write_velocity_autocorrelation_outputs(
    output_dir::AbstractString,
    autocorrelation::MpcVelocityAutocorrelationResult,
)
    autocorrelation_path = joinpath(output_dir, "velocity_autocorrelation.tsv")
    summary_path = joinpath(output_dir, "velocity_autocorrelation_summary.txt")
    realizations_path = joinpath(output_dir, "velocity_autocorrelation_realizations.tsv")

    write_velocity_autocorrelation_tsv(autocorrelation_path, autocorrelation)
    write_velocity_autocorrelation_summary(summary_path, autocorrelation)
    write_velocity_autocorrelation_realizations_tsv(realizations_path, autocorrelation)

    return (
        autocorrelation_path = autocorrelation_path,
        summary_path = summary_path,
        realizations_path = realizations_path,
    )
end

function write_velocity_autocorrelation_tsv(
    path::AbstractString,
    autocorrelation::MpcVelocityAutocorrelationResult,
)
    open(path, "w") do io
        println(io, "lag\ttime\tcv_raw\tcv_normalized\tsample_count\tmdc_cumulative")

        for lag in 0:autocorrelation.steps
            partial_cv = autocorrelation.cv_values[1:(lag + 1)]
            cumulative_mdc = integrate_velocity_autocorrelation(
                partial_cv,
                autocorrelation.tau,
                autocorrelation.dimension,
            )

            println(
                io,
                "$(lag)\t$(lag * autocorrelation.tau)\t$(autocorrelation.cv_values[lag + 1])\t$(autocorrelation.normalized_cv_values[lag + 1])\t$(autocorrelation.sample_counts[lag + 1])\t$(cumulative_mdc)",
            )
        end
    end
end

function write_velocity_autocorrelation_summary(
    path::AbstractString,
    autocorrelation::MpcVelocityAutocorrelationResult,
)
    open(path, "w") do io
        println(io, "velocity_autocorrelation_model=green_kubo_xy")
        println(io, "formula_cv=Cv(t)=<v(t0) dot v(t0+t)>")
        println(io, "formula_mdc=MDC=(1/d)*integral Cv(t) dt")
        println(io, "integration=discrete_trapezoidal_sum")
        println(io, "aggregation=mean_across_realizations")
        println(io, "dimension=$(autocorrelation.dimension)")
        println(io, "tau=$(autocorrelation.tau)")
        println(io, "integration_max_lag=$(autocorrelation.steps)")
        println(io, "trajectory_steps=$(autocorrelation.trajectory_steps)")
        println(io, "realizations=$(autocorrelation.realization_count)")
        println(io, "realization_seeds=$(join(autocorrelation.realization_seeds, ","))")
        println(io, "requested_labeled_particles=$(autocorrelation.requested_labeled_particles)")
        println(io, "labeled_particle_count=$(autocorrelation.labeled_particle_count)")
        println(io, "requested_initial_time_count=$(autocorrelation.requested_initial_time_count)")
        println(io, "initial_times=$(join(autocorrelation.initial_times, ","))")
        println(io, "mdc=$(autocorrelation.mdc)")
        println(io, "realization_mdc_values=$(join(autocorrelation.realization_mdc_values, ","))")
        println(io, "mdc_standard_deviation=$(standard_deviation(autocorrelation.realization_mdc_values))")
        println(io, "mdc_standard_error=$(standard_error(autocorrelation.realization_mdc_values))")
        println(io, "characteristic_time=$(optional_value(autocorrelation.characteristic_time))")
        println(io, "cv0=$(first(autocorrelation.cv_values))")
        println(io, "cv_final=$(last(autocorrelation.cv_values))")
        println(io, "cv_normalized_initial=$(first(autocorrelation.normalized_cv_values))")
        println(io, "cv_normalized_final=$(last(autocorrelation.normalized_cv_values))")
        println(io, "characteristic_time_fit=initial_contiguous_positive_decay")
    end
end

function write_velocity_autocorrelation_realizations_tsv(
    path::AbstractString,
    autocorrelation::MpcVelocityAutocorrelationResult,
)
    open(path, "w") do io
        println(io, "realization\tseed\tlabeled_particle_count\tinitial_times\tsample_count\tcv0\tcv_final\tmdc")

        for (index, seed) in enumerate(autocorrelation.realization_seeds)
            println(
                io,
                "$(index)\t$(seed)\t$(autocorrelation.labeled_particle_count)\t$(join(autocorrelation.initial_times, ","))\t$(autocorrelation.realization_sample_counts[index])\t$(autocorrelation.realization_cv0_values[index])\t$(autocorrelation.realization_cv_final_values[index])\t$(autocorrelation.realization_mdc_values[index])",
            )
        end
    end
end

function write_comparable_diffusion_metrics_outputs(
    output_dir::AbstractString,
    metrics::MpcComparableDiffusionMetrics,
)
    json_path = joinpath(output_dir, "diffusion_metrics.json")
    tsv_path = joinpath(output_dir, "diffusion_metrics.tsv")
    summary_path = joinpath(output_dir, "diffusion_metrics_summary.txt")

    write_comparable_diffusion_metrics_json(json_path, metrics)
    write_comparable_diffusion_metrics_tsv(tsv_path, metrics)
    write_comparable_diffusion_metrics_summary(summary_path, metrics)

    return (
        json_path = json_path,
        tsv_path = tsv_path,
        summary_path = summary_path,
    )
end

function write_comparable_diffusion_metrics_json(
    path::AbstractString,
    metrics::MpcComparableDiffusionMetrics,
)
    write_key_value_json(
        path,
        comparable_diffusion_metric_fields(metrics),
    )
end

function write_comparable_diffusion_metrics_tsv(
    path::AbstractString,
    metrics::MpcComparableDiffusionMetrics,
)
    fields = comparable_diffusion_metric_fields(metrics)

    open(path, "w") do io
        println(io, join(first.(fields), "\t"))
        println(io, join([tsv_value(value) for (_key, value) in fields], "\t"))
    end
end

function write_comparable_diffusion_metrics_summary(
    path::AbstractString,
    metrics::MpcComparableDiffusionMetrics,
)
    open(path, "w") do io
        println(io, "diffusion_metric_model=$(metrics.metric_model)")
        println(io, "reference_origin=$(metrics.reference_origin)")
        println(io, "purpose_note=$(metrics.purpose_note)")
        println(io, "units=$(metrics.units)")
        println(io, "aggregation=mean_across_realizations")
        println(io, "formula_mdc_star=MDC* = MDC / MDC0")
        println(io, "formula_mdc0=(kBT*tau/(2*m))*((2*n0 + 1 - exp(-n0))/(n0 - 1 + exp(-n0)))")
        println(io, "mdc=$(metrics.mdc)")
        println(io, "mdc0=$(metrics.mdc0)")
        println(io, "mdc_star=$(metrics.mdc_star)")
        println(io, "mdc_standard_deviation=$(metrics.mdc_standard_deviation)")
        println(io, "mdc_standard_error=$(metrics.mdc_standard_error)")
        println(io, "realization_mdc_values=$(join(metrics.realization_mdc_values, ","))")
        println(io, "realization_mdc_star_values=$(join(metrics.realization_mdc_star_values, ","))")
        println(io, "mdc_star_standard_deviation=$(metrics.mdc_star_standard_deviation)")
        println(io, "mdc_star_standard_error=$(metrics.mdc_star_standard_error)")
        println(io, "n0=$(metrics.n0)")
        println(io, "mass=$(metrics.mass)")
        println(io, "kbt=$(metrics.kbt)")
        println(io, "tau=$(metrics.tau)")
        println(io, "realizations=$(metrics.realizations)")
        println(io, "labeled_particle_count=$(metrics.labeled_particle_count)")
        println(io, "initial_time_count=$(metrics.initial_time_count)")
        println(io, "characteristic_time=$(optional_value(metrics.characteristic_time))")
    end
end

function write_synthetic_validation_case(
    output_dir::AbstractString,
    validation_case::SyntheticValidationCase,
)
    mkpath(output_dir)
    write_pgm_ascii(joinpath(output_dir, "input.pgm"), validation_case.image)
    write_c_reference_inputs(output_dir, validation_case.image)
    write_synthetic_validation_metadata(joinpath(output_dir, "case_metadata.tsv"), validation_case)

    return (
        pgm_path = joinpath(output_dir, "input.pgm"),
        matrix_path = joinpath(output_dir, "matrix.in"),
        size_path = joinpath(output_dir, "size.in"),
        metadata_path = joinpath(output_dir, "case_metadata.tsv"),
    )
end

function write_pgm_ascii(path::AbstractString, image::PgmImage)
    open(path, "w") do io
        println(io, "P2")
        println(io, "# Caso sintetico generado por MammographySimulation")
        println(io, "$(image.width) $(image.height)")
        println(io, "$(image.max_gray)")

        for y_index in 1:image.height
            println(io, join(vec(image.pixels[y_index, :]), " "))
        end
    end
end

function write_c_reference_inputs(output_dir::AbstractString, image::PgmImage)
    mkpath(output_dir)
    size_path = joinpath(output_dir, "size.in")
    matrix_path = joinpath(output_dir, "matrix.in")

    open(size_path, "w") do io
        println(io, "$(image.width)\t$(image.height)\t0")
    end

    open(matrix_path, "w") do io
        for y_index in 1:image.height
            for x_index in 1:image.width
                println(
                    io,
                    "$(x_index - 1)\t$(y_index - 1)\t$(image.pixels[y_index, x_index])",
                )
            end
        end
    end

    return (
        matrix_path = matrix_path,
        size_path = size_path,
    )
end

function write_synthetic_validation_metadata(
    path::AbstractString,
    validation_case::SyntheticValidationCase,
)
    open(path, "w") do io
        println(io, "field\tvalue")
        println(io, "name\t$(validation_case.name)")
        println(io, "description\t$(validation_case.description)")
        println(io, "width\t$(validation_case.image.width)")
        println(io, "height\t$(validation_case.image.height)")
        println(io, "max_gray\t$(validation_case.image.max_gray)")
        println(io, "expected_domain_cell_count\t$(validation_case.expected_domain_cell_count)")
        println(io, "expected_preliminary_blocking_obstacle_count\t$(validation_case.expected_preliminary_blocking_obstacle_count)")
        println(io, "notes\t$(validation_case.expected_notes)")
    end
end

function write_validation_cases_index(
    path::AbstractString,
    cases::Vector{SyntheticValidationCase},
)
    open(path, "w") do io
        println(
            io,
            "case\twidth\theight\texpected_domain_cell_count\texpected_preliminary_blocking_obstacle_count\tdescription\tnotes",
        )

        for validation_case in cases
            println(
                io,
                "$(validation_case.name)\t$(validation_case.image.width)\t$(validation_case.image.height)\t$(validation_case.expected_domain_cell_count)\t$(validation_case.expected_preliminary_blocking_obstacle_count)\t$(validation_case.description)\t$(validation_case.expected_notes)",
            )
        end
    end
end

function write_validation_summary_tsv(
    path::AbstractString,
    results::Vector{SyntheticValidationResult},
)
    open(path, "w") do io
        println(
            io,
            "case\tstatus\texpected_domain_cell_count\tactual_domain_cell_count\texpected_preliminary_blocking_obstacle_count\tactual_preliminary_blocking_obstacle_count\tmpc_particle_count\tconcentration_particle_sum\tparticle_conservation_ok\tmdc\tmdc0\tmdc_star\tinput_path\toutput_dir",
        )

        for result in results
            println(
                io,
                "$(result.case_name)\t$(result.status)\t$(result.expected_domain_cell_count)\t$(result.actual_domain_cell_count)\t$(result.expected_preliminary_blocking_obstacle_count)\t$(result.actual_preliminary_blocking_obstacle_count)\t$(result.mpc_particle_count)\t$(result.concentration_particle_sum)\t$(result.particle_conservation_ok)\t$(result.mdc)\t$(result.mdc0)\t$(result.mdc_star)\t$(result.input_path)\t$(result.output_dir)",
            )
        end
    end
end

function write_validation_summary_md(
    path::AbstractString,
    results::Vector{SyntheticValidationResult},
)
    open(path, "w") do io
        println(io, "# Validacion sintetica del simulador Julia")
        println(io)
        println(io, "Esta salida resume casos sinteticos no sensibles usados para validar invariantes del simulador MPC.")
        println(io)
        println(io, "| Caso | Estado | Dominio esperado/real | Obstaculos bloqueantes esperado/real | Conservacion particulas | MDC* |")
        println(io, "| --- | --- | --- | --- | --- | --- |")

        for result in results
            println(
                io,
                "| $(result.case_name) | $(result.status) | $(result.expected_domain_cell_count)/$(result.actual_domain_cell_count) | $(result.expected_preliminary_blocking_obstacle_count)/$(result.actual_preliminary_blocking_obstacle_count) | $(result.particle_conservation_ok) | $(result.mdc_star) |",
            )
        end
    end
end

function comparable_diffusion_metric_fields(metrics::MpcComparableDiffusionMetrics)
    return [
        ("status", "relative_diffusion_metrics_ready"),
        ("metric_model", metrics.metric_model),
        ("reference_origin", metrics.reference_origin),
        ("purpose_note", metrics.purpose_note),
        ("units", metrics.units),
        ("aggregation", "mean_across_realizations"),
        ("mdc", metrics.mdc),
        ("mdc0", metrics.mdc0),
        ("mdc_star", metrics.mdc_star),
        ("mdc_standard_deviation", metrics.mdc_standard_deviation),
        ("mdc_standard_error", metrics.mdc_standard_error),
        ("realization_mdc_values", metrics.realization_mdc_values),
        ("realization_mdc_star_values", metrics.realization_mdc_star_values),
        ("mdc_star_standard_deviation", metrics.mdc_star_standard_deviation),
        ("mdc_star_standard_error", metrics.mdc_star_standard_error),
        ("n0", metrics.n0),
        ("mass", metrics.mass),
        ("kbt", metrics.kbt),
        ("tau", metrics.tau),
        ("realizations", metrics.realizations),
        ("labeled_particle_count", metrics.labeled_particle_count),
        ("initial_time_count", metrics.initial_time_count),
        ("characteristic_time", metrics.characteristic_time),
    ]
end

function write_simulation_summary(
    path::AbstractString,
    run_config::SimulationRunConfig,
    space::SimulationSpace;
    mpc_initialization::Union{Nothing,MpcParticleInitialization} = nothing,
    mpc_streaming::Union{Nothing,MpcStreamingResult} = nothing,
    mpc_collision::Union{Nothing,MpcCollisionResult} = nothing,
    mpc_concentration::Union{Nothing,MpcConcentrationResult} = nothing,
    mpc_velocity_autocorrelation::Union{Nothing,MpcVelocityAutocorrelationResult} = nothing,
    mpc_diffusion_metrics::Union{Nothing,MpcComparableDiffusionMetrics} = nothing,
    simulation_box_visualization_path::Union{Nothing,String} = nothing,
    simulation_box_visualization_metadata_path::Union{Nothing,String} = nothing,
)
    free_cell_count = count_free_cells(space)

    open(path, "w") do io
        println(io, "status=mpc_results_ready")
        println(io, "steps=$(run_config.steps)")
        println(io, "seed=$(run_config.seed)")
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
        if simulation_box_visualization_path !== nothing
            println(io, "simulation_box_visualization_model=$(SIMULATION_BOX_VISUALIZATION_MODEL)")
            println(io, "simulation_box_visualization_file=$(basename(simulation_box_visualization_path))")
            println(io, "simulation_box_visualization_note=Representacion pseudo-3D del dominio mesoscopico; no es una reconstruccion anatomica 3D real.")
            println(io, "simulation_box_visualization_max_cylinders=$(SIMULATION_BOX_VISUALIZATION_MAX_CYLINDERS)")
            println(io, "simulation_box_visualization_max_particles=$(SIMULATION_BOX_VISUALIZATION_MAX_PARTICLES)")
            println(io, "simulation_box_visualization_max_columns=$(SIMULATION_BOX_VISUALIZATION_MAX_COLUMNS)")
            println(io, "simulation_box_visualization_max_rows=$(SIMULATION_BOX_VISUALIZATION_MAX_ROWS)")
            println(io, "simulation_box_visualization_max_directions=$(SIMULATION_BOX_VISUALIZATION_MAX_DIRECTIONS)")
            if simulation_box_visualization_metadata_path !== nothing
                println(io, "simulation_box_visualization_metadata_file=$(basename(simulation_box_visualization_metadata_path))")
            end
        end
        if mpc_streaming !== nothing
            println(io, "mpc_streaming_model=free_translation_periodic_boundaries_bounce_back")
            println(io, "mpc_streaming_steps=$(mpc_streaming.steps)")
            println(io, "mpc_streaming_tau=$(mpc_streaming.tau)")
            println(io, "mpc_streaming_obstacle_collision_count=$(mpc_streaming.obstacle_collision_count)")
            println(io, "mpc_streaming_domain_boundary_collision_count=$(mpc_streaming.domain_boundary_collision_count)")
            println(io, "mpc_streaming_boundary_crossing_count_x=$(mpc_streaming.boundary_crossing_count_x)")
            println(io, "mpc_streaming_boundary_crossing_count_y=$(mpc_streaming.boundary_crossing_count_y)")
        end
        if mpc_collision !== nothing
            println(io, "mpc_collision_model=multiparticle_collision_by_cell")
            println(io, "mpc_collision_seed=$(mpc_collision.seed)")
            println(io, "mpc_collision_rotation_angle=$(mpc_collision.rotation_angle)")
            println(io, "mpc_collision_active_cell_count=$(mpc_collision.active_cell_count)")
            println(io, "mpc_collision_cell_count=$(mpc_collision.collision_cell_count)")
            println(io, "mpc_collision_singleton_cell_count=$(mpc_collision.singleton_cell_count)")
            println(io, "mpc_collision_particle_count=$(mpc_collision.particle_count)")
            println(io, "mpc_collision_max_particles_per_cell=$(mpc_collision.max_particles_per_cell)")
        end
        if mpc_concentration !== nothing
            println(io, "mpc_concentration_model=particles_per_cell_snapshot")
            println(io, "mpc_concentration_aggregation=mean_across_realizations")
            println(io, "mpc_concentration_realizations=$(mpc_concentration.realization_count)")
            println(io, "mpc_concentration_realization_seeds=$(join(mpc_concentration.realization_seeds, ","))")
            println(io, "mpc_concentration_requested_output_times=$(join(mpc_concentration.requested_output_times, ","))")
            println(io, "mpc_concentration_captured_output_times=$(join(mpc_concentration.captured_output_times, ","))")
            println(io, "mpc_concentration_expected_density_n0=$(mpc_concentration.expected_density)")
            println(io, "mpc_concentration_high_threshold=$(mpc_concentration.high_concentration_threshold)")
            println(io, "mpc_concentration_particle_count=$(mpc_concentration.particle_count)")
            println(io, "mpc_concentration_snapshot_count=$(length(mpc_concentration.snapshots))")
            println(io, "mpc_concentration_representative_realization_index=$(mpc_concentration.representative_realization_index)")
            println(io, "mpc_concentration_representative_seed=$(mpc_concentration.representative_seed)")
            println(io, "mpc_concentration_visual_scale_max=$(mpc_concentration.high_concentration_threshold)")
        end
        if mpc_velocity_autocorrelation !== nothing
            println(io, "velocity_autocorrelation_model=green_kubo_xy")
            println(io, "velocity_autocorrelation_aggregation=mean_across_realizations")
            println(io, "velocity_autocorrelation_dimension=$(mpc_velocity_autocorrelation.dimension)")
            println(io, "velocity_autocorrelation_max_lag=$(mpc_velocity_autocorrelation.steps)")
            println(io, "velocity_autocorrelation_trajectory_steps=$(mpc_velocity_autocorrelation.trajectory_steps)")
            println(io, "velocity_autocorrelation_realizations=$(mpc_velocity_autocorrelation.realization_count)")
            println(io, "velocity_autocorrelation_requested_labeled_particles=$(mpc_velocity_autocorrelation.requested_labeled_particles)")
            println(io, "velocity_autocorrelation_labeled_particle_count=$(mpc_velocity_autocorrelation.labeled_particle_count)")
            println(io, "velocity_autocorrelation_requested_initial_time_count=$(mpc_velocity_autocorrelation.requested_initial_time_count)")
            println(io, "velocity_autocorrelation_initial_times=$(join(mpc_velocity_autocorrelation.initial_times, ","))")
            println(io, "velocity_autocorrelation_mdc=$(mpc_velocity_autocorrelation.mdc)")
            println(io, "velocity_autocorrelation_realization_mdc_values=$(join(mpc_velocity_autocorrelation.realization_mdc_values, ","))")
            println(io, "velocity_autocorrelation_mdc_standard_deviation=$(standard_deviation(mpc_velocity_autocorrelation.realization_mdc_values))")
            println(io, "velocity_autocorrelation_mdc_standard_error=$(standard_error(mpc_velocity_autocorrelation.realization_mdc_values))")
            println(io, "velocity_autocorrelation_characteristic_time=$(optional_value(mpc_velocity_autocorrelation.characteristic_time))")
        end
        if mpc_diffusion_metrics !== nothing
            println(io, "diffusion_metric_model=$(mpc_diffusion_metrics.metric_model)")
            println(io, "diffusion_metric_reference_origin=$(mpc_diffusion_metrics.reference_origin)")
            println(io, "diffusion_metric_units=$(mpc_diffusion_metrics.units)")
            println(io, "diffusion_metric_mdc=$(mpc_diffusion_metrics.mdc)")
            println(io, "diffusion_metric_mdc0=$(mpc_diffusion_metrics.mdc0)")
            println(io, "diffusion_metric_mdc_star=$(mpc_diffusion_metrics.mdc_star)")
            println(io, "diffusion_metric_mdc_standard_deviation=$(mpc_diffusion_metrics.mdc_standard_deviation)")
            println(io, "diffusion_metric_mdc_standard_error=$(mpc_diffusion_metrics.mdc_standard_error)")
            println(io, "diffusion_metric_mdc_star_standard_deviation=$(mpc_diffusion_metrics.mdc_star_standard_deviation)")
            println(io, "diffusion_metric_mdc_star_standard_error=$(mpc_diffusion_metrics.mdc_star_standard_error)")
            println(io, "diffusion_metric_purpose_note=$(mpc_diffusion_metrics.purpose_note)")
        end
        println(io, "free_cell_count=$(free_cell_count)")
        println(io, "configuration_model=$(MPC_CONFIGURATION_MODEL)")
        println(io, "execution_engine=$(SIMULATION_ENGINE_MPC)")
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

function optional_value(value::Nothing)
    return ""
end

function optional_value(value)
    return value
end

function compact_numeric_value(value::Real)
    numeric_value = Float64(value)

    if isfinite(numeric_value) && isinteger(numeric_value)
        return string(round(Int, numeric_value))
    end

    return string(value)
end

function tsv_value(value::Nothing)
    return ""
end

function tsv_value(value)
    return string(value)
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

function json_value(value::Nothing)
    return "null"
end

function json_value(value::AbstractVector{<:Integer})
    return "[" * join(string.(value), ", ") * "]"
end

function json_value(value::AbstractVector{<:AbstractFloat})
    return "[" * join([json_value(item) for item in value], ", ") * "]"
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
