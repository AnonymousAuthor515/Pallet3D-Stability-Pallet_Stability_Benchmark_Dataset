import pathlib
import random
import json
from typing import List, Set
from tqdm import tqdm
from multiprocessing import Pool
from item import Item
from pallet import Pallet


EMPTY_SPACE_CONFIGS = {
    """
    Defines the minimum size for empty space patches to be viable for item placement.
    """

    "min_size" : (150, 150, 90),
}


LAYER_DIMENSIONS = {
    """
    Defines the dimension range of the layers that the pallet layout is constructed of.
    """

    "min_height" : 800,
    "max_height" : 2000
}


class Rectangle():
    """
    This class represents a Rectangle in two dimensional space defined by two points (lower-left point and upper-right point) as well as an occupation indicator
    """

    def __init__(self, lx, ly, rx, ry, value = 1): 

        self.lx = lx
        self.ly = ly
        self.rx = rx
        self.ry = ry
        
        self.length = self.rx - self.lx
        self.width = self.ry - self.ly
        self.area = self.length * self.width
        
        self.value = value


    def intersects(self, other: 'Rectangle'): 
        """
        Returns whether two given rectangles intersect. 
        """


        # If one is completely to the left of the other
        if self.rx <= other.lx or other.rx <= self.lx: 
            return False

        # If one is completely below the other
        if self.ry <= other.ly or other.ry <= self.ly: 
            return False

        return True


    def is_included(self, other: 'Rectangle'): 
        """
        Returns whether an other rectangle is completely included in the given rectangle. 
        """

        return self.lx >= other.lx and self.rx <= other.rx and self.ly >= other.ly and self.ry <= other.ry 

    
    def __lt__(self, other: 'Rectangle'):
        """
        Comperator used to order rectangles by size. 
        """
        
        return self.area < other.area
    

    def add_rectangle(self, other):
        """
        Integrates other rectangle in given rectangle by creating new bounds as the bounding box of both previous rectangles.
        """ 
        
        self.lx = min(self.lx, other.lx)
        self.ly = min(self.ly, other.ly)
        self.rx = max(self.rx, other.rx)
        self.ry = max(self.ry, other.ry)


class Simple_space(): 
    """
    The Simple_space class represents a patch of space defined by two points (front-left-lower point and back-right-upper point) within the pallet dimensions.
    Can either be empty or occupied. 
    """

    def __init__(self, lx, ly, lz, rx, ry, rz):

        self.lx = lx
        self.ly = ly
        self.lz = lz
        self.rx = rx
        self.ry = ry
        self.rz = rz 

        self.length = self.rx - self.lx
        self.width = self.ry - self.ly
        self.height = self.rz - self.lz

        self.base_area = self.length * self.width
        self.volume = self.length * self.width * self.height


    def intersection_rectangle(self, other: 'Simple_space') -> Rectangle: 
        """
        Calculates the intersection with an other patch of space on the x-y coordinate layer.
        Returns a 0-Rectangle if there is no intersection. 
        """

        lx = max(self.lx, other.lx)
        ly = max(self.ly, other.ly)
        rx = min(self.rx, other.rx)
        ry = min(self.ry, other.ry)

        if lx < rx and ly < ry: 
            return Rectangle(lx, ly, rx, ry)
        else: 
            return Rectangle(0,0,0,0)


    def z_support(self, placed_items_below: List['Item']): 
        """
        Checks if an empty patch of space has z-support by either the ground or underlying items. 
        """

        if self.lz == 0: 
            return 100
        
        supporting_surfaces: List['Rectangle'] = list()
        threshold = 5
        for item in placed_items_below: 
            if self.has_z_overlap(item) and (item.rz <= self.lz <= item.rz + threshold): 
                lx = max(self.lx, item.lx)
                ly = max(self.ly, item.ly)
                rx = min(self.rx, item.rx)
                ry = min(self.ry, item.ry)

                intersection = Rectangle(lx, ly, rx, ry)
                supporting_surfaces.append(intersection)
        
        supported_area = 0
        for surface in supporting_surfaces: 
            supported_area += surface.area

        return (supported_area / self.base_area) * 100


    def has_z_overlap(self, other: 'Item') -> bool: 
        """
        Calculates whether a space has overlap with an item in x-y coordinate layer. 
        """

        # If one is completely to the left of the other
        if self.rx <= other.lx or other.rx <= self.lx: 
            return False

        # If one is completely below the other
        if self.ry <= other.ly or other.ry <= self.ly: 
            return False

        return True
    

    def adapt_coordinates_based_on_z_support(self, placed_items_below: List['Item']): 
        """
        Adapts the dimensions and coordinates of the empty Simple_space based on its support structure by items beneath it. 
        Cuts away unsupported patches of space to avoid an item being placed in the air with no support structure at all.  
        """

        if self.lz == 0: 
            return 
        
        supporting_surfaces: List['Rectangle'] = list()
        for item in placed_items_below: 
            if self.has_z_overlap(item) and (item.rz <= self.lz <= item.rz + 10): 
                lx = max(self.lx, item.lx)
                ly = max(self.ly, item.ly)
                rx = min(self.rx, item.rx)
                ry = min(self.ry, item.ry)

                intersection = Rectangle(lx, ly, rx, ry)
                supporting_surfaces.append(intersection)
        
        lx = supporting_surfaces[0].lx
        ly = supporting_surfaces[0].ly
        rx = supporting_surfaces[0].rx
        ry = supporting_surfaces[0].ry
        for surface in supporting_surfaces:
            lx = min(lx, surface.lx)
            ly = min(ly, surface.ly)
            rx = max(rx, surface.rx)
            ry = max(ry, surface.ry)

        self.lx = lx 
        self.ly = ly
        self.rx = rx 
        self.ry = ry 
        self.length = self.rx - self.lx
        self.width = self.ry - self.ly
        self.base_area = self.length * self.width
        self.volume = self.length * self.width * self.height

        return 


    def __lt__(self, other): 
        """
        Comperator used to order spaces based on volume.
        """

        return self.volume < other.volume
    

    def __eq__(self, other):
        """
        Comporator used to decide whether to spaces are the same.
        """

        if not isinstance(other, Simple_space):
            return False
        return (self.lx, self.ly, self.rx, self.ry) == (other.lx, other.ly, other.rx, other.ry)


    def __hash__(self):
        """
        Hash function of the Simple_space class. 
        """

        return hash((self.lx, self.ly, self.rx, self.ry))


class Layer_generator(): 
    """
    Class that generate a layer of the pallet based on a given order (list of given items to be placed). 
    Generates layers of variable height to be filled, filles a layer till its considered full.
    """

    def __init__(self, item_order: List[Item], placed_items: Set[Item], offset_height, next_item_id):
        self.length = 1200
        self.width = 800
        self.height = self.generate_random_layer_height_within_bound(offset_height, item_order)
        self.lz = offset_height
        self.rz = offset_height + self.height

        self.item_catalog = item_order
        self.placed_items = placed_items 
        self.next_id = next_item_id

        #layerspecific placed item list 
        #lets upper layers ignore the placed items of lower layers for placement calculation
        self.item_list: List[Item] = list()

        #used for skipping lower empty spaces that arent big enough anyway 
        self.min_z = 0


    def fill_layer(self): 
        """
        Method to fill a layer with items. 
        As long as remaining items exist in the order remaining spaces are evaluated and the biggest remaining space to fit an item is selected. 
        The biggest fitting item is placed within this space. 
        """    

        if len(self.item_catalog) == 0: 
            return 
        
        empty_space = self.calculate_empty_space()
        while self.is_space_big_enough(empty_space) and len(self.item_catalog) > 0: 
            no_item_fits = self.pick_items(empty_space)
            if no_item_fits or len(self.item_catalog) == 0: 
                self.sanity_check()
                self.placed_items.add(item for item in self.item_list)
                return 
            empty_space = self.calculate_empty_space()
        self.sanity_check()
        self.placed_items.add(item for item in self.item_list)
        return 
    

    def sanity_check(self): 
        """
        Algorithm tends to bad placements in most upper positions, so placements that do not fit minimum requirements are removed 
        """

        #find highest items with no items above 
        new_item_list: List['Item'] = list()
        for item in self.item_list: 
            if not item.has_items_above(self.item_list) and item.get_surface_support(self.item_list) < 60: 
                continue 
            else: 
                new_item_list.append(item)
    
        self.item_list = new_item_list
    

    def calculate_empty_space(self) -> Simple_space:
        """
        Calculates the biggest consecutive empty space left in the layer.
        If no items are placed yet the space is the entire layer volume. 
        """

        if len(self.item_list) < 1: 
            return Simple_space(0, 0, self.lz, self.length, self.width, self.rz)

        empty_space = self.calculate_biggest_empty_space_left()
        return empty_space


    def get_height_segments(self) -> List[int]: 
        """
        To reduce complexity in empty space calculation the layer is split up in height segments defined by placed item boarders. 
        Each unique item.rz within the layer defines a segment.
        Self.min_z denotes the minimum relevant z value in this layer. 
        It gets updated as item placement proceeds and lower empty spaces get to small to fit remaining items rendering them irrelevant for further consideration. 
        """

        relevant_heights: List[int] = list()
        if self.min_z == 0: 
            relevant_heights.append(0)

        unique_rz = list({item.rz for item in self.item_list if (item.rz) < self.rz}) 
        for rz in unique_rz: 
            if rz - self.lz > self.min_z: 
                relevant_heights.append((rz - self.lz) +1)

        return sorted(relevant_heights)


    def calculate_biggest_empty_space_left(self) -> Simple_space: 
        """
        Calculates the biggest consecutive patches of unoccupied space left in the layer. 
        Calculation on the entire mm resolution voxel grid are to complex so resolution is downscaled to a scale with pixels of size = 1 Item (leading to pixels of various size).
        Unoccupied space is then calculated as the largest sum of consecutive unoccuped group of pixels (calculated by acutal pixel volume rather than pixel number). 
        To further reduce the resolution the z-axis is also divided in segments denoted by item boarders. So pixels on the x-y plane are only calculated for each segment and then patched toghether at the end.  
        """
        cubes = set()

        height_segments = self.get_height_segments()
        for lz in height_segments:
            big_enough_spaces_in_layer = False
            # for each z-layer, compute largest rectangle in 2D height map
            downscaled_voxels = self.downscale((lz + self.lz))
            rects = self.largest_distinct_rectangles_in_heightmap(downscaled_voxels)
            for rect in rects: 
                cube_temp = Simple_space(rect.lx, rect.ly, (lz + self.lz), rect.rx, rect.ry, (self.rz))
                if self.is_space_big_enough(cube_temp):
                    cubes.add(cube_temp)
                    big_enough_spaces_in_layer = True
                
            if not big_enough_spaces_in_layer: 
                self.min_z = max(self.min_z, lz)
        
        return self.select_empty_space(cubes)


    def select_empty_space(self, cubes: Set[Simple_space]) -> Simple_space: 
        """
        Selects the best remaining empty space of all remaining emtpy saces left. 
        Prefers lower, bigger spaces with a minimum of base support. 
        """

        #prefere lower open spaces 
        if len(cubes) == 0: 
            #return space to small to fit an item -> should lead to auto termination of process
            return Simple_space(0,0,0,1,1,1)

        cube_list = list(cubes)
        distinct_z_values = list({cube.lz for cube in cube_list})
        distinct_z_values = sorted(distinct_z_values, key=lambda lz: lz)

        for z in distinct_z_values: 
            z_layer_list = list({cube for cube in cube_list if cube.lz == z})
            z_layer_list = sorted(z_layer_list, key = lambda cube: cube.volume, reverse=True)

            for cube in z_layer_list: 
                z_support = cube.z_support(self.item_list)
                if z_support > 20: 
                    return cube 
                else: 
                    cube.adapt_coordinates_based_on_z_support(self.item_list)
                    if self.is_space_big_enough(cube): 
                        return cube 
        
        return max(cubes)
        

    def downscale(self, lz): 
        """
        To reduce complexity in unoccupied space calculation the resolution is being down scaled. 
        To Achieve the biggest possible downscale for every layout the new pixels of the grid are build by intersection of items on the 2D Grid. 
        See Example scheme    X denotes an item: 
         _____________________
        |__|___|_____|_|XXXXXX|
        |___XXX|_____| |   |__|
        |___XXX|_____|XXXXX|  |
        |  |___|_____|XXXXX|__|
        |XX|___|_____|XXXXX|__|
        |XX|___|_____|_|___|__|

        """


        rect_list: List[List[Rectangle]] = list() 
        
        x_intersection_coordinates = set()
        y_intersection_coordinates = set()

        max_y, max_x = 800, 1200
        x_intersection_coordinates.add(0)
        y_intersection_coordinates.add(0)
        x_intersection_coordinates.add(max_x)
        y_intersection_coordinates.add(max_y)

        #create intersections 
        for item in self.item_list: 
            x_intersection_coordinates.add(item.lx)
            x_intersection_coordinates.add(item.rx)
            y_intersection_coordinates.add(item.ly)
            y_intersection_coordinates.add(item.ry)
        
        x_intersection_coordinates = sorted(list(x_intersection_coordinates))
        y_intersection_coordinates = sorted(list(y_intersection_coordinates))

        for ly, ry in zip(y_intersection_coordinates, y_intersection_coordinates[1:]): 
            inner_rect_list: List[Rectangle] = list()
            
            for lx, rx in zip(x_intersection_coordinates, x_intersection_coordinates[1:]): 
                rect = Rectangle(lx, ly, rx, ry)
                inner_rect_list.append(rect)
            
            rect_list.append(inner_rect_list) 

        #set value 
        rows = len(rect_list)
        cols = len(rect_list[0])
        for i in range(rows):
            for j in range(cols):
                if self.is_part_of_item(rect_list[i][j], lz): 
                    rect_list[i][j].value = 0 
        
        return rect_list
    

    def is_part_of_item(self, rect: Rectangle, lz:int) -> bool: 
        """
        Calculates if a given rectangle overlaps with any item in the placed items of this layer. 
        """

        for item in self.item_list: 
            x_included = rect.lx >= item.lx and rect.rx <= item.rx
            y_included = rect.ly >= item.ly and rect.ry <= item.ry 
            z_included =  item.rz > lz
            if x_included and y_included and z_included:
                return True 

        return False


    def largest_distinct_rectangles_in_heightmap(self, slice): 
        """
        Calculates all unoccupied consecutive distinct pixel groups of a given 2D slice of this layer.
        """

        # Initialize heights array for histogram representation
        rows = len(slice)
        cols = len(slice[0])
        heights = [0] * cols
        rects: List['Rectangle'] = list()
        
        for i in range(rows):
                # Update histogram heights for this row
                for j in range(cols):
                    if slice[i][j].value == 1:
                        heights[j] += 1
                    else:
                        heights[j] = 0

                # Largest rectangle in histogram "heights"
                stack = []
                extended = heights + [0]  # sentinel to flush the stack

                for j in range(cols + 1):
                    while stack and extended[j] < extended[stack[-1]]:
                        h_idx = stack.pop()
                        h = extended[h_idx]

                        # Determine width bounds
                        left = stack[-1] + 1 if stack else 0
                        right = j - 1

                        lx = slice[i - h + 1][left].lx
                        ly = slice[i - h + 1][left].ly
                        rx = slice[i][right].rx
                        ry = slice[i][right].ry
                        new_rect = Rectangle(lx, ly, rx, ry)

                        is_new_rect_distinct = True
                        for old_rect in rects: 
                            if old_rect.is_included(new_rect): 
                                is_new_rect_distinct = False
                        
                        if is_new_rect_distinct: 
                            rects.append(new_rect)

                        for x, old_rect in enumerate(rects): 
                            if old_rect.is_included(new_rect): 
                                rects[x] = max(new_rect, old_rect)

                    stack.append(j)
        return rects
    

    def pick_items(self, empty_space: Simple_space) -> bool: 
        """
        Place multiple items.
        Current implementation allows for up to one items being placed after another before next free space caluclation is necessary.
        Returned boolean indicates placement success.
        """

        #find all in cataloge that are smaller than empty space left: 
        fitting_items = [item for item in self.item_catalog if ((item.length <= empty_space.length and item.width <= empty_space.width) or (item.width <= empty_space.length and item.length <= empty_space.width)) and item.height <= empty_space.height]

        if len(fitting_items) == 0: 
            return True
        
        #pick biggest fitting item and apply coordinate shift 
        item: Item = max(fitting_items)
        rotate = self.need_to_rotate_item(item, empty_space)
        id = self.next_id
        lx = item.lx + empty_space.lx if not rotate else item.ly + empty_space.lx 
        ly = item.ly + empty_space.ly if not rotate else item.lx + empty_space.ly
        lz = item.lz + empty_space.lz 
        rx = item.rx + empty_space.lx if not rotate else item.ry + empty_space.lx
        ry = item.ry + empty_space.ly if not rotate else item.rx + empty_space.ly
        rz = item.rz + empty_space.lz
        weight = item.weight
        new_item = Item(id, lx, ly, lz, rx, ry, rz, weight)

        self.correct_item_z_position(new_item)

        self.item_list.append(new_item)
        #self.placed_items.append(new_item)
        self.item_catalog.remove(item)
        self.next_id = self.next_id + 1
        return False
    

    def correct_item_z_position(self, item: Item):
        """
        Calculates z support for this item: if 0 then translate item downward till z support is achieved. 
        """

        if item.lz == 0: 
            return 
        
        z_overlap_list = list()
        for placed_item in self.item_list: 
            if item.has_z_overlap(placed_item): 
                z_overlap_list.append(placed_item) 
        
        for placed_item in z_overlap_list: 
            if item.lz == placed_item.rz or (placed_item.rz < item.lz < placed_item.rz + 2): 
                return 
            
        if len(z_overlap_list) == 0: 
            height = item.rz - item.lz
            item.lz = 0
            item.rz = item.lz + height   
            return  
        
        max_rz = max(placed_item.rz for placed_item in z_overlap_list)
        height = item.rz - item.lz
        item.lz = max_rz 
        item.rz = item.lz + height
        
        return 


    def need_to_rotate_item(self, item: Item, empty_space: Simple_space): 
        """
        Selected space is guaranteed to be big enough for selected item, however it may occur that the item needs to be rotated in order to fit. 
        Method rotates items if neccessary. 
        Only ortation arount the z-axis is allowed. 
        """

        #if it doesnt fit rotated it may not be rotated as we know the space is big enough for at least one 
        rotation_prohibited = (item.width > empty_space.length or item.length > empty_space.width)

        if rotation_prohibited: 
            return False
        
        #if it doesnt fit normally it needs to be rotated as we know the space is big enough for at least one 
        rotation_needed = (item.length > empty_space.length or item.width > empty_space.width)

        if rotation_needed: 
            return True 

        #choose orientation that generates the biggest possible rectangle in the remaining space
        rotated_rect_1 = Rectangle(empty_space.lx, item.rx, empty_space.rx, empty_space.ry)
        rotated_rect_2 = Rectangle(item.ry, empty_space.ly, empty_space.rx, empty_space.ry)
        not_rotated_rect_1 = Rectangle(empty_space.lx, item.ry, empty_space.rx, empty_space.ry)
        not_rotated_rect_2 = Rectangle(item.rx, empty_space.ly, empty_space.rx, empty_space.ry)

        rotation_wanted = max(rotated_rect_1, rotated_rect_2) > max(not_rotated_rect_1, not_rotated_rect_2)

        return rotation_wanted


    def is_space_big_enough(self, empty_space: Simple_space) -> bool: 
        """
        Calculates all items from the not yet placed items that are small enought to fit in the selecet empty space.
        Return value indicates whether fitting items were found or not. 
        """

        fitting_items = [item for item in self.item_catalog if ((item.length <= empty_space.length and item.width <= empty_space.width) or (item.width <= empty_space.length and item.length <= empty_space.width)) and item.height <= empty_space.height]

        if len(fitting_items) > 0: 
            return True
        
        return False


    def generate_random_layer_height_within_bound(self, offset_height, item_catalog,  weights = [0.10, 0.20, 0.70]) -> int: 
        """
        Generates a layer height by random sampling within the LAYER_DIMENSIONS based on weight distribution to favor higher layers 
        as to many small layers lead to worse pallet outcomes but to few hinder diversity 
        """
        
        upper_bound = LAYER_DIMENSIONS["max_height"]
        lower_bound = LAYER_DIMENSIONS["min_height"]

        if upper_bound < lower_bound:
            return upper_bound

        if offset_height + lower_bound >= LAYER_DIMENSIONS["max_height"]: 
            return LAYER_DIMENSIONS["max_height"] - offset_height

        first_third = int((upper_bound - lower_bound) * (1/2))
        second_third = int((upper_bound - lower_bound) * (6/8))
        subranges = [
            (lower_bound, lower_bound + first_third),   # range 0–10
            (lower_bound + first_third + 1, lower_bound + second_third),  # range 11–20
            (lower_bound + second_third + 1, upper_bound)   # range 21–30
        ]

        if len(item_catalog) < 50:
            weights = [0.50, 0.50, 0.00]

        if len(item_catalog) > 50:
            weights = [0.0, 0.50, 0.50]

        if len(item_catalog) > 60:
            weights = [0.0, 0.15, 0.85]


        # Pick the subrange based on weights
        low, high = random.choices(subranges, weights=weights, k=1)[0]
        # Pick number inside selected subrange
        height = random.randint(low, high)

        if offset_height + height >= LAYER_DIMENSIONS["max_height"]: 
            return  LAYER_DIMENSIONS["max_height"] - offset_height
        
        return height


class Pallet_generator(): 
    """
    Class that generates the layout of a single pallet based on a given order (list of given items to be placed). 
    Generates layers of variable height to be filled, filles a layer till its considered full
    then proceeds with the next until no further item can be placed either because the list of remaining items is empty 
    or the pallet volume is used up. 
    """

    def __init__(self, pallet_id, item_order: List[Item]): 
        #layer_list: List[Layer_generator] = list()
        placed_items: Set[Item] = set()
        remaining_order = sorted(item_order)
        next_item_id = 0

        #the Layer_generator will shift items it places from remaining order to placed_items
        #the pallet_heihgt is the accumulated height of all layers beneath the next layer
        pallet_height = 0
        while len(remaining_order) > 0:
            Layer_generator(remaining_order, placed_items, pallet_height, next_item_id)
            pallet_height = max(item.rz for item in placed_items)
        
        return Pallet(pallet_id, list(placed_items))


class Pallet_list_generator(): 
    """
    Class that loads the item-catalog an generates orders containing 40-70 items.
    Generates a pallet layout for each order by using the Pallet_generator class.
    """

    def __init__(self):
        return


    def load_item_catalog(self) -> List[Item]: 
        """
        Loads the entire item-catalog from json and seperates the items in their size-modifier categories.
        """

        item_catalog = {}
        
        output_file = (
            pathlib.Path(__file__).resolve().parent.parent / "Jsons" / "Items" / "item_catalog.json"
        )

        with open(output_file) as f:
            json = json.load(f)

        for category, items in json.items():
            for item_data in items:
                item_catalog.setdefault(category, []).append(
                    Item(
                        -1, 0, 0, 0,
                        item_data["length"],
                        item_data["width"],
                        item_data["height"],
                        item_data["weight"]
                    )
                )

        return item_catalog


    def generate_random_order(self) -> List[Item]: 
        """
        Generates a order of random items from the given item-catalog. 
        Ordersizes range form 48 - 70 items.
        Items of each category a random sampled based on modifiers.  
        """

        order = list()
        item_catalog = self.load_item_catalog()
    
        #sum has to be num_items
        num_small_items = random.randint(int(8), int(12))
        num_tall_items = random.randint(int(8), int(13))
        num_high_items = random.randint(int(7), int(8))
        num_medium_items =  random.randint(int(15), int(20))
        num_flat_items = random.randint(int(6), int(11))
        num_long_items = random.randint(int(4), int(6))

        order += random.sample(item_catalog["medium"], num_medium_items)
        order += random.sample(item_catalog["tall"], num_tall_items)
        order += random.sample(item_catalog["high"], num_high_items)
        order += random.sample(item_catalog["flat"], num_flat_items)
        order += random.sample(item_catalog["small"], num_small_items)
        order += random.sample(item_catalog["long"], num_long_items)

        return order


    def generate_pallet_list(self, pallet_count = 1000, save_to_json = True, save_to_single_json = True) -> List[Pallet]: 
        """
        Generates a list of pallet_count items and saves them either to a single json or to invidual jsons based on given parameters.
        Execution of pallet generation is parallelized. 
        """
        
        pallet_list: List[Pallet] = list()
        
        for i in tqdm(range(0, pallet_count)):
            pallet_ids = range(i * 1, (i+1) * 1)

        with Pool() as pool: 
            for pallet in tqdm(pool.imap_unordered(self.generate_pallet, pallet_ids), total=len(pallet_ids)):
                pallet_list.append(pallet)
                pass
        
        if save_to_json: 
            if save_to_single_json: 
                for pallet in pallet_list: 
                    self.save_pallet_to_json(pallet)
            else: 
                self.save_pallets_to_json(pallet_list)
        
        return pallet_list


    def generate_pallet(self, pallet_id) -> Pallet: 
        """
        Generates a single pallet layout by first generating a random order of items
        and placing items from that order on the pallet until either volum is used up or remainig item list is empty. 
        """

        order = self.generate_random_order() 
        pallet = Pallet_generator(pallet_id, order) 

        return pallet 


    def save_pallet_to_json(self, pallet: Pallet): 
        """
        Saves a single gegenerated pallet to a json file named after the pallets id. 
        """
    
        file_name = f"pallet_{pallet.id}.json"
        output_file = (
            pathlib.Path(__file__).resolve().parent.parent / "Jsons" / "Pallets" / file_name
        )

        with open(output_file, "w") as file:
            json.dump(pallet.to_json(), file, indent=4)

        return 


    def save_pallets_to_json(self, pallet_list: List[Pallet]):
        """
        Saves a list of generated pallets to a json file named after the lowest pallet id - highest pallet id of the list.
        """

        pallet_list = sorted(pallet_list, key=lambda pallet: pallet.id)
        file_name = f"pallet_{pallet_list[0].id}_{pallet_list[-1].id}.json"
        output_file = (
            pathlib.Path(__file__).resolve().parent.parent / "Jsons" / "Pallets" / file_name
        )

        pallets_json = {}
        for pallet in pallet_list:             
            pallets_json.setdefault("pallets", []).append(pallet.to_json())

        with open(output_file, "w") as file:
            json.dump(pallets_json, file, indent=4)

        return
    
  
if __name__ == "__main__":
    
    generator = Pallet_list_generator()
    generator.generate_pallet_list(1000, True, True)


