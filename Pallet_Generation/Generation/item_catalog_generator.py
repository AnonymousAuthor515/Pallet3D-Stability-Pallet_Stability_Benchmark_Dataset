import pathlib
import random
import json
from typing import List
from tqdm import tqdm
from item import Item
from enum import Enum

ITEM_DIMENSIONS = {
    """
    Range of dimensions for the generated items. 
    """

    "min_size" : (100, 100, 60),
    "max_size" : (600, 400, 400), 
    "weight_range": (300, 8000)
}


class Size_modifier(Enum):
    """
    Categories items get assigned to represent a dimensional characteristic for it. 
    Used to generate a clear definable but diverse itemset so all shapes are represented.
    No wide items are needed as items can be rotated during placement making long and wide the same. 
    """

    MEDIUM = (0, "medium")
    TALL = (1, "tall")
    HIGH = (2, "high")
    LONG = (3, "long")
    SMALL = (4, "small")
    FLAT = (5, "flat")

    def __init__(self, value, text): 
        self._value_ = value
        self.text = text


class Item_generator(): 
    """
    Class that generates the item-catalog and saves it in a json file. Only defining feature is an auto-incrementing id used for the items.
    """

    def __init__(self): 
        self.next_id = 0 
        return 
    

    def generate_item_catalog(self, item_count = 600, save_to_json = True) -> List[Item, str]: 
        """
        generates an item catalog of the given size saves it to the json if wanted and returns it. 
        Splits the items in equal parts of each size modifier. 
        """

        item_catalog: List[Item, str]
        for i in tqdm(range(0, item_count)): 
            modifier = Size_modifier.Medium

            if i > item_count * (1/6): 
                modifier = Size_modifier.TALL

            if i > item_count * (2/6): 
                modifier = Size_modifier.HIGH

            if i > item_count * (3/6):
                modifier = Size_modifier.LONG 

            if i > item_count * (4/6):
                modifier = Size_modifier.SMALL
            
            if i > item_count * (5/6):
                modifier = Size_modifier.FLAT

            item = self.generate_item(modifier)
            item_catalog.append(item, modifier.text)

            if save_to_json: 
                self.save_item_to_catalog(item, modifier)
        
        return item_catalog


    def generate_item(self, size_modifier: Size_modifier): 
        """
        Generates dimensions for the next item based on the given Size_modifier and initialies the new item. 
        """

        lx,ly,lz,rx,ry,rz, weight = self.generate_random_item_dimension_within_bound(size_modifier)
        
        item: Item = Item(self.next_id, lx, ly, lz, rx, ry, rz, weight)
    
        self.next_id = self.next_id + 1
        return item
    

    def generate_random_item_dimension_within_bound(self, size_modifier: Size_modifier): 
        """
        Generates random item dimensions within the bounds of the min/max dimensions and based on the size modifier settings
        """

        lx, ly, lz = 0, 0, 0
        rx, ry, rz = ITEM_DIMENSIONS["max_size"]

        min_rx, min_ry, min_rz = ITEM_DIMENSIONS["min_size"]
        max_rx, max_ry, max_rz = ITEM_DIMENSIONS["max_size"]

        #dimension determination
        if size_modifier == Size_modifier.MEDIUM: 
            min_rx = max(ITEM_DIMENSIONS["min_size"][0], ITEM_DIMENSIONS["max_size"][0] * (5/12))
            min_ry = max(ITEM_DIMENSIONS["min_size"][1], ITEM_DIMENSIONS["max_size"][1] * (5/12))
            min_rz = max(ITEM_DIMENSIONS["min_size"][2], ITEM_DIMENSIONS["max_size"][2] * (5/12))
            max_rx = max(ITEM_DIMENSIONS["min_size"][0], ITEM_DIMENSIONS["max_size"][0] * (10/12))
            max_ry = max(ITEM_DIMENSIONS["min_size"][1], ITEM_DIMENSIONS["max_size"][1] * (10/12))
            max_rz = max(ITEM_DIMENSIONS["min_size"][2], ITEM_DIMENSIONS["max_size"][2] * (10/12))

        elif size_modifier == Size_modifier.TALL: 
            min_rx = max(ITEM_DIMENSIONS["min_size"][0], ITEM_DIMENSIONS["max_size"][0] * (2/3))
            min_ry = max(ITEM_DIMENSIONS["min_size"][1], ITEM_DIMENSIONS["max_size"][1] * (2/3))
            min_rz = max(ITEM_DIMENSIONS["min_size"][2], ITEM_DIMENSIONS["max_size"][2] * (2/3))
        
        elif size_modifier == Size_modifier.SMALL: 
            min_rx = max(ITEM_DIMENSIONS["min_size"][0], ITEM_DIMENSIONS["max_size"][0] * (4/12))
            min_ry = max(ITEM_DIMENSIONS["min_size"][1], ITEM_DIMENSIONS["max_size"][1] * (4/12))
            min_rz = max(ITEM_DIMENSIONS["min_size"][2], ITEM_DIMENSIONS["max_size"][2] * (4/12))
            max_rx = max(ITEM_DIMENSIONS["min_size"][0], ITEM_DIMENSIONS["max_size"][0] * (6/12))
            max_ry = max(ITEM_DIMENSIONS["min_size"][1], ITEM_DIMENSIONS["max_size"][1] * (6/12))
            max_rz = max(ITEM_DIMENSIONS["min_size"][2], ITEM_DIMENSIONS["max_size"][2] * (6/12))
        
        elif size_modifier == Size_modifier.LONG: 
            min_rx = max(ITEM_DIMENSIONS["min_size"][0], ITEM_DIMENSIONS["max_size"][0] * (5/12))
            max_rx = max(ITEM_DIMENSIONS["min_size"][0], ITEM_DIMENSIONS["max_size"][1] * (8/10))
            max_ry = max(ITEM_DIMENSIONS["min_size"][1], ITEM_DIMENSIONS["max_size"][1] * (6/10))
            max_rz = max(ITEM_DIMENSIONS["min_size"][2], ITEM_DIMENSIONS["max_size"][2] * (6/10))
            min_ry = max(ITEM_DIMENSIONS["min_size"][1], ITEM_DIMENSIONS["max_size"][1] * (3/10))
            min_rz = max(ITEM_DIMENSIONS["min_size"][2], ITEM_DIMENSIONS["max_size"][2] * (3/10))
        
        elif size_modifier == Size_modifier.HIGH: 
            min_rx = max(ITEM_DIMENSIONS["min_size"][0], ITEM_DIMENSIONS["max_size"][0] * (3/10))
            max_rx = max(ITEM_DIMENSIONS["min_size"][0], ITEM_DIMENSIONS["max_size"][0] * (5/10))
            min_ry = max(min_ry, max_rx * (2/3))
            max_ry = min(max_ry, max_rx * (4/3))
            min_rz = max(ITEM_DIMENSIONS["min_size"][2], ITEM_DIMENSIONS["max_size"][2] * (10/12))        
        
        elif size_modifier == Size_modifier.FLAT: 
            min_rx = max(ITEM_DIMENSIONS["min_size"][0], ITEM_DIMENSIONS["max_size"][0] * (4/10))
            min_ry = max(ITEM_DIMENSIONS["min_size"][1], ITEM_DIMENSIONS["max_size"][1] * (4/10))            
            max_rx = max(ITEM_DIMENSIONS["min_size"][0], ITEM_DIMENSIONS["max_size"][0] * (8/10))
            max_ry = max(ITEM_DIMENSIONS["min_size"][1], ITEM_DIMENSIONS["max_size"][1] * (8/10))
            max_rz = max(ITEM_DIMENSIONS["min_size"][2], ITEM_DIMENSIONS["max_size"][2] * (4/10)) 
            min_rz = max(ITEM_DIMENSIONS["min_size"][2], ITEM_DIMENSIONS["max_size"][2] * (2/10)) 

        rx = random.randint(int(min_rx), int(max_rx))
        ry = random.randint(int(min_ry), int(max_ry))       
        rz = random.randint(int(min_rz), int(max_rz))

        #weight determination
        length = rx - lx 
        width = ry - ly 
        height = rz - lz
        volume = length * width * height 

        max_volume = ITEM_DIMENSIONS["max_size"][0] * ITEM_DIMENSIONS["max_size"][1] * ITEM_DIMENSIONS["max_size"][2]
        relative_volume = volume / max_volume
        adjusted_max_weight = relative_volume * ITEM_DIMENSIONS["weight_range"][1]

        min_weight = min(ITEM_DIMENSIONS["weight_range"][1], max(ITEM_DIMENSIONS["weight_range"][0], adjusted_max_weight - (adjusted_max_weight * (3/10)) ))
        max_weight = max(ITEM_DIMENSIONS["weight_range"][1], min(ITEM_DIMENSIONS["weight_range"][1], adjusted_max_weight + (adjusted_max_weight * (3/10)) ))

        weight = random.randint(int(min_weight), int(max_weight))

        return (lx, ly, lz, rx, ry, rz, weight)


    def save_item_to_catalog(self, item: Item, size_modifier: Size_modifier): 
        """
        Saves a given item to the item-catalog json file. 
        """

        output_file = (
            pathlib.Path(__file__).resolve().parent.parent / "Jsons" / "Items" / "item_catalog.json"
        )

        with open(output_file) as f:
            item_catalog = json.load(f)
        
        item_catalog.setdefault(size_modifier.text, []).append(item.to_catalog_json())

        with open(output_file, "w") as file:
            json.dump(item_catalog, file, indent=4)

        return 
    

if __name__ == "__main__": 

    generator = Item_generator()
    generator.generate_item_catalog(600, True)