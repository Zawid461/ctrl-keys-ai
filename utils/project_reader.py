import os


def get_project_files(project_path):

    all_files = []

    for root, dirs, files in os.walk(project_path):

        for file in files:

            full_path = os.path.join(root, file)

            relative_path = os.path.relpath(
                full_path,
                project_path
            )

            all_files.append(relative_path)

    return sorted(all_files)


def read_project_file(project_path, file_path):

    full_path = os.path.join(project_path, file_path)

    try:
        with open(full_path, "r", encoding="utf-8") as f:
            return f.read()

    except Exception as e:
        return str(e)