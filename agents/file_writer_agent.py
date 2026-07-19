import os
from datetime import datetime

from utils.file_writer import save_generated_project
from utils.logger import add_log
from utils.zipper import create_project_zip
from utils.live_status import add_live_log


def file_writer_agent(state):

    add_log("📂 Writing generated files...")
    add_live_log("📂 File Writer Agent writing files...")

    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")

    project_path = os.path.join(
        "generated_projects",
        f"project_{timestamp}"
    )

    os.makedirs(project_path, exist_ok=True)

    generated_code = state.get(
        "reviewed_code",
        state.get("generated_code", "")
    )

    save_generated_project(
        generated_code,
        project_path
    )

    zip_path = create_project_zip(project_path)

    add_live_log("📂 File Writer Agent completed")
    add_log("✅ Files written successfully")

    return {
        "project_path": project_path,
        "zip_path": zip_path
    }
