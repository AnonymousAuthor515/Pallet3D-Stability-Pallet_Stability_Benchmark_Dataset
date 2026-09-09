import json
import os
import gc
import logging
import math
import pathlib
import Adams
import importlib.util as iu
import statistics as stats
from itertools import combinations
from typing import List
from datetime import datetime
try:
    import readline
except ImportError:
    pass


#import Adams  # may exist in your Adams Python environment
# ----------------------------
# Config (mm-kg-s)
# ----------------------------

T_END = 5.0
DT_OUT = 50 

GROUND_X = 1200.0
GROUND_Y = 800.0
GROUND_THICK = 20.0 

# Friction 
FRIC_ITEM_ITEM = dict(mu_s=0.45, mu_d=0.35, vs=0.2, vd=2.0)  # carton-carton
FRIC_ITEM_GND  = dict(mu_s=0.35, mu_d=0.25, vs=0.2, vd=2.0)  # carton-wood
# Contact normal law 
CONTACT_NORMAL = dict(stiffness=1.2e3, damping=3.9, exponent=2.0, dmax=1.0)
CONTACT_GROUND = dict(stiffness=8.0e4, damping=2.0e2, exponent=2.0, dmax=1.0)

# Gravity (mm/s^2)
G = -9806.65


logger = logging.getLogger(__name__)
logging.basicConfig(filename="adams.log", level=logging.INFO, format="%(asctime)s| %(message)s", )

#import command hooks from Adams
names = ["Adams"]
lines = []
for n in names:
    spec = iu.find_spec(n)
    lines.append(f"{n}: " + "found at " + str(spec.origin) if spec else "NOT FOUND")
items = [x for x in dir(Adams) if not x.startswith("_")]

# ----------------------------
# Adams command execution hook
# ----------------------------
def adams_cmd(cmd: str):
    """
    Executes a command in Adams.
    """
    return Adams.execute_cmd(cmd)


def inertia_rect_prism_kg_mm2(m_kg: float, sx_mm: float, sy_mm: float, sz_mm: float):
    # Inertia about center axes for a rectangular prism:
    # Ixx = 1/12 m (sy^2 + sz^2), etc.
    ixx = (m_kg / 12.0) * (sy_mm**2 + sz_mm**2)
    iyy = (m_kg / 12.0) * (sx_mm**2 + sz_mm**2)
    izz = (m_kg / 12.0) * (sx_mm**2 + sy_mm**2)
    return ixx, iyy, izz

# ----------------------------
# Adams command builders 
# ----------------------------
def cmd_new_model(model_name: str):
    """
    Returns the command to create a new model with given name. 
    """

    return f'model create model={model_name}'


def cmd_set_units_mmkgsec():
    """
    Returns the command to set the default units of measurement in Adams.
    """

    return 'default units length=mm mass=kg force=newton time=Second angle=degrees frequency=hz'


def cmd_create_ground_plate(model_name: str, ground_part: str, ground_geom: str):
    """
    Returns the commands to create a ground plate in Adams with the size of a pallet.
    """

    return [
        f'part modify rigid_body mass_properties part_name=.{model_name}.{ground_part} material =.materials.wood',
        f'marker create marker=.{model_name}.{ground_part}.corner_marker_ground location= {0}, -{GROUND_THICK}, {0} orientation = 0.0, 0.0, 0.0',
        f'geometry create shape block block_name=.{model_name}.{ground_part}.{ground_geom} diag_corner_coords={GROUND_X}, {GROUND_THICK}, {GROUND_Y} corner_marker=.{model_name}.{ground_part}.corner_marker_ground'
    ]


def cmd_create_item_box(model_name: str, part_name: str, geom_name: str, center_marker_name: str, corner_marker_name: str, cx: float, cy: float, cz: float, sx: float, sy: float, sz: float, lx: float, ly: float, lz: float):
    """
    Returns the commands to create an item box with given measurements in Adams.
    """

    return [
        f'part create rigid_body name_and_position part_name=.{model_name}.{part_name} location = {lx}, {ly}, {lz} orientation= 0.0 , 0.0, 0.0 ',
        f'marker create marker=.{model_name}.{part_name}.{corner_marker_name} location= {lx}, {ly}, {lz} orientation = 0.0, 0.0, 0.0',
        f'marker create marker=.{model_name}.{part_name}.{center_marker_name} location= {cx}, {cy}, {cz} orientation = 0.0, 0.0, 0.0',
        f'geometry create shape block block_name=.{model_name}.{part_name}.{geom_name} diag_corner_coords={sx}, {sy}, {sz} corner_marker=.{model_name}.{part_name}.{corner_marker_name}'
    ]


def cmd_set_mass_props(model_name: str, part_name: str, center_marker_name: str, m_kg: float, ixx: float, iyy: float, izz: float):
    """
    Returns the command to set the mass properties for a given item. 
    """

    return f'part modify rigid_body mass_properties part_name=.{model_name}.{part_name} mass={m_kg} ixx={ixx} iyy={iyy} izz={izz} center_of_mass_marker=.{model_name}.{part_name}.{center_marker_name}'


def cmd_create_gravity():
    """
    Returns the command to set the gravitational force in Adams.
    """

    return f'force create body gravitational gravity=gravity x_comp=0 y_comp={G} z_comp=0'


def cmd_create_group(item_geom_group, all_geoms):
    """
    Returns the command that creates a group of items in Adams
    """

    f'group create group_name={item_geom_group} objects_in_group={all_geoms}'


def cmd_create_contact(contact_name: str,  i_geoms: str, j_geoms: str, normal: dict, fric: dict):
    """
    Returns the command to create Contacts between two given items or a given item and the ground in Adams.
    """

    k = normal["stiffness"]
    c = normal["damping"]
    e = normal["exponent"]
    dmax = normal["dmax"]
    mu_s = fric["mu_s"]
    mu_d = fric["mu_d"]
    vs = fric["vs"]
    vd = fric["vd"]

    return (
        f'contact create contact_name={contact_name} type = solid_to_solid '
        f'i_geometry_name={i_geoms} j_geometry_name={j_geoms} '
        f'stiffness={k} damping={c} exponent={e} '
        f'coulomb_friction = on mu_static={mu_s} mu_dynamic={mu_d} stiction_transition_velocity={vs} friction_transition_velocity={vd} dmax = {dmax}'
    )


def cmd_create_measure_pos(measure_name: str, part_name: str, component: str):
    """
    Returns the command to take a positions measurement in Adams.
    """

    return f'measure create object measure_name={measure_name} characteristic = cm_position object={part_name} component={component}'


def cmd_run_dynamics():
    """
    Returns the command to start a simulation in Adams. 
    """

    return f'simulation single trans type=dynamic end_time={T_END} number_of_steps={DT_OUT}'


def cmd_export_measures_to_table(filepath: str, measure_names: List[str]):
    """
    Returns the command to export taken measurements in Adams.
    """

    measures = ",".join(measure_names)
    return f'file table write file="{filepath}" measures={measures}'


def cmd_reset_model(model_name: str): 
    """
    Returns the commands that reset the simulation and delete the model in Adams.
    """
    
    return (
        f'model delete model={model_name}'
        f'simulation single reset'
    )


# ----------------------------
# Main pipeline
# ----------------------------
def main(packing_plan):
    """
    Creates a simulation in Adams. Initializes all Items specified in packing_plan as rectangle boxes 1cm in the air and lets them drop to the ground.
    Positions are measured at the beginning and end of simulation and are compared.  
    Results are added back to packing_plan.
    """

    # Create model
    adams_cmd(cmd_new_model(f"json_model_{packing_plan['id']}"))
    model = Adams.getCurrentModel()

    # Units (optional; keep if your environment doesn't already load mm-kg-s)
    try:
        adams_cmd(cmd_set_units_mmkgsec())
    except Exception:
        # Some installs don't support this command; ignore if your template already sets units.
        pass

    # Ground plate
    ground_part = "ground"
    ground_geom = "geom_ground"
    for c in cmd_create_ground_plate(model.name, ground_part, ground_geom):
        adams_cmd(c)

    # Gravity
    adams_cmd(cmd_create_gravity())

    # Items: create parts + geometry + mass props + measures
    item_parts = []
    measure_names = {}

    for item in packing_plan["items"]:
        item_id = item["id"]
        lx = item["lx"]
        ly = item["lz"] + 10
        lz = item["ly"]
        rx = item["rx"]
        ry = item["rz"] + 10
        rz = item["ry"]
        m = item["weight"] / 1000

        sx = rx - lx
        sy = ry - ly
        sz = rz - lz
        if sx <= 0 or sy <= 0 or sz <= 0:
            raise ValueError(f"Invalid AABB for {item_id}: sizes must be positive (rx>lx etc.).")

        cx = 0.5 * (lx + rx)
        cy = 0.5 * (ly + ry)
        cz = 0.5 * (lz + rz)

        part_name = f"part_{item_id}"
        geom_name = f"geom_{item_id}"
        corner_marker_name = f"corner_marker_{item_id}"
        center_marker_name = f"center_marker_{item_id}"
        for c in cmd_create_item_box(model.name, part_name, geom_name, center_marker_name, corner_marker_name, cx, cy, cz, sx, sy, sz, lx, ly, lz):
            adams_cmd(c)

        ixx, iyy, izz = inertia_rect_prism_kg_mm2(m, sx, sy, sz)
        adams_cmd(cmd_set_mass_props(model.name, part_name, center_marker_name, m, ixx, iyy, izz))

        item_parts.append((item_id, part_name, geom_name))

        # Measures: CM position components (cx,cy,cz over time)
        mx = f"m_{item_id}_cx"
        my = f"m_{item_id}_cy"
        mz = f"m_{item_id}_cz"
        adams_cmd(cmd_create_measure_pos(mx, "."+ model.name + "." + part_name, "x_component"))
        adams_cmd(cmd_create_measure_pos(my, "."+ model.name + "." + part_name, "y_component"))
        adams_cmd(cmd_create_measure_pos(mz, "."+ model.name + "." + part_name, "z_component"))
        measure_names[item_id] = [mx, my, mz]


    # Contacts
    item_geom_group = "grp_item_geoms"
    all_geoms = ",".join(["." + model.name + "." + p + "." + g for (_, p, g) in item_parts])
    adams_cmd(cmd_create_group(item_geom_group, all_geoms))
    
    geoms_list = list()
    for (_, p, g) in item_parts:
        geoms_list.append("." + model.name + "." + p + "." + g)

    pairs = list(combinations(geoms_list, 2))
    for pair in pairs:
        adams_cmd(cmd_create_contact(
            contact_name=f"contact_{pair[0].rsplit('_', 1)[1]}_{pair[1].rsplit('_', 1)[1]}",
            i_geoms=pair[0],
            j_geoms=pair[1],
            normal=CONTACT_NORMAL,
            fric=FRIC_ITEM_ITEM
        ))

    # Item–Ground contact
    for i_geom in geoms_list:
        adams_cmd(cmd_create_contact(
            contact_name=f"contact_{i_geom.rsplit('_', 1)[1]}_ground",
            i_geoms=i_geom,
            j_geoms="."+model.name+"."+ground_part+"."+ground_geom,
            normal=CONTACT_GROUND,
            fric=FRIC_ITEM_GND
        ))

    # Run simulation
    adams_cmd(cmd_run_dynamics())

    itemMovements = []
    zMovements = []
    xMovements = []
    yMovements = []
    for key,value in measure_names.items():
        delta_x = abs(Adams.evaluate_real_exp(value[0])[-1] - Adams.evaluate_real_exp(value[0])[0])
        delta_z = abs(Adams.evaluate_real_exp(value[1])[-1] - Adams.evaluate_real_exp(value[1])[0])
        delta_y = abs(Adams.evaluate_real_exp(value[2])[-1] - Adams.evaluate_real_exp(value[2])[0])
        itemDelta = abs(math.sqrt(
            delta_x * delta_x + delta_y * delta_y + delta_z * delta_z))  # math.dist(startPos, endPos)
        itemMovements.append({"item_name": key, "item_delta": itemDelta, "x_movement": delta_x, "y_movement": delta_y, "z_movement": delta_z})

        xMovements.append(delta_x)
        yMovements.append(delta_y)
        zMovements.append(delta_z)


    movementValues = {
        "mean_x_movements/mm": str(stats.mean(xMovements)),
        "max_x_movements/mm": str(max(xMovements)),
        "mean_y_movements/mm": str(stats.mean(yMovements)),
        "max_y_movements/mm": str(max(yMovements)),
        "mean_z_movements/mm": str(stats.mean(zMovements)),
        "max_z_movements/mm": str(max(zMovements)),
        "is_stable": str(
            max(xMovements) < 50
            and max(yMovements) < 50
            and max(zMovements) < 50
        ),
        "item_translations": itemMovements
    }
    packing_plan["movement_values_adams_fall"] = movementValues

    #reset the adams model to avoid the next simulation to crash
    for c in cmd_create_item_box(cmd_reset_model(model.name)):
            adams_cmd(c)


if __name__ == "__main__":
    directory = os.environ.get("ADAMS_INPUT_JSON")
    if not LOGGING_MINIMAL_ONLY : logging.info(directory)
    file_path = pathlib.Path(directory)
  
    logging.info(f"started simulation of {file_path.stem} at {datetime.now()}")
    #packing_plan_file = pathlib.Path("/home/tha/Promotion/Dataset_Generation/Data/Jsons/Pallets/pallet_2_995.json")
    #output_file = pathlib.Path("/home/tha/Promotion/Dataset_Generation/Data/Jsons/Pallets/mvp_out.json")

    with open(file_path) as f:
        packing_plan = json.load(f)

    #pallets = packing_plan["pallets"]
    #for pallet in pallets: 
    #    main(pallet)
    main(packing_plan=packing_plan)
    logging.info(f"finished simulation of {file_path.stem} at {datetime.now()}")

    with open(file_path, "w") as file:
        if not LOGGING_MINIMAL_ONLY : logging.info("writing to file")
        json.dump(packing_plan, file, indent=4)

    if not LOGGING_MINIMAL_ONLY : logging.info("dumped json")

    gc.collect()


    """if not LOGGING_MINIMAL_ONLY : logging.info("Application starting 2")
    directory = os.environ.get("ADAMS_INPUT_JSON")
    if not LOGGING_MINIMAL_ONLY : logging.info(directory)
    directory = pathlib.Path(directory)
    # iterate files (Path-based)
    for file_path in sorted(directory.iterdir(), key=lambda p: int(p.stem)):
        if not file_path.is_file():
            continue

        if int(file_path.stem) < 513: 
            continue

        logging.info(f"started simulation of {file_path.stem}")
        #packing_plan_file = pathlib.Path("/home/tha/Promotion/Dataset_Generation/Data/Jsons/Pallets/pallet_2_995.json")
        #output_file = pathlib.Path("/home/tha/Promotion/Dataset_Generation/Data/Jsons/Pallets/mvp_out.json")

        with open(file_path) as f:
            packing_plan = json.load(f)

        #pallets = packing_plan["pallets"]
        #for pallet in pallets: 
        #    main(pallet)
        main(packing_plan=packing_plan)
        logging.info(f"finished simulation of {file_path.stem}")

        with open(file_path, "w") as file:
            if not LOGGING_MINIMAL_ONLY : logging.info("writing to file")
            json.dump(packing_plan, file, indent=4)

        if not LOGGING_MINIMAL_ONLY : logging.info("dumped json")

        gc.collect()"""
