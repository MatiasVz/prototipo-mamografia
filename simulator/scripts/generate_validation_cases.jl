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
    joinpath("storage", "validation", "synthetic_cases"),
)

cases = MammographySimulation.generate_synthetic_validation_cases(output_dir)

println("Casos sinteticos generados correctamente.")
println("output_dir=$(abspath(output_dir))")
println("case_count=$(length(cases))")

for validation_case in cases
    println("case=$(validation_case.name)")
end
