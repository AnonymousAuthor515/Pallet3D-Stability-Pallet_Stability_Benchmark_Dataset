import subprocess
import pathlib
import gc
import os
from multiprocessing import Pool

# Point this to your Adams 2025.2 install root (the folder that contains mdi/, linux64/, appbar/, etc.)
INSTALL_DIR = pathlib.Path("~/Adams").expanduser()

# Your working directory (same idea as before)
WORK = pathlib.Path("~/Blender_Simulation/Adams_Simulation/").expanduser()

#The file that is used by blender to initialize and conduct the simulation.
SCENEGENFILE = pathlib.Path(__file__).parent.resolve() / "scene_creation_adams.py"


def run_adams_simulation(input_output_dir: pathlib.Path) -> None:
    """
    Loads all files from the input_ouptu_dir and starts a Pool where 10 simulatons at once get performed. 
    Requires enough Adams License tokens to work. If not available change parallization amount. 
    """

    directorylist = []

    for file_path in input_output_dir.iterdir(): 
        if not file_path.is_file():
            continue

        directorylist.append(file_path)

    with Pool(10) as pool:
        pool.imap_unordered(process_file, directorylist)


def process_file(input_ouput_file): 
    """
    Opens an MSC Adams instance and provides the rum_simulation_adams.py file that gets called by Adams to create a simulation of the pallet layout provided in the json_file.
    """

    mdi = INSTALL_DIR / "mdi"
    if not mdi.exists():
        raise FileNotFoundError(f"Could not find mdi at: {mdi}")
    
    cmd = [
        str(mdi),
        "-c",
        "aview",
        "ru-s",
        "b",
        str(SCENEGENFILE),
        "exit",
    ]

    # Environment: make sure Adams libs resolve and Qt does not try to use X11
    env = os.environ.copy()
    env["INSTALL_DIR"] = str(INSTALL_DIR)
    env["ADAMS_INPUT_JSON"] = input_ouput_file
    env["MSC_ADAMS_NUM_THREADS"] = "1"
    env["OMP_NUM_THREADS"] = "1"
    # --- Critical: Adams + SCA_Kernel runtime libs on loader path ---
    adams_lib_dirs = [
        INSTALL_DIR / "linux64",
        INSTALL_DIR / "aview" / "linux64",
        INSTALL_DIR / "appbar" / "linux64",
        INSTALL_DIR / "richclient" / "SCA_Kernel" / "LX8664" / "lib",
    ]

    existing = env.get("LD_LIBRARY_PATH", "")
    env["LD_LIBRARY_PATH"] = ":".join([str(p) for p in adams_lib_dirs] + ([existing] if existing else []))
    env["MSC_LICENSE_FILE"] = "27500@uservm"
    env["LM_LICENSE_FILE"]  = "27500@uservm"

    # Headless Qt: do NOT require DISPLAY / X server
    env["QT_QPA_PLATFORM"] = env.get("QT_QPA_PLATFORM", "offscreen")
    env.pop("DISPLAY", None)

    try:

        res = subprocess.run(
            cmd,
            cwd=str(WORK),
            env=env,
            text=True,
            capture_output=True,
            shell=False,
        )

        print("Return code:", res.returncode)
        print("STDOUT:\n", res.stdout)
        print("STDERR:\n", res.stderr)

        gc.collect()
         
        if res.returncode != 0:
            raise SystemExit("Adams batch run failed – see STDOUT/STDERR.")

        return res.returncode
    except Exception as e: 
        print(f"[PID {os.getpid()}] FAIL {input_ouput_file}: {e}", flush=True)
        return 


if __name__ == "__main__":
    """
    MSC Adams paths are configured for use on Linux. 
    Proper performance is not guaranteed under Windows.
    This file executes the MSC Adams simulations of pallet layouts to determine stability. 
    An installed MSC Adams version 2025_2 instance is a Prerequisite for this file to work properly.  
    Per simulated pallet layout a runtime of around 30 min - 1,5 h is to be expected for the configurations applied in scene_creation_adams.py
    """

    input_output_dir = pathlib.Path(__file__).parent.parent / "Pallet_Generation" / "Jsons" / "Pallets" 
    run_adams_simulation(input_output_dir)

    #input_output_file = pathlib.Path(__file__).parent.parent / "Pallet_Generation" / "Jsons" / "Pallets" / "0.json"
    #run_blender_watchable_simulation(input_output_file, 2)
