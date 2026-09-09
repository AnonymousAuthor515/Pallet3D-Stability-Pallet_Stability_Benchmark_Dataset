import pyvista
import os
import pathlib
import json
from typing import List
from PIL import Image
from tqdm import tqdm
from Generation.item import Item
from Generation.item_catalog_generator import Item_generator, Size_modifier


def visualize_item_angle_view(items):
    """
    Generates an image of each of the given items in a 45° angled view. 
    Saves the generated pngs in the Png/Pallets subfolder
    """

    output_folder = (
        pathlib.Path(__file__).resolve().parent / "Png" / "Items" 
    )

    for item, modifier in tqdm(items, desc="angle view highlighted item"):

        plotter = pyvista.Plotter(off_screen=True, window_size=[896,896])
        invisible_box = pyvista.Cube(bounds=(0, 1200, 0, 800, 0, 1856))
        plotter.add_mesh(invisible_box, opacity=0.0, show_edges=False)

        bounds = (item.lx, item.rx, item.ly, item.ry, item.lz, item.rz)

        pv_cube = pyvista.Cube(bounds=bounds)
        plotter.add_mesh(pv_cube, color="lightblue", opacity=1, show_edges=True, line_width=0.5)

        plotter.view_vector((1, 1, 0.577))
        plotter.set_background("white")
        plotter.camera.zoom(1)

        image = plotter.screenshot(return_img=True)
        plotter.close()
        filename = f"item_{item.id}_{modifier}.png"
        filepath = os.path.join(output_folder, filename)
        Image.fromarray(image).save(filepath)


if __name__ == "__main__": 

    #generate new items and visualize each of them
    generator = Item_generator()
    item_list = generator.generate_item_catalog(6, False)
    visualize_item_angle_view(item_list)

    #read items from existing catalog file and visualizes them
    """item_list: List[Item] = list()
    json_file = (
        pathlib.Path(__file__).resolve().parent.parent / "Jsons" / "Items" / "item_catalog.json"
    )
    with open(json_file) as f:
        catalog_json = json.load(f)

    for modifier in Size_modifier:
        sub_catalog = catalog_json[modifier.text]
        for item in sub_catalog: 
            item_list.append(Item.from_json(item), modifier.text)
    
    visualize_item_angle_view(item_list)"""
