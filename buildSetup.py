from cx_Freeze import setup

# This seems to be broken?
# build_exe_options = {
#     "include_files": [
#         "addresses.json"
#     ]
# }

name = "RoadTripAdventure-InventoryEditor"
version = "0.1.0"

setup(
    name=name,
    version=version,
    description="Live inventory editor for Road Trip Adventure, with additional functionality for manual Archipelago randomizer.",
    # options={"build_exe": build_exe_options},
    executables=[{"script": "main.py", "base": "console", "target_name": f"{name}-{version}"}],
)
