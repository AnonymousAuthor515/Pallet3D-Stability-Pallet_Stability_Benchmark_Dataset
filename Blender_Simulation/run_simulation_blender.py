import pathlib
import subprocess
import gc
import os
from tqdm import tqdm

#The Template file contains the pre configuration of the blender environment
TEMPLATEFILE = pathlib.Path(__file__).parent.resolve() / "template.blend"

#The file that is used by blender to initialize and conduct the simulation.
SCENEGENFILE = pathlib.Path(__file__).parent.resolve() / "scene_creation_blender.py"

#Path to the installed Blender instance
BLENDERPATH = "C:/Program Files/Blender Foundation/Blender 4.5/blender.exe"
if not BLENDERPATH or not pathlib.Path(BLENDERPATH).exists():
    raise FileNotFoundError(f"Blender not found at: {BLENDERPATH}. Check installation / PATH.")


def run_blender_simulation(input_output_dir: pathlib.Path, mode: int = 2) -> None:
    """
    This method iterates through all json files in the input_output_dir and opens a blender instance without gui. 
    The opened blender instance will call the scene_creation.py file which will create a simulation for the pallet layout in the json file. 
    The results of the simulation are written into the json file after the simulation ends. 
    """

    for file_path in tqdm(sorted(input_output_dir.iterdir()), desc="Running test"):
        if not file_path.is_file():
            continue
        
        cmd = [
            BLENDERPATH,
            "-b", # headless
            str(TEMPLATEFILE),
            "--python",
            str(SCENEGENFILE),
            "--",
            "packing_plan_file",
            str(file_path),
            "mode",
            str(mode),
        ]

        subprocess.run(cmd, check=True)

        gc.collect()
        

def run_blender_watchable_simulation(file_path: pathlib.Path, mode: int = 2) -> None:
    """
    This method opens a blender instance with gui for a single file. 
    The opened blender instance will call the scene_creation.py file which will create a simulation for the pallet layout in the json file. 
    The results of the simulation are written into the json file after the simulation ends. 
    """

    cmd = [
        BLENDERPATH,
        str(TEMPLATEFILE),
        "--python",
        str(SCENEGENFILE),
        "--",
        "packing_plan_file",
        str(file_path),
        "mode",
        str(mode),
    ]

    subprocess.run(cmd, shell=False)

    gc.collect()


if __name__ == "__main__":
    """
    This file executes the blender simulations of pallet layouts to determine stability. 
    An installed Blender instance is a Prerequisite for this file to work properly.  
    The simulation encompases 2 modes: 
        Mode 1 is the basic simulation. 
        Mode 2 uses rounded off edges to achieve higher accuracy compared to the MSC Adams simulations
    Mode can be adjusted in the run_.. methods. 
    Per simulated pallet layout a runtime of around 10-15 seconds is to be expected for the configurations applied in scene_creation_blender.py
    """

    input_output_dir = pathlib.Path(__file__).parent.parent / "Pallet_Generation" / "Jsons" / "Pallets" 
    run_blender_simulation(input_output_dir, 2)

    #input_output_file = pathlib.Path(__file__).parent.parent / "Pallet_Generation" / "Jsons" / "Pallets" / "0.json"
    #run_blender_watchable_simulation(input_output_file, 2)
