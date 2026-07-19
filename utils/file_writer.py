import os
import re


def save_generated_project(generated_code, output_dir):

    os.makedirs(output_dir, exist_ok=True)

    # Split on FILE:
    sections = re.split(
        r"FILE:\s*",
        generated_code
    )

    created_files = set()

    for section in sections:

        section = section.strip()

        if not section:
            continue

        lines = section.splitlines()

        if not lines:
            continue

        file_path = lines[0].strip()

        code = "\n".join(lines[1:]).strip()

        # Remove code wrappers
        code = code.replace("<CODE>", "")
        code = code.replace("</CODE>", "")
        code = code.replace("```python", "")
        code = code.replace("```", "")
        code = code.strip()

        full_path = os.path.join(
            output_dir,
            file_path
        )

        os.makedirs(
            os.path.dirname(full_path),
            exist_ok=True
        )

        if full_path in created_files:

            with open(
                full_path,
                "a",
                encoding="utf-8"
            ) as f:
                f.write("\n\n")
                f.write(code)

            print(f"🔄 Merged: {file_path}")

        else:

            with open(
                full_path,
                "w",
                encoding="utf-8"
            ) as f:
                f.write(code)

            created_files.add(full_path)

            print(f"✅ Created: {file_path}")

    print(
        f"\n✅ Project written successfully! "
        f"({len(created_files)} files)"
    )