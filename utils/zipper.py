import shutil
import os


def create_project_zip(project_path):

    zip_path = project_path.rstrip("/\\") + ".zip"

    if os.path.exists(zip_path):
        os.remove(zip_path)

    shutil.make_archive(
        project_path,
        "zip",
        project_path
    )

    return zip_path