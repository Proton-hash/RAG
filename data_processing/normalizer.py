import json
from pathlib import Path

def load_all_jsons_from_dir(directory: Path) -> list:
    """Combine all lists from JSON files in a directory into one flat list."""
    result = []
    for json_file in sorted(directory.glob("*.json")):
        try:
            with open(json_file, "r", encoding="utf-8") as f:
                data = json.load(f)
                if isinstance(data, list):
                    result.extend(data)
                else:
                    result.append(data)
        except Exception as e:
            print(f"Error reading {json_file}: {e}")
    return result

def load_all_jsons_from_folder(folder: Path) -> list:
    """Combine all lists from JSON files in a given folder into one flat list."""
    combined = []
    for json_file in sorted(folder.glob("*.json")):
        try:
            with open(json_file, "r", encoding="utf-8") as f:
                data = json.load(f)
                if isinstance(data, list):
                    combined.extend(data)
                else:
                    combined.append(data)
        except Exception as e:
            print(f"Error reading {json_file}: {e}")
    return combined

def normalize_projects_and_commits():
    projects_dir = Path("data/raw/projects")
    commits_dir = Path("data/raw/commits")
    # Combine all projects
    projects_list = load_all_jsons_from_dir(projects_dir)
    for project in projects_list:
        name = project.get("name")
        owner = project.get("owner", {})
        login = owner.get("login")
        if not name or not login:
            continue  # skip malformed records
        folder_name = f"{login}__{name}"
        commit_folder = commits_dir / folder_name
        if commit_folder.exists() and commit_folder.is_dir():
            commits = load_all_jsons_from_folder(commit_folder)
            project["commits"] = commits
        else:
            project["commits"] = []
    return projects_list
