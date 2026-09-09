import pyvista
import os
import pathlib
import json
from typing import List
from PIL import Image
from tqdm import tqdm
from Generation.pallet import Pallet
from Generation.pallet_generator import Pallet_list_generator


def visualize_pallet_angle_view(plts: List[Pallet]):
    """
    Generates an image of each of the given pallets in a 45° angled view. 
    Saves the generated pngs in the Png/Pallets subfolder
    """

    output_folder = (
        pathlib.Path(__file__).resolve().parent / "Png" / "Pallets" 
    )

    for pallet in tqdm(plts, desc="angle view highlighted pallet"):

        plotter = pyvista.Plotter(off_screen=True, window_size=[896,896])
        invisible_box = pyvista.Cube(bounds=(0, 1200, 0, 800, 0, 1856))
        plotter.add_mesh(invisible_box, opacity=0.0, show_edges=False)

        for item in pallet.items:

            bounds = (item.lx, item.rx, item.ly, item.ry, item.lz, item.rz)

            pv_cube = pyvista.Cube(bounds=bounds)
            plotter.add_mesh(pv_cube, color="lightblue", opacity=1, show_edges=True, line_width=0.5)

        plotter.view_vector((1, 1, 0.577))
        plotter.set_background("white")
        plotter.camera.zoom(1)

        image = plotter.screenshot(return_img=True)
        plotter.close()
        filename = f"{pallet.id}.png"
        filepath = os.path.join(output_folder, filename)
        Image.fromarray(image).save(filepath)


if __name__ == "__main__":

    #generate new pallets and visualize them
    generator = Pallet_list_generator()
    pallet_list = generator.generate_pallet_list(10, False)
    visualize_pallet_angle_view(pallet_list)

    #read pallets from json files and visualizes them
    """filename = "insert filename here"
    pallet_list: List[Pallet] = list()
    json_file = (
        pathlib.Path(__file__).resolve().parent.parent / "Jsons" / "Pallets" / filename
    )
    with open(json_file) as f:
        pallet_json = json.load(f)

    #account for two different json formats one storing one pallet per file the other multiple
    if pallet_json.get("pallets"): 
        for pallet in pallet_json["pallets"]: 
            pallet_list.append(Pallet.from_json(pallet))
    else: 
        pallet_list.append(Pallet.from_json(pallet_json))

    visualize_pallet_angle_view(pallet_list)"""
