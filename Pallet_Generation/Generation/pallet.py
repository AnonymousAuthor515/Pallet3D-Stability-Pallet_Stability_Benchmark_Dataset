from typing import List
from item import Item

class Pallet():
    """
    The class Pallet represents a EUR-Pallet loading unit containing a list of placed Item instances. It is defined by its id, its dimensions (length, width, height) and a list of items placed upon it.
    """

    def __init__(self, id, item_list: List["Item"]):
        self.id = id
        
        self.items : List['Item'] = item_list
        self.max_height = max(item.rz for item in self.items)

        self.length = 1200
        self.width = 800
        self.height = 2000


    @classmethod
    def from_json(cls, pallet_json):
        """
        Translates the json format of an pallet back to the runtime model
        """
        
        item_list: List[Item] = list()

        for item in pallet_json["items"]: 
            item_list.append(Item.from_json(item))

        return cls(pallet_json["id"], item_list)


    def get_tuple(self): 
        """
        Returns a tuple representation of the pallet containing the tuple representation of every item on it. 
        """

        item_list = [item.get_tuple() for item in self.items]
        return (self.id, item_list)


    def to_json(self): 
        """
        Translates the pallet into a json format.
        """

        item_json = []
        for item in self.items: 
            item_json.append(item.to_json())
        
        pallet_json = {}
        pallet_json["id"] = self.id
        pallet_json["item_count"] = len(self.items)
        pallet_json["items"] = item_json

        return pallet_json

    

