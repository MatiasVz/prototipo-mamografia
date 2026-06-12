#!/usr/bin/env julia

using MammographySimulation

function option_value(args, name, default)
    index = findfirst(==(name), args)

    if index === nothing
        return default
    end

    if index == length(args)
        error("La opcion $(name) requiere un valor.")
    end

    return args[index + 1]
end

output_dir = option_value(
    ARGS,
    "--output",
    joinpath("storage", "validation", "synthetic_report"),
)
seed = parse(Int, option_value(ARGS, "--seed", "1234"))
steps = parse(Int, option_value(ARGS, "--steps", "5"))

results = MammographySimulation.validate_synthetic_cases(
    output_dir;
    seed = seed,
    steps = steps,
)

println("Validacion sintetica ejecutada correctamente.")
println("output_dir=$(abspath(output_dir))")
println("case_count=$(length(results))")
println("summary_path=$(abspath(joinpath(output_dir, "validation_summary.tsv")))")

for result in results
    println("case=$(result.case_name) status=$(result.status)")
end
