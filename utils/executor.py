import subprocess
import os
import sys

# Import the pre-run patcher
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from utils.pre_run_patcher import pre_run_patch


def install_requirements(project_path):

    for root, dirs, files in os.walk(project_path):

        if "requirements.txt" in files:

            requirements_path = os.path.join(root, "requirements.txt")

            print(f"\nInstalling dependencies from: {requirements_path}\n")

            cleaned_requirements = []

            with open(requirements_path, "r", encoding="utf-8") as f:
                lines = f.readlines()
                
            invalid_packages = {
                "sqlite",
                "sqlite3"
                }
            
            for line in lines:
                
                package = line.strip()

                # Skip empty lines
                if not package:
                    continue

                # Remove AI formatting
                if package.startswith("FILE:"):
                    continue

                if package.startswith("CODE:"):
                    continue

                if package == "<CODE>":
                    continue

                if package == "</CODE>":
                    continue

                if package.startswith("```"):
                    continue

                # Skip comments
                if package.startswith("#"):
                    continue

                # Skip invalid packages
                if package.lower() in invalid_packages:
                    continue

                cleaned_requirements.append(package)

            # ✅ Always ensure pydantic-settings is installed (Pydantic v2 requirement)
            if "pydantic-settings" not in cleaned_requirements:
                cleaned_requirements.append("pydantic-settings")

            temp_requirements = os.path.join(root, "temp_requirements.txt")

            with open(temp_requirements, "w") as f:
                f.write("\n".join(cleaned_requirements))

            # ✅ Use sys.executable so pip runs inside the venv
            subprocess.run(
                [sys.executable, "-m", "pip", "install", "-r", temp_requirements],
                check=False
            )

            return


def find_entry_file(project_path):

    possible_paths = [
        "main.py",
        "app/main.py",
        "src/main.py",
        "project/app/main.py"
    ]

    for path in possible_paths:

        full_path = os.path.join(project_path, path)

        if os.path.exists(full_path):
            return full_path

    # fallback recursive search
    for root, dirs, files in os.walk(project_path):

        if "main.py" in files:
            return os.path.join(root, "main.py")

    return None


def run_project(project_path):

    install_requirements(project_path)

    # ✅ NEW: Patch common LLM codegen issues before running
    pre_run_patch(project_path)

    entry_file = find_entry_file(project_path)

    if not entry_file:

        return {
            "success": False,
            "stdout": "",
            "stderr": "No valid entry file found."
        }

    try:

        working_dir = os.path.dirname(entry_file)

        print(f"\nRunning from: {working_dir}\n")

        # ✅ Use sys.executable so project runs inside the venv
        result = subprocess.run(
            [sys.executable, os.path.basename(entry_file)],
            cwd=working_dir,
            capture_output=True,
            text=True,
            timeout=15
        )

        return {
            "success": result.returncode == 0,
            "stdout": result.stdout,
            "stderr": result.stderr
        }

    except Exception as e:

        return {
            "success": False,
            "stdout": "",
            "stderr": str(e)
        }