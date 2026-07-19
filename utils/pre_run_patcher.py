import os
import re
import sys
import subprocess


# ─────────────────────────────────────────────
# Packages FastAPI silently needs but LLMs forget
# ─────────────────────────────────────────────
IMPLICIT_PACKAGES = [
    "python-multipart",
    "pydantic-settings",
    "python-jose",
    "passlib",
    "bcrypt",
]


# ─────────────────────────────────────────────
# Invalid requirements AI hallucinations
# ─────────────────────────────────────────────
INVALID_REQUIREMENTS = [
    "sqlite",
    "sqlite3",
    "os",
    "sys",
    "re",
    "json",
]


# ─────────────────────────────────────────────
# Safe default settings
# ─────────────────────────────────────────────
DEFAULT_SETTINGS = {
    "DATABASE_URL": "sqlite:///./database.db",
    "SECRET_KEY": "supersecretkey123",
    "ALGORITHM": "HS256",
    "ACCESS_TOKEN_EXPIRE_MINUTES": 30,
    "API_KEY": "default_api_key",
    "DEBUG": True,
}


# ─────────────────────────────────────────────
# settings.py template
# ─────────────────────────────────────────────
SETTINGS_TEMPLATE = '''
from pydantic_settings import BaseSettings

class Settings(BaseSettings):

    DATABASE_URL: str = "{DATABASE_URL}"
    SECRET_KEY: str = "{SECRET_KEY}"
    ALGORITHM: str = "{ALGORITHM}"
    ACCESS_TOKEN_EXPIRE_MINUTES: int = {ACCESS_TOKEN_EXPIRE_MINUTES}
    API_KEY: str = "{API_KEY}"
    DEBUG: bool = {DEBUG}

    class Config:
        env_file = ".env"

settings = Settings()
'''.strip()


# ─────────────────────────────────────────────
# .env template
# ─────────────────────────────────────────────
ENV_TEMPLATE = '''
DATABASE_URL={DATABASE_URL}
SECRET_KEY={SECRET_KEY}
ALGORITHM={ALGORITHM}
ACCESS_TOKEN_EXPIRE_MINUTES={ACCESS_TOKEN_EXPIRE_MINUTES}
API_KEY={API_KEY}
DEBUG={DEBUG}
'''.strip()


# ─────────────────────────────────────────────
# Install missing hidden dependencies
# ─────────────────────────────────────────────
def install_implicit_packages():

    print("  📦 Ensuring implicit dependencies are installed...")

    subprocess.run(
        [
            sys.executable,
            "-m",
            "pip",
            "install",
            "--quiet",
            *IMPLICIT_PACKAGES
        ],
        check=False
    )

    print("  ✅ Implicit packages ready")


# ─────────────────────────────────────────────
# Clean broken requirements.txt
# ─────────────────────────────────────────────
def clean_requirements(project_path: str):

    req_path = os.path.join(project_path, "requirements.txt")

    if not os.path.exists(req_path):
        return

    with open(req_path, "r", encoding="utf-8") as f:
        lines = f.readlines()

    cleaned = []

    for line in lines:

        package = line.strip()

        if package and package not in INVALID_REQUIREMENTS:
            cleaned.append(package)

    with open(req_path, "w", encoding="utf-8") as f:
        f.write("\n".join(cleaned))

    print("  ✅ Cleaned requirements.txt")


# ─────────────────────────────────────────────
# Fix settings.py
# ─────────────────────────────────────────────
def fix_settings_file(project_path: str):

    config_dir = os.path.join(project_path, "config")

    settings_path = os.path.join(config_dir, "settings.py")

    init_path = os.path.join(config_dir, "__init__.py")

    os.makedirs(config_dir, exist_ok=True)

    needs_rewrite = False

    if not os.path.exists(settings_path):

        print("  ⚠️ config/settings.py missing")

        needs_rewrite = True

    else:

        with open(settings_path, "r", encoding="utf-8") as f:
            content = f.read()

        missing = [
            key
            for key in DEFAULT_SETTINGS
            if key not in content
        ]

        if missing:

            print(f"  ⚠️ Missing settings fields: {missing}")

            needs_rewrite = True

    if needs_rewrite:

        new_content = SETTINGS_TEMPLATE.format(
            **{
                k: str(v)
                for k, v in DEFAULT_SETTINGS.items()
            }
        )

        with open(settings_path, "w", encoding="utf-8") as f:
            f.write(new_content)

        print("  ✅ settings.py regenerated")

    if not os.path.exists(init_path):

        with open(init_path, "w", encoding="utf-8") as f:
            f.write("from config.settings import settings\n")

        print("  ✅ config/__init__.py created")


# ─────────────────────────────────────────────
# Fix .env
# ─────────────────────────────────────────────
def fix_env_file(project_path: str):

    env_path = os.path.join(project_path, ".env")

    if not os.path.exists(env_path):

        content = ENV_TEMPLATE.format(
            **{
                k: str(v)
                for k, v in DEFAULT_SETTINGS.items()
            }
        )

        with open(env_path, "w", encoding="utf-8") as f:
            f.write(content)

        print("  ✅ .env created")

        return

    with open(env_path, "r", encoding="utf-8") as f:
        existing = f.read()

    missing = []

    for key, value in DEFAULT_SETTINGS.items():

        if key not in existing:
            missing.append(f"{key}={value}")

    if missing:

        with open(env_path, "a", encoding="utf-8") as f:
            f.write("\n" + "\n".join(missing))

        print("  ✅ .env patched")


# ─────────────────────────────────────────────
# Create missing __init__.py files
# ─────────────────────────────────────────────
def fix_missing_init_files(project_path: str):

    skip_dirs = {
        ".git",
        "__pycache__",
        "venv",
        ".venv",
        "node_modules"
    }

    for root, dirs, files in os.walk(project_path):

        dirs[:] = [
            d for d in dirs
            if d not in skip_dirs
        ]

        has_python = any(
            f.endswith(".py")
            for f in files
        )

        if has_python:

            init_path = os.path.join(root, "__init__.py")

            if not os.path.exists(init_path):

                with open(init_path, "w", encoding="utf-8") as f:
                    f.write("")

                rel = os.path.relpath(init_path, project_path)

                print(f"  ✅ Created {rel}")


# ─────────────────────────────────────────────
# Fix Pydantic v2 + SQLAlchemy imports
# ─────────────────────────────────────────────
def fix_pydantic_settings_import(project_path: str):

    for root, dirs, files in os.walk(project_path):

        for filename in files:

            if not filename.endswith(".py"):
                continue

            filepath = os.path.join(root, filename)

            with open(filepath, "r", encoding="utf-8") as f:
                content = f.read()

            new_content = content.replace(
                "from pydantic import BaseSettings",
                "from pydantic_settings import BaseSettings"
            )

            new_content = new_content.replace(
                "from sqlalchemy.ext.declarative import declarative_base",
                "from sqlalchemy.orm import declarative_base"
            )

            if new_content != content:

                with open(filepath, "w", encoding="utf-8") as f:
                    f.write(new_content)

                rel = os.path.relpath(filepath, project_path)

                print(f"  ✅ Patched imports in {rel}")


# ─────────────────────────────────────────────
# Fix recursive get_db imports
# ─────────────────────────────────────────────
def fix_recursive_get_db_imports(project_path: str):

    for root, dirs, files in os.walk(project_path):

        for file in files:

            if file.endswith(".py"):

                path = os.path.join(root, file)

                with open(path, "r", encoding="utf-8") as f:
                    content = f.read()

                original = content

                bad_imports = [
                    "from . import get_db",
                    "from utils import get_db",
                ]

                for bad in bad_imports:
                    content = content.replace(bad, "")

                if content != original:

                    with open(path, "w", encoding="utf-8") as f:
                        f.write(content)

                    print(f"  ✅ Fixed recursive imports in {file}")


# ─────────────────────────────────────────────
# Remove markdown fences
# ─────────────────────────────────────────────
def remove_markdown_fences(project_path: str):

    pattern = r"```(?:python)?(.*?)```"

    for root, dirs, files in os.walk(project_path):

        for file in files:

            if file.endswith(".py"):

                path = os.path.join(root, file)

                with open(path, "r", encoding="utf-8") as f:
                    content = f.read()

                cleaned = re.sub(
                    pattern,
                    r"\1",
                    content,
                    flags=re.DOTALL
                )

                if cleaned != content:

                    with open(path, "w", encoding="utf-8") as f:
                        f.write(cleaned)

                    print(f"  ✅ Removed markdown fences in {file}")


# ─────────────────────────────────────────────
# Remove duplicate imports
# ─────────────────────────────────────────────
def remove_duplicate_imports(project_path: str):

    for root, dirs, files in os.walk(project_path):

        for file in files:

            if not file.endswith(".py"):
                continue

            path = os.path.join(root, file)

            with open(path, "r", encoding="utf-8") as f:
                lines = f.readlines()

            seen = set()

            cleaned = []

            for line in lines:

                stripped = line.strip()

                if stripped.startswith("import ") or stripped.startswith("from "):

                    if stripped in seen:
                        continue

                    seen.add(stripped)

                cleaned.append(line)

            with open(path, "w", encoding="utf-8") as f:
                f.writelines(cleaned)

    print("  ✅ Removed duplicate imports")


# ─────────────────────────────────────────────
# Remove duplicate comments
# ─────────────────────────────────────────────
def remove_duplicate_comments(project_path: str):

    for root, dirs, files in os.walk(project_path):

        for file in files:

            if file.endswith(".py"):

                path = os.path.join(root, file)

                with open(path, "r", encoding="utf-8") as f:
                    content = f.read()

                content = re.sub(
                    r"(# Removed duplicate.*\n)+",
                    "# Removed duplicate imports\n",
                    content
                )

                with open(path, "w", encoding="utf-8") as f:
                    f.write(content)

    print("  ✅ Removed duplicate comments")


# ─────────────────────────────────────────────
# Fix empty python files
# ─────────────────────────────────────────────
def fix_empty_python_files(project_path: str):

    for root, dirs, files in os.walk(project_path):

        for file in files:

            if file.endswith(".py"):

                path = os.path.join(root, file)

                if os.path.getsize(path) == 0:

                    with open(path, "w", encoding="utf-8") as f:
                        f.write("# Auto-generated placeholder\n")

                    print(f"  ✅ Fixed empty file: {file}")


# ─────────────────────────────────────────────
# Validate Python syntax
# ─────────────────────────────────────────────
def validate_python_syntax(project_path: str):

    print("  🔍 Validating Python syntax...")

    for root, dirs, files in os.walk(project_path):

        for file in files:

            if file.endswith(".py"):

                path = os.path.join(root, file)

                result = subprocess.run(
                    [sys.executable, "-m", "py_compile", path],
                    capture_output=True,
                    text=True
                )

                if result.returncode != 0:

                    print(f"  ❌ Syntax error in {file}")
                    print(result.stderr)

                else:

                    print(f"  ✅ {file}")


def remove_code_tags(project_path):

    print("  🧹 Removing raw <CODE> tags...")

    for root, dirs, files in os.walk(project_path):

        for filename in files:

            if not filename.endswith(".py"):
                continue

            filepath = os.path.join(root, filename)

            with open(filepath, "r", encoding="utf-8") as f:
                content = f.read()

            cleaned = (
                content
                .replace("<CODE>", "")
                .replace("</CODE>", "")
            )

            if cleaned != content:

                with open(filepath, "w", encoding="utf-8") as f:
                    f.write(cleaned)

                rel = os.path.relpath(filepath, project_path)

                print(f"  ✅ Cleaned CODE tags: {rel}")

RESERVED_MODULE_NAMES = [
    "pydantic_settings.py",
    "fastapi.py",
    "sqlalchemy.py",
    "jwt.py",
    "bcrypt.py",
]

RESERVED_MODULE_FILES = [
    "pydantic_settings.py",
    "fastapi.py",
    "sqlalchemy.py",
    "jwt.py",
    "bcrypt.py",
]

def remove_fake_library_files(project_path: str):

    print("  🛡️ Removing fake library shadow files...")

    for root, dirs, files in os.walk(project_path):

        for file in files:

            if file in RESERVED_MODULE_FILES:

                # ONLY remove root-level shadow files
                if os.path.abspath(root) != os.path.abspath(project_path):
                    continue

                file_path = os.path.join(root, file)

                try:

                    os.remove(file_path)

                    print(f"  ✅ Removed fake library file: {file}")

                except Exception as e:

                    print(f"  ❌ Failed removing {file}: {e}")

# ─────────────────────────────────────────────
# MASTER PATCHER
# ─────────────────────────────────────────────
def pre_run_patch(project_path: str):

    print("\n🔧 Running pre-execution patcher...\n")

    install_implicit_packages()

    clean_requirements(project_path)

    remove_code_tags(project_path)

    remove_fake_library_files(project_path)

    fix_settings_file(project_path)

    fix_env_file(project_path)

    fix_missing_init_files(project_path)

    fix_pydantic_settings_import(project_path)

    fix_recursive_get_db_imports(project_path)

    remove_markdown_fences(project_path)

    remove_duplicate_imports(project_path)

    remove_duplicate_comments(project_path)

    fix_empty_python_files(project_path)

    validate_python_syntax(project_path)

    print("\n✅ Pre-execution patch complete.\n")