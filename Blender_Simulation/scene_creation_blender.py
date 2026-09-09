import ast
import gc
import json
import logging
import math
import pathlib
import statistics
import sys
import time
import bpy


# Import physics configuration
PHYSICS_CONFIG_STATIC = {
    "item_friction": 0.47, 
    "ground_friction": 0.6,
    "pallet_friction": 0.6,
    "item_restitution": 0.070,
    "ground_restitution": 0.1,
    "pallet_restitution": 0.0,
    "linear_damping": 0.09, 
    "angular_damping": 0.1,
    "collision_margin": 0.000001,
    "split_impulse": False,
    "substeps_per_frame": 100,
    "solver_iterations": 200,
    "gravity": [0.0, 0.0, -9.81],
    "fall_height": 20
}

#bpy.context.scene.frame_end The integer of the last frame in the .blend file.
ENDFRAME = 120 

FIXED_OBJECTS = ["Light.000", "Light.001", "Light.002"]

# for Blender scene: convert mm to m: Blender has problems with friction calculations at smaller scale so scale of items is adapted proportionally bigger by factor of 5 for every axis.
SCALE_DIVISOR = 200  

logger = logging.getLogger(__name__)


def getRGBFromHex(hex: str) -> tuple:
    """
    Converts the color from hex in RGB format.

    Parameters.
    -----------
    hex: str
        The color given in hex format.

    Returns.
    --------
    rgb: tuple
        The percentage of red, green, and blue in %, i.e., values are in [0, 1].

    Example.
    --------
    >>> getRGBFromHex("#FFFFFF")
    (1.0, 1.0, 1.0)
    """

    r_hex = hex[1:3]
    g_hex = hex[3:5]
    b_hex = hex[5:7]
    return (
        int(r_hex, 16) / 255.0,
        int(g_hex, 16) / 255.0,
        int(b_hex, 16) / 255.0,
    )


def getRGBFromColorName() -> tuple:
    """
    For a given name, which is specified in colors.json in the visualization package, the RGB percentages are returned.
    """
    
    return getRGBFromHex("#201923")  # hexname)


def addItemToScene(item, mode) -> None:
    """
    Adds an item to the Blender scene. 
    Depending on the mode the item edges are rounded off so the rigid body collision behaves less like a perfectly sharp box.
    """

    locationValues = [
        item["lx"] + item["length"] / 2,
        item["ly"] + item["width"] / 2,
        item["lz"] + item["height"] / 2,
    ]

    # Create cube
    bpy.ops.mesh.primitive_cube_add(
        size=1.0,
        calc_uvs=True,
        enter_editmode=False,
        align="WORLD",
        location=locationValues,
        rotation=(0.0, 0.0, 0.0),
        scale=(item["length"], item["width"], item["height"]),
    )

    ob = bpy.context.object
    ob.name = f"item_{item['id']}"

    # Apply scale so bevel width is interpreted correctly
    bpy.context.view_layer.objects.active = ob
    bpy.ops.object.transform_apply(location=False, rotation=False, scale=True)

    # Add rounded edges via bevel
    if mode == 2: 
        bevel = ob.modifiers.new(name="RoundedEdges", type="BEVEL")
        bevel.width = 20 / 200      # example: 10 mm if your scene unit is meters
        bevel.segments = 3
        bevel.limit_method = "ANGLE"
        bevel.angle_limit = 0.523599  # 30 degrees in radians

    # Apply bevel so collision mesh uses the rounded geometry
    bpy.ops.object.modifier_apply(modifier=bevel.name)

    # Add rigid body
    bpy.ops.rigidbody.object_add()
    ob.rigid_body.enabled = True
    ob.rigid_body.mass = item["weight"]

    # IMPORTANT: BOX ignores the rounded geometry for collision
    ob.rigid_body.collision_shape = "CONVEX_HULL"

    # Physics parameters
    ob.rigid_body.friction = PHYSICS_CONFIG_STATIC["item_friction"]
    ob.rigid_body.restitution = PHYSICS_CONFIG_STATIC["item_restitution"]
    ob.rigid_body.linear_damping = PHYSICS_CONFIG_STATIC["linear_damping"]
    ob.rigid_body.angular_damping = PHYSICS_CONFIG_STATIC["angular_damping"]
    ob.rigid_body.collision_margin = PHYSICS_CONFIG_STATIC["collision_margin"]

    # Material / color
    mat = bpy.data.materials.get(str(item["id"]))
    if mat is None:
        mat = bpy.data.materials.new(name=str(item["id"]))
        mat.use_nodes = True
        tree = mat.node_tree
        nodes = tree.nodes
        bsdf = nodes["Principled BSDF"]
        color = getRGBFromColorName()
        color = (color[0], color[1], color[2], 1)
        bsdf.inputs["Base Color"].default_value = color
        mat.diffuse_color = color

    if ob.data.materials:
        ob.data.materials[0] = mat
    else:
        ob.data.materials.append(mat)


def __addGround(size: tuple = (500, 500, 1)) -> None:
    """
    Adds a ground plane to the scene.
    """

    bpy.ops.mesh.primitive_plane_add(
        size=1.0, enter_editmode=False, align="WORLD", location=(0, 0, 0)
    )

    # scale argument does not work here
    bpy.ops.transform.resize(
        value=size,
        orient_type="GLOBAL",
        orient_matrix=((1, 0, 0), (0, 1, 0), (0, 0, 1)),
        orient_matrix_type="GLOBAL",
        mirror=False,
        use_proportional_edit=False,
        proportional_edit_falloff="SMOOTH",
        proportional_size=1,
        use_proportional_connected=False,
        use_proportional_projected=False,
    )

    bpy.ops.transform.translate(value=(0, 0, 0))

    # set the color
    bottomMaterial = bpy.data.materials.new(name="bottom_color")
    bottomMaterial.use_nodes = True
    tree = bottomMaterial.node_tree
    nodes = tree.nodes
    bsdf = nodes["Principled BSDF"]
    # make the bottom "transparent" -> white
    color = (1, 1, 1, 1)  # color = (0, 0.0684781, 0.278894, 1)
    bsdf.inputs["Base Color"].default_value = color
    bsdf.inputs["Alpha"].default_value = 1
    bsdf.inputs["Emission Color"].default_value = (1, 1, 1, 1)

    bottomMaterial.diffuse_color = color
    ob = bpy.context.active_object
    ob.data.materials.append(bottomMaterial)

    # set rigid body to passive
    bpy.ops.rigidbody.object_add()
    bpy.context.object.rigid_body.type = "PASSIVE"
    # Physics parameters for ground (using configuration)
    bpy.context.object.rigid_body.friction = PHYSICS_CONFIG_STATIC[
        "ground_friction"
    ]
    bpy.context.object.rigid_body.restitution = PHYSICS_CONFIG_STATIC[
        "ground_restitution"
    ]
    bpy.context.object.name = "bottom"


def __initScene() -> None:
    """
    Initializes the scene.
    """
    
    for mat in bpy.data.materials:
        bpy.data.materials.remove(mat)

    scene = bpy.context.scene.gravity = PHYSICS_CONFIG_STATIC["gravity"]
    # enable the rigidbody world such that the simulation is enabled
    bpy.context.scene.rigidbody_world.enabled = True
    bpy.context.scene.rigidbody_world.collection = bpy.data.collections[
        "Collection"
    ]

    # Global physics world parameters for tuning (using configuration)
    # Set solver iterations for physics accuracy
    try:
        bpy.context.scene.rigidbody_world.solver_iterations = (
            PHYSICS_CONFIG_STATIC["solver_iterations"]
        )
        bpy.context.scene.rigidbody_world.substeps_per_frame = (
            PHYSICS_CONFIG_STATIC["substeps_per_frame"]
        )
        bpy.context.scene.rigidbody_world.use_split_impulse = (
            PHYSICS_CONFIG_STATIC["split_impulse"]
        )
    except AttributeError:
        logger.warning(
            "Could not set solver_iterations - using Blender defaults"
        )

    # Set cache frame end
    try:
        bpy.context.scene.rigidbody_world.point_cache.frame_end = ENDFRAME
    except AttributeError:
        logger.warning(
            "Could not set point_cache.frame_end - using Blender defaults"
        )

    # draw border of objects
    bpy.context.scene.render.use_freestyle = True

    objsNotToRemove = []
    for objName in FIXED_OBJECTS:
        objsNotToRemove.append(bpy.data.objects.get(objName))
    for obj in bpy.data.objects:
        if not (obj) in objsNotToRemove:
            bpy.data.objects.remove(obj)

    __addGround()


def simulate(packing_plan, mode: int) -> None:
    """
    Creates the simulations.
    Initializes all items in packing plan at fall_height and lets them drop to the ground.
    Calculates their displacement during simulation and adds the results to the packing_plan.
    """
    
    __initScene()

    # iterate over packing plan
    for item in packing_plan["items"]:
        properties = {
            "lx": item["lx"] / SCALE_DIVISOR,
            "ly": item["ly"] / SCALE_DIVISOR,
            "lz": ((item["lz"]) + PHYSICS_CONFIG_STATIC["fall_height"]) / SCALE_DIVISOR,
            "length": (item["rx"] - item["lx"]) / SCALE_DIVISOR,
            "width": (item["ry"] - item["ly"]) / SCALE_DIVISOR,
            "height": (item["rz"] - item["lz"]) / SCALE_DIVISOR,
            "weight": (item["weight"] / (1000)) * 125, #adjustment for the bigger item scale factor 5 for every axis.
            "id": item["id"],
        }

        addItemToScene(properties, mode)

    # every frame has to be set in order to have a correct render and rigid body simulation
    startTime = time.time()
    scene = bpy.context.scene
    seconds = 5
    fps = 24

    scene.render.fps = fps
    scene.frame_start = 1
    scene.frame_end = seconds * fps
    for f in range(ENDFRAME + 1):
        scene.frame_set(f)

    # store the item locations for start and endframe
    startTime = time.time()
    itemLocations = {}
    frames4investigation = [0, ENDFRAME]
    for f in frames4investigation:
        # set the correct frame
        scene = bpy.context.scene
        scene.frame_set(f)

        # get the locations of each item
        frameLocations = {}
        for obj in bpy.data.objects:
            itemName = obj.name
            if not (itemName in FIXED_OBJECTS):
                if not (itemName in itemLocations.keys()):
                    itemLocations[itemName] = {}
                itemLocations[itemName][f] = list(obj.matrix_world.translation)

    # compare the previously stored item locations
    itemMovements = []
    zMovements = []
    xMovements = []
    yMovements = []
    for itemName, frameAndPositions in itemLocations.items():
        startPos = frameAndPositions.get(frames4investigation[0])
        endPos = frameAndPositions.get(frames4investigation[-1])

        itemDelta = math.dist(startPos, endPos) * SCALE_DIVISOR
        itemMovements.append({"item_name": itemName, "itemDelta": itemDelta})

        xMovements.append(abs(startPos[0] - endPos[0]) * SCALE_DIVISOR) 
        yMovements.append(abs(startPos[1] - endPos[1]) * SCALE_DIVISOR)
        zMovements.append(abs(startPos[2] - endPos[2]) * SCALE_DIVISOR)  

    # append the KPIs to a file
    movementValues = {
        "mean_x_movements/mm": str(statistics.fmean(xMovements)),
        "max_x_movements/mm": str(max(xMovements)),
        "mean_y_movements/mm": str(statistics.fmean(yMovements)),
        "max_y_movements/mm": str(max(yMovements)),
        "mean_z_movements/mm": str(statistics.fmean(zMovements)),
        "max_z_movements/mm": str(max(zMovements)),
        "is_stable": str(
            max(xMovements) < 50
            and max(yMovements) < 50
            and max(zMovements) < 50
        ),
        "item_translations": itemMovements
    }

    packing_plan["movement_values_blender"] = movementValues


if __name__ == "__main__":
    """
    This script generates a scene in a Blender file. Prepares a simulation and then executes this simulation. 
    Results are being written int the input_output_file.
    Code is taken and adapted from 'https://doi.org/10.1177/02783649231193048'.
    """

    # Get the command line arguments
    argv = sys.argv
    argv = argv[argv.index("--") + 1 :]

    # Parse arguments
    commands = {}
    for i in range(int(len(argv) / 2)):
        commands[argv[2 * i]] = argv[2 * i + 1]
    mode = ast.literal_eval(commands.get("mode"))

    # Extract basic arguments
    # Read data from files
    input_output_file = pathlib.Path(commands.get("packing_plan_file"))

    with open(input_output_file) as f:
        packing_plan = json.load(f)

    simulate(packing_plan, mode)

    with open(input_output_file, "w") as file:
        json.dump(packing_plan, file, indent=4)

    gc.collect()
