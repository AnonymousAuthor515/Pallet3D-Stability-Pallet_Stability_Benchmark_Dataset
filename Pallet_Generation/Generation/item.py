from typing import List, Set

class Item():
    """
    The class Item is a presentation of a real world item defined by its id, two points (front-left-lower point and back-right-upper point) and its weight
    """
    

    def __init__(self, id=0, lx=0, ly=0, lz=0, rx=0, ry=0, rz=0, weight=0):
        self.id = id

        self.lx : int = min(lx, rx)
        self.ly : int = min(ly, ry)
        self.lz : int = min(lz, rz)
        self.rx : int = max(rx, lx)
        self.ry : int = max(ry, ly)
        self.rz : int = max(rz, lz)

        self.length : int = abs(self.rx - self.lx)
        self.width : int = abs(self.ry - self.ly)
        self.height : int = abs(self.rz - self.lz)
        self.volume = self.get_volume()

        self.weight : float = weight 

        self.items_below: Set['Item'] = set()
        self.items_intersecting_z_shadow: List['Item'] = list()
 

    @classmethod
    def from_json(cls, item_json):
        """
        Translates the json format of an item back to the runtime model
        """
        
        return cls(item_json["id"], item_json["lx"], item_json["ly"], item_json["lz"], item_json["rx"], item_json["ry"], item_json["rz"], item_json["weight"])


    def has_items_above(self, item_list: List['Item']): 
        """
        Checks whether, for a given Layout an item has other items above it
        """

        for item in item_list: 
            if self.has_z_overlap(item) and item.lz >= self.rz: 
                return True


    def get_center_point(self): 
        """
        Return the geometrical center point of the item
        """

        c_x = self.lx + 0.5 * self.length
        c_y = self.ly + 0.5 * self.width
        c_z = self.lz + 0.5 * self.height

        return c_x, c_y, c_z


    def get_surface_support(self, item_list: List['Item']): 
        """
        calculates the percentual support of the bottom surface of a given item in the given layout. 
        Items with z == 0 are defined to have perfect support. 
        Items count as supported if they have an overlap with other items in x and y coordinates and are less than "threshold" mm above the supporting items.
        """

        if self.lz == 0: 
            return 100
        
        supporting_area = 0
        threshold = 5
        for item in item_list: 
            if self.has_z_overlap(item) and (item.rz <= self.lz <= item.rz + threshold): 
                lx = max(self.lx, item.lx)
                ly = max(self.ly, item.ly)
                rx = min(self.rx, item.rx)
                ry = min(self.ry, item.ry)

                intersection_area = (rx - lx) * (ry - ly) 
                supporting_area += intersection_area
        
        return (supporting_area / (self.length * self.width)) * 100


    def recalculate_measurements(self): 
        """
        Updates the measurements of a given item after its defining points have been changed. 
        Necessary for item rotation for example.
        """

        self.length : int = abs(self.rx - self.lx)
        self.width : int = abs(self.ry - self.ly)
        self.height : int = abs(self.rz - self.lz)
        self.volume = self.get_volume()


    def has_z_overlap(self, other: 'Item') -> bool: 
        """
        Checks whether two given items have an overlap in ther x/y dimensions.
        """
        
        # If one is completely to the left of the other
        if self.rx <= other.lx or other.rx <= self.lx: 
            return False

        # If one is completely below the other
        if self.ry <= other.ly or other.ry <= self.ly: 
            return False

        return True


    def get_volume(self) -> float:
        """
        returns the volume of a given item.
        """

        return self.length * self.width * self.height


    def get_tuple(self) -> List[int]: 
        """
        Returns a tuple representation of the items defining features.
        """

        return [self.id, self.lx, self.ly, self.lz, self.length, self.width, self.height, self.weight]
    

    def to_catalog_json(self): 
        """
        Translates the item into the json format used for the item catalog. 
        As items in the catalog are not placed in a layout the placement coordinates are omitted and the item is only represented by its length, width, height and weight. 
        """

        item_json = {}
        item_json["length"] = self.length
        item_json["width"] = self.width
        item_json["height"] = self.height
        item_json["weight"] = self.weight

        return item_json
    

    def to_json(self): 
        """
        Translates the item into the json format used in pallet layouts. 
        """

        item_json = {}
        item_json["lx"] = self.lx
        item_json["ly"] = self.ly
        item_json["lz"] = self.lz
        item_json["rx"] = self.rx
        item_json["ry"] = self.ry
        item_json["rz"] = self.rz
        item_json["id"] = self.id
        item_json["weight"] = self.weight

        return item_json
    
    
    def __lt__(self, other: "Item"): 
        """
        Comperator that returns if a given item is greater or smaller than another item by volume.
        """
        
        return self.volume < other.volume