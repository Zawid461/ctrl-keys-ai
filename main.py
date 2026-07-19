from core.graph import graph

user_input = input("Enter your project idea: ")

result = graph.invoke({
    "user_input": user_input
})

# DEBUG STATE
print("\n========== STATE KEYS ==========\n")
print(result.keys())

print("\n========== FINAL CODE ==========\n")

print(
    result.get(
        "debugged_code",
        result.get(
            "reviewed_code",
            result.get(
                "generated_code",
                "No generated code found"
            )
        )
    )
)

print("\n========== EXECUTION OUTPUT ==========\n")

print(
    result.get(
        "execution_output",
        "No execution output"
    )
)

print("\n========== EXECUTION ERRORS ==========\n")

print(
    result.get(
        "execution_error",
        "No execution errors"
    )
)