import numpy as np
import pandas as pd
import pathlib
import json
import math 
from typing import Dict, List
from Pallet_Generation.Generation.item import Item
from Pallet_Generation.Generation.pallet import Pallet


class BedBppKPIEvaluator:
    """
    BED-BPP Benchmark: KPI Evaluator (Updated with BinPackingEvaluator KPIs)
    Implements comprehensive KPIs from BinPackingEvaluator for better packing evaluation.
    """

    def __init__(self, pallet: Pallet):
        """
        Args:
            pallet: Pallet whose kpis are to be calculated
        """

        self.pallet = pallet 

        # Initialize KPI calculators from BinPackingEvaluator
        # Import classes from the attached file (they're already in the same file)
        
        self.height_width_ratio = HeightWidthRatio(pallet)
        self.relative_density = RelativeDensity(pallet)
        self.absolute_density = AbsoluteDensity(pallet)
        self.side_support = SideSupport(pallet)
        self.side_support_most_outer_items_fully_supported = SideSupportMostOuterItemsFullySupported(pallet)
        self.surface_support = SurfaceSupport(pallet)
        self.minimal_surface_support = MinimalSurfaceSupport(pallet)
        self.center_of_gravity_2d = CenterOfGravity2D(pallet)
        self.center_of_gravity_3d = CenterOfGravity3D(pallet)
        self.pillar_score = PillarScore(pallet, 
            base_support_threshold=1.01,
            get_side_support=self.side_support.get_item_scores, 
            get_surface_support=self.surface_support.get_item_scores
        )

    def evaluate(self) -> Dict[str, float]:
        """
        Evaluate all KPIs using BinPackingEvaluator methodology.
        """
        # Calculate individual KPI scores
        height_width_ratio_score = self.height_width_ratio.calculate()
        absolute_density_score = self.absolute_density.calculate()
        relative_density_score = self.relative_density.calculate()
        side_support_score = self.side_support.calculate()
        self.side_support_most_outer_items_fully_supported_score = self.side_support_most_outer_items_fully_supported.calculate()
        surface_support_score = self.surface_support.calculate()
        minimal_surface_support_score = self.minimal_surface_support.calculate()
        cog_2d_score = self.center_of_gravity_2d.calculate()
        cog_3d_score = self.center_of_gravity_3d.calculate()
        pillar_score = self.pillar_score.calculate()
        
        # Construct result dictionary
        result = {
            'pallet_id': self.pallet.id,
            'absolute_density': absolute_density_score,            
            'relative_density': relative_density_score,        
            'side_support': side_support_score,
            'side_support_most_outer_fully_supported': self.side_support_most_outer_items_fully_supported_score,
            'surface_support': surface_support_score,
            "min_surface_support": minimal_surface_support_score,
            'center_of_gravity_2d': cog_2d_score,
            'center_of_gravity_3d': cog_3d_score,
            'height_width_ratio': height_width_ratio_score,
            'pillar_score': pillar_score,
        }
        
        return result


class AbsoluteDensity:
    """
    Class for calculating the Absolute Density KPI.
    
    This KPI measures how effectively the total bin volume is utilized by
    comparing the total volume of all items to the bin volume.
    
    A score of 1.0 indicates perfect volume utilization (bin is completely filled).
    A score of 0.0 indicates empty bin.
    """
    
    def __init__(self, pallet:Pallet):
        """
        Args:
            pallet: Pallet whose kpis are to be calculated
        """
        self.pallet = pallet
        
    def calculate(self) -> float:
        """
        Calculate the Absolute Density KPI
        """
        item_volume = 0
        # Calculate total volume of all items
        for item in self.pallet.items: 
            item_volume += item.get_volume()
        
        # Calculate bin volume
        pallet_volume = self.pallet.length * self.pallet.width * self.pallet.height
        
        absolute_density = item_volume / pallet_volume
        
        # Ensure the score is between 0 and 1
        return max(0.0, min(1.0, absolute_density))


class RelativeDensity:
    """
    Class for calculating the Relative Density KPI.
    
    This KPI measures how effectively space is utilized by comparing 
    the actual volume of packed items to the volume of the utilized space.
    
    A score of 1.0 indicates perfect packing density.
    A score approaching 0.0 indicates poor space utilization.
    """

    def __init__(self, pallet: Pallet):  
        """
        Args:
            pallet: Pallet whose kpis are to be calculated
        """
        self.pallet = pallet
        
    def calculate(self) -> float:
        """
        Calculate the Relative Density KPI

        Returns:
            float: Score between 0.0 and 1.0
        """
            
        item_volume = 0
        # Calculate total volume of all items
        for item in self.pallet.items: 
            item_volume += item.get_volume()
        
        # Calculate utilized space volume based on method
            utilized_volume = self._calculate_bounding_box_volume()
            
        # Relative density is the ratio of item volume to utilized volume
        density = item_volume / utilized_volume
        
        # Ensure result is between 0 and 1 (should naturally be, but safety check)
        return min(1.0, max(0.0, density))
    
    def _calculate_bounding_box_volume(self) -> float:
        """
        Calculate the volume of the axis-aligned bounding box containing all items
        """
        # Find the bounds of all packed items
        min_x = min(obj.lx for obj in self.pallet.items)
        max_x  = max(obj.rx for obj in self.pallet.items)

        min_y = min(obj.ly for obj in self.pallet.items)
        max_y  = max(obj.ry for obj in self.pallet.items)
        
        min_z = min(obj.lz for obj in self.pallet.items)
        max_z  = max(obj.rz for obj in self.pallet.items)
        
        # Calculate bounding box volume
        width = max_x - min_x
        length = max_y - min_y
        height = max_z - min_z
        
        return width * length * height


class CenterOfGravity2D:
    """
    Class for calculating the Center of Gravity 2D KPI.
    
    This KPI evaluates the relationship between the actual center of gravity
    in 2D space (X-Y plane) and the worst possible center of gravity.
    
    A score of 1.0 indicates optimal center of gravity (at bin center).
    A score of 0.0 indicates worst possible center of gravity (at corners).
    """
    
    def __init__(self, pallet: Pallet):  
        """
        Args:
            pallet: Pallet whose kpis are to be calculated
        """
        self.pallet = pallet
        
    def calculate(self) -> float:
        """
        Calculate the Center of Gravity 2D KPI

        Returns:
            float: Score between 0.0 and 1.0
        """
                
        # Calculate center of gravity
        total_mass = sum(obj.weight for obj in self.pallet.items)
           
        cog_x = sum(obj.get_center_point()[0] * obj.weight for obj in self.pallet.items) / total_mass
        cog_y = sum(obj.get_center_point()[1] * obj.weight for obj in self.pallet.items) / total_mass
        
        # Calculate ideal center of gravity (center of bin)
        ideal_x = self.pallet.length / 2
        ideal_y = self.pallet.width / 2
        
        # Calculate worst possible distance (from center to corner)
        worst_distance = np.sqrt(ideal_x**2 + ideal_y**2)
        
        # Calculate actual distance from ideal
        actual_distance = np.sqrt((cog_x - ideal_x)**2 + (cog_y - ideal_y)**2)
        
        # Normalize to 0-1 score (1 = perfect, 0 = worst)
        if worst_distance == 0:
            return 1.0
            
        score = 1.0 - (actual_distance / worst_distance)
        
        return max(0.0, min(1.0, score))
    

class CenterOfGravity3D:
    """
    Class for calculating the Center of Gravity 3D KPI.
    
    This KPI evaluates the relationship between the actual center of gravity
    in 3D space and the worst possible center of gravity.
    
    A score of 1.0 indicates optimal center of gravity (at bin center).
    A score of 0.0 indicates worst possible center of gravity (at corners).
    """
    
    def __init__(self, pallet: Pallet):  
        """
        Args:
            pallet: Pallet whose kpis are to be calculated
        """
        self.pallet = pallet
        
    def calculate(self) -> float:
        """
        Calculate the Center of Gravity 3D KPI
                
        Returns:
            float: Score between 0.0 and 1.0
        """
        # Calculate center of gravity
        total_mass = sum(obj.weight for obj in self.pallet.items)
                    
        cog_x = sum(obj.get_center_point()[0] * obj.weight for obj in self.pallet.items) / total_mass
        cog_y = sum(obj.get_center_point()[1] * obj.weight for obj in self.pallet.items) / total_mass
        cog_z = sum(obj.get_center_point()[2] * obj.weight for obj in self.pallet.items) / total_mass
        
        # Calculate ideal center of gravity (center of bin)
        ideal_x = self.pallet.length / 2
        ideal_y = self.pallet.width / 2
        ideal_z = self.pallet.height / 2

        # Calculate worst possible distance (from center to corner)
        worst_distance = np.sqrt(ideal_x**2 + ideal_y**2 + ideal_z**2)
        
        # Calculate actual distance from ideal
        actual_distance = np.sqrt((cog_x - ideal_x)**2 + (cog_y - ideal_y)**2 + (cog_z - ideal_z)**2)
        
        # Normalize to 0-1 score (1 = perfect, 0 = worst)
        if worst_distance == 0:
            return 1.0
            
        score = 1.0 - (actual_distance / worst_distance)
        
        return max(0.0, min(1.0, score))
    

class HeightWidthRatio:
    """
    Class for calculating the HeightWidthRatio KPI.
    
    This KPI evaluates how well tall items (with high height-to-base ratio) 
    are placed in stable positions (middle and bottom of bin).
    
    A score of 1.0 indicates optimal placement of tall items.
    A score of 0.0 indicates poor placement with tall items in unstable positions.
    """
    
    class ExpandedItem: 
        """
        Extension class for Item. 
        This class is not present in the original code and was added to integrate the code in the local data format.
        It is used to carry out all item wise calculations for the height-width-ratio. 
        """

        def __init__(self, item: Item, pallet: Pallet): 
            self.item = item
            self.base_area = item.width * item.length
            self.height_base_ratio = item.height / math.sqrt(self.base_area)
            self.normalized_ratio = item.height / math.sqrt(self.base_area)
            self.pallet_center_x = pallet.length / 2 
            self.pallet_center_y = pallet.width / 2
            self.center_x = item.get_center_point()[0]
            self.center_y = item.get_center_point()[1]
            self.center_z = item.get_center_point()[2]
            self.dist_from_center = math.sqrt((self.center_x - self.pallet_center_x) **2 + (self.center_y - self.pallet_center_y) **2)
            self.normalized_distance = 0
            self.normalized_center_z = self.center_z / pallet.height
            self.score = 0

        def update_normalized_ratio(self, max_ratio):
            self.normalized_ratio = self.height_base_ratio / max_ratio

        def update_normalized_distance(self, max_distance):
            self.normalized_ratio = self.dist_from_center / max_distance

        def calculate_score(self): 
            self.score = 1 - ( self.normalized_ratio * (0.7 * self.normalized_distance + 0.3 * self.normalized_center_z))


    def __init__(self, pallet: Pallet):  
        """
        Args:
            pallet: Pallet whose kpis are to be calculated
        """
        self.pallet = pallet
        
    def calculate(self) -> float:
        """
        Calculate the HeightWidthRatio KPI.
                
        Returns:
            float: Score between 0.0 and 1.0
        """
        expanded_items: List[HeightWidthRatio.ExpandedItem] = list()
        for item in self.pallet.items: 
            expanded_items.append(self.ExpandedItem(item, self.pallet))
        
        for item in expanded_items: 
            item.update_normalized_ratio(max(obj.height_base_ratio for obj in expanded_items))
            item.update_normalized_distance(max(obj.dist_from_center for obj in expanded_items))
            item.calculate_score()

        total_volume = sum(obj.item.get_volume() for obj in expanded_items)

        weighted_score = sum((obj.score * obj.item.get_volume()) / total_volume for obj in expanded_items)

        # Return normalized score between 0 and 1
        return max(0.0, min(1.0, weighted_score))
    

class SideSupport:
    """
    Class for calculating the Side Support KPI.
    
    This KPI measures how many sides of items are supported by adjacent items,
    ignoring the outer sides of the bin.
    
    A score of 1.0 indicates all item sides have support.
    A score of 0.0 indicates no side support at all.
    """
    
    def __init__(self, pallet: Pallet, min_overlap_ratio: float = 0.2):
        """
        Args:
            pallet: Pallet of which the kpis are to be calculated
            min_overlap_ratio: Minimum ratio of overlap required to consider sides supported
        """
        self.pallet = pallet
        self.min_overlap_ratio = min_overlap_ratio
        
    def calculate(self) -> float:
        """
        Calculate the Side Support KPI
                
        Returns:
            float: Score between 0.0 and 1.0
        """

        total_sides = 0
        supported_sides = 0

        for item in self.pallet.items: 
            x1, y1, z1 = item.lx, item.ly, item.lz
            x2, y2, z2 = item.rx, item.ry, item.rz
            
            # Define the 4 sides of the item as (axis, position, start1, end1, start2, end2)
            sides = [
                # Left side face (x-axis, left)
                ('x', x1, y1, y2, z1, z2),
                # Right side face (x-axis, right)
                ('x', x2, y1, y2, z1, z2),
                # Front side face (y-axis, front)
                ('y', y1, x1, x2, z1, z2),
                # Back side face (y-axis, back)
                ('y', y2, x1, x2, z1, z2)
            ]            

         # Check each side
            for side_axis, side_pos, start1, end1, start2, end2 in sides:
                # Skip sides that are at bin boundaries
                if ((side_axis == 'x' and (side_pos == 0 or side_pos == self.pallet.length)) or
                    (side_axis == 'y' and (side_pos == 0 or side_pos == self.pallet.width))):
                    continue
                
                # Calculate side area
                if side_axis == 'x':
                    side_area = (end1 - start1) * (end2 - start2)  # length * height
                else:  # y-axis
                    side_area = (end1 - start1) * (end2 - start2)  # width * height
                
                total_sides += 1
                
                # Check if this side has support from other items
                supported_area = 0

                for other_item in self.pallet.items: 

                    if item.id == other_item.id: 
                        continue

                    # Calculate other item coordinates
                    ox1, oy1, oz1 = other_item.lx, other_item.ly, other_item.lz
                    ox2, oy2, oz2 = other_item.rx, other_item.ry, other_item.rz
                    
                    # Check if other item is adjacent to this side
                    if side_axis == 'x':
                        if side_pos == x1:  # Left side
                            if abs(ox2 - x1) < 0.1:  # Other item's right side touches this item's left side
                                # Calculate overlap area
                                y_overlap = max(0, min(y2, oy2) - max(y1, oy1))
                                z_overlap = max(0, min(z2, oz2) - max(z1, oz1))
                                supported_area += y_overlap * z_overlap
                        else:  # Right side
                            if abs(ox1 - x2) < 0.1:  # Other item's left side touches this item's right side
                                # Calculate overlap area
                                y_overlap = max(0, min(y2, oy2) - max(y1, oy1))
                                z_overlap = max(0, min(z2, oz2) - max(z1, oz1))
                                supported_area += y_overlap * z_overlap
                    else:  # y-axis
                        if side_pos == y1:  # Front side
                            if abs(oy2 - y1) < 0.1:  # Other item's back side touches this item's front side
                                # Calculate overlap area
                                x_overlap = max(0, min(x2, ox2) - max(x1, ox1))
                                z_overlap = max(0, min(z2, oz2) - max(z1, oz1))
                                supported_area += x_overlap * z_overlap
                        else:  # Back side
                            if abs(oy1 - y2) < 0.1:  # Other item's front side touches this item's back side
                                # Calculate overlap area
                                x_overlap = max(0, min(x2, ox2) - max(x1, ox1))
                                z_overlap = max(0, min(z2, oz2) - max(z1, oz1))
                                supported_area += x_overlap * z_overlap
                
                # Calculate support ratio for this side
                support_ratio = supported_area / side_area if side_area > 0 else 0
                
                # Count side as supported if enough of it is covered
                if support_ratio >= self.min_overlap_ratio:
                    supported_sides += 1
        
        # Calculate overall side support score
        if total_sides == 0:
            return 0.0
            
        return supported_sides / total_sides
    
    def get_item_scores(self) -> pd.DataFrame:
        """
        Return side support scores for individual items
            
        Returns:
            DataFrame with item identifiers and side support scores
        """

        results = []
        
        for item in self.pallet.items: 
            x1, y1, z1 = item.lx, item.ly, item.lz
            x2, y2, z2 = item.rx, item.ry, item.rz
            
            # Define the 4 sides of the item as (axis, position, start1, end1, start2, end2)
            sides = [
                # Left side face (x-axis, left)
                ('x', x1, y1, y2, z1, z2),
                # Right side face (x-axis, right)
                ('x', x2, y1, y2, z1, z2),
                # Front side face (y-axis, front)
                ('y', y1, x1, x2, z1, z2),
                # Back side face (y-axis, back)
                ('y', y2, x1, x2, z1, z2)
            ]            
            
            # Check each side
            total_sides = 0
            supported_sides = 0
            
            for side_axis, side_pos, start1, end1, start2, end2 in sides:
                # Skip sides that are at bin boundaries
                if ((side_axis == 'x' and (side_pos == 0 or side_pos == self.pallet.width)) or
                    (side_axis == 'y' and (side_pos == 0 or side_pos == self.pallet.length))):
                    continue
                
                # Calculate side area
                if side_axis == 'x':
                    side_area = (end1 - start1) * (end2 - start2)  # length * height
                else:  # y-axis
                    side_area = (end1 - start1) * (end2 - start2)  # width * height
                
                total_sides += 1
                
                # Check if this side has support from other items
                supported_area = 0
                
                for other_item in self.pallet.items: 

                    if item.id == other_item.id: 
                        continue

                    # Calculate other item coordinates
                    ox1, oy1, oz1 = other_item.lx, other_item.ly, other_item.lz
                    ox2, oy2, oz2 = other_item.rx, other_item.ry, other_item.rz
                    
                    # Check if other item is adjacent to this side
                    if side_axis == 'x':
                        if side_pos == x1:  # Left side
                            if abs(ox2 - x1) < 0.1:  # Other item's right side touches this item's left side
                                # Calculate overlap area
                                y_overlap = max(0, min(y2, oy2) - max(y1, oy1))
                                z_overlap = max(0, min(z2, oz2) - max(z1, oz1))
                                supported_area += y_overlap * z_overlap
                        else:  # Right side
                            if abs(ox1 - x2) < 0.1:  # Other item's left side touches this item's right side
                                # Calculate overlap area
                                y_overlap = max(0, min(y2, oy2) - max(y1, oy1))
                                z_overlap = max(0, min(z2, oz2) - max(z1, oz1))
                                supported_area += y_overlap * z_overlap
                    else:  # y-axis
                        if side_pos == y1:  # Front side
                            if abs(oy2 - y1) < 0.1:  # Other item's back side touches this item's front side
                                # Calculate overlap area
                                x_overlap = max(0, min(x2, ox2) - max(x1, ox1))
                                z_overlap = max(0, min(z2, oz2) - max(z1, oz1))
                                supported_area += x_overlap * z_overlap
                        else:  # Back side
                            if abs(oy1 - y2) < 0.1:  # Other item's front side touches this item's back side
                                # Calculate overlap area
                                x_overlap = max(0, min(x2, ox2) - max(x1, ox1))
                                z_overlap = max(0, min(z2, oz2) - max(z1, oz1))
                                supported_area += x_overlap * z_overlap
                
                # Calculate support ratio for this side
                support_ratio = supported_area / side_area if side_area > 0 else 0
                
                # Count side as supported if enough of it is covered
                if support_ratio >= self.min_overlap_ratio:
                    supported_sides += 1
            
            # Calculate side support score for this item
            item_score = supported_sides / total_sides if total_sides > 0 else 0
            
            results.append({
                'item': item.id,
                'side_support_score': item_score
            })
        
        return pd.DataFrame(results)


class SideSupportMostOuterItemsFullySupported:
    """
    Class for calculating the Side Support KPI.
    
    This KPI measures how many sides of items are supported by adjacent items,
    most outer items are counted as fully supported.
    
    A score of 1.0 indicates all item sides have support.
    A score of 0.0 indicates no side support at all.
    """
    
    def __init__(self, pallet: Pallet, min_overlap_ratio: float = 0.2):
        """
        Args:
            pallet: Pallet of which the kpis are to be calculated
            min_overlap_ratio: Minimum ratio of overlap required to consider sides supported
        """
        self.pallet = pallet
        self.min_overlap_ratio = min_overlap_ratio
        
    def calculate(self) -> float:
        """
        Calculate the Side Support KPI
                
        Returns:
            float: Score between 0.0 and 1.0
        """

        total_sides = 0
        supported_sides = 0

        for item in self.pallet.items: 
            x1, y1, z1 = item.lx, item.ly, item.lz
            x2, y2, z2 = item.rx, item.ry, item.rz
            
            # Define the 4 sides of the item as (axis, position, start1, end1, start2, end2)
            sides = [
                # Left side face (x-axis, left)
                ('x', x1, y1, y2, z1, z2),
                # Right side face (x-axis, right)
                ('x', x2, y1, y2, z1, z2),
                # Front side face (y-axis, front)
                ('y', y1, x1, x2, z1, z2),
                # Back side face (y-axis, back)
                ('y', y2, x1, x2, z1, z2)
            ]            

         # Check each side
            for side_axis, side_pos, start1, end1, start2, end2 in sides:
                # Skip sides that are at bin boundaries
                if ((side_axis == 'x' and (side_pos == 0 or side_pos == self.pallet.length)) or
                    (side_axis == 'y' and (side_pos == 0 or side_pos == self.pallet.width))):
                    continue
                
                # Calculate side area
                if side_axis == 'x':
                    side_area = (end1 - start1) * (end2 - start2)  # length * height
                else:  # y-axis
                    side_area = (end1 - start1) * (end2 - start2)  # width * height
                
                total_sides += 1
                
                # Check if this side has support from other items
                supported_area = 0


                if side_pos == x1: 
                    is_most_outer_side = True
                    for other_item in self.pallet.items: 

                        if item.id == other_item.id: 
                            continue

                        # Calculate other item coordinates
                        ox1, oy1, oz1 = other_item.lx, other_item.ly, other_item.lz
                        ox2, oy2, oz2 = other_item.rx, other_item.ry, other_item.rz

                        if ox2 < x1: 
                            y_overlap = max(0, min(y2, oy2) - max(y1, oy1))
                            z_overlap = max(0, min(z2, oz2) - max(z1, oz1))     
                            overlap = y_overlap * z_overlap
                            if overlap > 0: 
                                is_most_outer_side = False
                                if abs(ox2 - x1) < 2:  # Other item's right side touches this item's left side
                                # Calculate overlap area
                                    supported_area += overlap

                    #most outer sides count as completely supported as they are by default as supported as they possible can be
                    if is_most_outer_side == True: 
                        supported_area += (y2 - y1) * (z2 - z1)


                if side_pos == x2: 
                    is_most_outer_side = True
                    for other_item in self.pallet.items: 

                        if item.id == other_item.id: 
                            continue

                        # Calculate other item coordinates
                        ox1, oy1, oz1 = other_item.lx, other_item.ly, other_item.lz
                        ox2, oy2, oz2 = other_item.rx, other_item.ry, other_item.rz

                        if ox1 > x2: 
                            y_overlap = max(0, min(y2, oy2) - max(y1, oy1))
                            z_overlap = max(0, min(z2, oz2) - max(z1, oz1))     
                            overlap = y_overlap * z_overlap
                            if overlap > 0: 
                                is_most_outer_side = False
                                if abs(ox1 - x2) < 2:  # Other item's right side touches this item's left side
                                # Calculate overlap area
                                    supported_area += overlap

                    #most outer sides count as completely supported as they are by default as supported as they possible can be
                    if is_most_outer_side == True: 
                        supported_area += (y2 - y1) * (z2 - z1)


                if side_pos == y1: 
                    is_most_outer_side = True
                    for other_item in self.pallet.items: 

                        if item.id == other_item.id: 
                            continue

                        # Calculate other item coordinates
                        ox1, oy1, oz1 = other_item.lx, other_item.ly, other_item.lz
                        ox2, oy2, oz2 = other_item.rx, other_item.ry, other_item.rz

                        if oy2 > y1: 
                            x_overlap = max(0, min(x2, ox2) - max(x1, ox1))
                            z_overlap = max(0, min(z2, oz2) - max(z1, oz1))    
                            overlap = x_overlap * z_overlap
                            if overlap > 0: 
                                is_most_outer_side = False
                                if abs(oy2 - y1) < 2:  # Other item's right side touches this item's left side
                                # Calculate overlap area
                                    supported_area += overlap

                    #most outer sides count as completely supported as they are by default as supported as they possible can be
                    if is_most_outer_side == True: 
                        supported_area += (x2 - x1) * (z2 - z1)

                        
                if side_pos == y2: 
                    is_most_outer_side = True
                    for other_item in self.pallet.items: 

                        if item.id == other_item.id: 
                            continue

                        # Calculate other item coordinates
                        ox1, oy1, oz1 = other_item.lx, other_item.ly, other_item.lz
                        ox2, oy2, oz2 = other_item.rx, other_item.ry, other_item.rz

                        if oy1 < y2: 
                            x_overlap = max(0, min(x2, ox2) - max(x1, ox1))
                            z_overlap = max(0, min(z2, oz2) - max(z1, oz1))    
                            overlap = x_overlap * z_overlap
                            if overlap > 0: 
                                is_most_outer_side = False
                                if abs(oy1 - y1) < 2:  # Other item's right side touches this item's left side
                                # Calculate overlap area
                                    supported_area += overlap

                    #most outer sides count as completely supported as they are by default as supported as they possible can be
                    if is_most_outer_side == True: 
                        supported_area += (x2 - x1) * (z2 - z1)
                
                # Calculate support ratio for this side
                support_ratio = supported_area / side_area if side_area > 0 else 0
                
                # Count side as supported if enough of it is covered
                if support_ratio >= self.min_overlap_ratio:
                    supported_sides += 1
        
        # Calculate overall side support score
        if total_sides == 0:
            return 0.0
        
            
        return supported_sides / total_sides
    

    def get_item_scores(self) -> pd.DataFrame:
        """
        Return side support scores for individual items
            
        Returns:
            DataFrame with item identifiers and side support scores
        """

        results = []
        
        for item in self.pallet.items: 
            x1, y1, z1 = item.lx, item.ly, item.lz
            x2, y2, z2 = item.rx, item.ry, item.rz
            
            # Define the 4 sides of the item as (axis, position, start1, end1, start2, end2)
            sides = [
                # Left side face (x-axis, left)
                ('x', x1, y1, y2, z1, z2),
                # Right side face (x-axis, right)
                ('x', x2, y1, y2, z1, z2),
                # Front side face (y-axis, front)
                ('y', y1, x1, x2, z1, z2),
                # Back side face (y-axis, back)
                ('y', y2, x1, x2, z1, z2)
            ]            
            
            # Check each side
            total_sides = 0
            supported_sides = 0
            
            for side_axis, side_pos, start1, end1, start2, end2 in sides:
                # Skip sides that are at bin boundaries
                if ((side_axis == 'x' and (side_pos == 0 or side_pos == self.pallet.length)) or
                    (side_axis == 'y' and (side_pos == 0 or side_pos == self.pallet.width))):
                    continue
                
                # Calculate side area
                if side_axis == 'x':
                    side_area = (end1 - start1) * (end2 - start2)  # length * height
                else:  # y-axis
                    side_area = (end1 - start1) * (end2 - start2)  # width * height
                
                total_sides += 1
                
                # Check if this side has support from other items
                supported_area = 0


                if side_pos == x1: 
                    is_most_outer_side = True
                    for other_item in self.pallet.items: 

                        if item.id == other_item.id: 
                            continue

                        # Calculate other item coordinates
                        ox1, oy1, oz1 = other_item.lx, other_item.ly, other_item.lz
                        ox2, oy2, oz2 = other_item.rx, other_item.ry, other_item.rz

                        if ox2 < x1: 
                            y_overlap = max(0, min(y2, oy2) - max(y1, oy1))
                            z_overlap = max(0, min(z2, oz2) - max(z1, oz1))     
                            overlap = y_overlap * z_overlap
                            if overlap > 0: 
                                is_most_outer_side = False
                                if abs(ox2 - x1) < 2:  # Other item's right side touches this item's left side
                                # Calculate overlap area
                                    supported_area += overlap

                    #most outer sides count as completely supported as they are by default as supported as they possible can be
                    if is_most_outer_side == True: 
                        supported_area += (y2 - y1) * (z2 - z1)


                if side_pos == x2: 
                    is_most_outer_side = True
                    for other_item in self.pallet.items: 

                        if item.id == other_item.id: 
                            continue

                        # Calculate other item coordinates
                        ox1, oy1, oz1 = other_item.lx, other_item.ly, other_item.lz
                        ox2, oy2, oz2 = other_item.rx, other_item.ry, other_item.rz

                        if ox1 > x2: 
                            y_overlap = max(0, min(y2, oy2) - max(y1, oy1))
                            z_overlap = max(0, min(z2, oz2) - max(z1, oz1))     
                            overlap = y_overlap * z_overlap
                            if overlap > 0: 
                                is_most_outer_side = False
                                if abs(ox1 - x2) < 2:  # Other item's right side touches this item's left side
                                # Calculate overlap area
                                    supported_area += overlap

                    #most outer sides count as completely supported as they are by default as supported as they possible can be
                    if is_most_outer_side == True: 
                        supported_area += (y2 - y1) * (z2 - z1)


                if side_pos == y1: 
                    is_most_outer_side = True
                    for other_item in self.pallet.items: 

                        if item.id == other_item.id: 
                            continue

                        # Calculate other item coordinates
                        ox1, oy1, oz1 = other_item.lx, other_item.ly, other_item.lz
                        ox2, oy2, oz2 = other_item.rx, other_item.ry, other_item.rz

                        if oy2 > y1: 
                            x_overlap = max(0, min(x2, ox2) - max(x1, ox1))
                            z_overlap = max(0, min(z2, oz2) - max(z1, oz1))    
                            overlap = x_overlap * z_overlap
                            if overlap > 0: 
                                is_most_outer_side = False
                                if abs(oy2 - y1) < 2:  # Other item's right side touches this item's left side
                                # Calculate overlap area
                                    supported_area += overlap

                    #most outer sides count as completely supported as they are by default as supported as they possible can be
                    if is_most_outer_side == True: 
                        supported_area += (x2 - x1) * (z2 - z1)

                        
                if side_pos == y2: 
                    is_most_outer_side = True
                    for other_item in self.pallet.items: 

                        if item.id == other_item.id: 
                            continue

                        # Calculate other item coordinates
                        ox1, oy1, oz1 = other_item.lx, other_item.ly, other_item.lz
                        ox2, oy2, oz2 = other_item.rx, other_item.ry, other_item.rz

                        if oy1 < y2: 
                            x_overlap = max(0, min(x2, ox2) - max(x1, ox1))
                            z_overlap = max(0, min(z2, oz2) - max(z1, oz1))    
                            overlap = x_overlap * z_overlap
                            if overlap > 0: 
                                is_most_outer_side = False
                                if abs(oy1 - y1) < 2:  # Other item's right side touches this item's left side
                                # Calculate overlap area
                                    supported_area += overlap

                    #most outer sides count as completely supported as they are by default as supported as they possible can be
                    if is_most_outer_side == True: 
                        supported_area += (x2 - x1) * (z2 - z1)
                
                # Calculate support ratio for this side
                support_ratio = supported_area / side_area if side_area > 0 else 0
                
                # Count side as supported if enough of it is covered
                if support_ratio >= self.min_overlap_ratio:
                    supported_sides += 1
            
            # Calculate side support score for this item
            item_score = supported_sides / total_sides if total_sides > 0 else 0
            
            results.append({
                'item': item.id,
                'side_support_score': item_score
            })
        
        return pd.DataFrame(results)


class SurfaceSupport:
    """
    Class for calculating the Surface Support KPI.
    
    This KPI measures if items have a solid base structure to stand on,
    either by sufficient bottom surface contact or stable corner support.
    
    A score of 1.0 indicates all items have optimal surface support.
    A score of 0.0 indicates poor surface support across all items.
    """
    
    def __init__(self, pallet: Pallet , min_surface_ratio: float = 0.5, corner_support_threshold: int = 3):
        """
        Args:
            pallet: The pallet whose kpis are to be calculated
            min_surface_ratio: Minimum ratio of bottom surface that needs support
            corner_support_threshold: Minimum number of corners that need support (out of 4)
        """
        self.pallet = pallet
        self.min_surface_ratio = min_surface_ratio
        self.corner_support_threshold = corner_support_threshold
        
    def calculate(self) -> float:
        """
        Calculate the Surface Support KPI
                
        Returns:
            float: Score between 0.0 and 1.0
        """
        # Track support scores for each item
        support_scores = []

        for item in sorted(self.pallet.items, key=lambda obj: obj.lz):
        
            # Skip items directly on the ground (they have perfect support)
            if abs(item.lz) == 0:
                support_scores.append(1.0)
                continue
            
            # Calculate item bottom surface coordinates
            x1, y1, z1 = item.lx, item.ly, item.lz
            x2, y2 = item.rx , item.ry
            bottom_area = item.width * item.length
            
            # Calculate the corners of the bottom face
            corners = [
                (x1, y1),  # bottom-left
                (x2, y1),  # bottom-right
                (x1, y2),  # top-left
                (x2, y2)   # top-right
            ]
            
            supported_corners = 0
            supported_area = 0
            
            # Check support from other items
            for other_item in sorted(
                (o_item for o_item in self.pallet.items if o_item.rz < item.lz),
                key=lambda obj: obj.rz,
            ):
                # Skip self or items above this one
                if other_item.id == item.id:
                    continue
                
                # Calculate other item top surface coordinates
                ox1, oy1 = other_item.lx, other_item.ly
                ox2, oy2 = other_item.rx, other_item.ry
                oz2 = other_item.rz
                
                # Check if other item's top is directly below this item's bottom
                if abs(oz2 - z1) < 2:
                    # Calculate overlap area
                    x_overlap = max(0, min(x2, ox2) - max(x1, ox1))
                    y_overlap = max(0, min(y2, oy2) - max(y1, oy1))
                    
                    if x_overlap > 0 and y_overlap > 0:
                        supported_area += x_overlap * y_overlap
                    
                    # Check if corners are supported
                    for cx, cy in corners:
                        if ox1 <= cx <= ox2 and oy1 <= cy <= oy2:
                            supported_corners += 1
            
            # Calculate support ratio
            area_ratio = supported_area / bottom_area if bottom_area > 0 else 0
            
            # Determine if item has sufficient support
            has_area_support = area_ratio >= self.min_surface_ratio
            has_corner_support = supported_corners >= self.corner_support_threshold
            
            if has_area_support or has_corner_support:
                # Calculate weighted score based on support type
                if has_area_support and has_corner_support:
                    score = 1.0  # Both types of support: perfect
                elif has_area_support:
                    score = area_ratio  # Area support: score based on coverage
                else:
                    score = supported_corners / 4  # Corner support: score based on corner count
            else:
                # Insufficient support
                score = area_ratio  # Partial score based on whatever support exists
            
            support_scores.append(score)
        
        # Calculate overall score as average of all item scores
        if not support_scores:
            return 0.0

        test = sum(support_scores) / len(support_scores)
        return test

    def get_item_scores(self) -> pd.DataFrame:
        """
        Return surface support scores for individual items
            
        Returns:
            DataFrame with item identifiers and support details
        """
        results = []
        for item in sorted(self.pallet.items, key=lambda obj: obj.lz):
        
            # Skip items directly on the ground (they have perfect support)
            if abs(item.lz) == 0:
                results.append({
                    'item': item.id,
                    'area_support_ratio': 1.0,
                    'corner_support_count': 4,
                    'support_score': 1.0
                })
                continue
            
            # Calculate item bottom surface coordinates
            x1, y1, z1 = item.lx, item.ly, item.lz
            x2, y2 = item.rx , item.ry
            bottom_area = item.width * item.length
            
            # Calculate the corners of the bottom face
            corners = [
                (x1, y1),  # bottom-left
                (x2, y1),  # bottom-right
                (x1, y2),  # top-left
                (x2, y2)   # top-right
            ]

            supported_corners = 0
            supported_area = 0
            
            # Check support from other items
            for other_item in sorted(self.pallet.items, key=lambda obj: obj.lx):
                # Skip self or items above this one
                if other_item.id == item.id or other_item.lz >= item.lz or other_item.rz >= item.lz:
                    continue
                
                # Calculate other item top surface coordinates
                ox1, oy1 = other_item.lx, other_item.ly
                ox2, oy2 = other_item.rx, other_item.ry
                oz2 = other_item.rz

                # Check if other item's top is directly below this item's bottom
                if abs(oz2 - z1) < 0.1:
                    # Calculate overlap area
                    x_overlap = max(0, min(x2, ox2) - max(x1, ox1))
                    y_overlap = max(0, min(y2, oy2) - max(y1, oy1))
                    
                    if x_overlap > 0 and y_overlap > 0:
                        supported_area += x_overlap * y_overlap
                    
                    # Check if corners are supported
                    for idx, (cx, cy) in enumerate(corners):
                        if ox1 <= cx <= ox2 and oy1 <= cy <= oy2:
                            supported_corners += 1
            
            # Calculate area support ratio
            area_ratio = supported_area / bottom_area if bottom_area > 0 else 0
            
            # Determine if item has sufficient support
            has_area_support = area_ratio >= self.min_surface_ratio
            has_corner_support = supported_corners >= self.corner_support_threshold
            
            if has_area_support or has_corner_support:
                # Calculate weighted score based on support type
                if has_area_support and has_corner_support:
                    score = 1.0  # Both types of support: perfect
                elif has_area_support:
                    score = area_ratio  # Area support: score based on coverage
                else:
                    score = supported_corners / 4  # Corner support: score based on corner count
            else:
                # Insufficient support
                score = area_ratio  # Partial score based on whatever support exists
            
            results.append({
                'item': item.id,
                'area_support_ratio': area_ratio,
                'corner_support_count': supported_corners,
                'support_score': score
            })
        
        return pd.DataFrame(results)


class MinimalSurfaceSupport:
    """
    Class for calculating the Surface Support KPI.
    
    This KPI measures if items have a solid base structure to stand on.
    Only takes the minimum surface support per pallet into consideration and only uses the supported surface ratio for the per item score.

    A score of 1.0 indicates all items have optimal surface support.
    A score of 0.0 indicates poor surface support across all items.
    """
    
    def __init__(self, pallet: Pallet):
        """
        Args:
            pallet: The pallet whose kpis are to be calculated
            min_surface_ratio: Minimum ratio of bottom surface that needs support
            corner_support_threshold: Minimum number of corners that need support (out of 4)
        """
        self.pallet = pallet
        
    def calculate(self) -> float:
        """
        Calculate the Surface Support KPI
                
        Returns:
            float: Score between 0.0 and 1.0
        """
        # Track support scores for each item
        support_scores = []

        for item in sorted(self.pallet.items, key=lambda obj: obj.lx):
        
            # Skip items directly on the ground (they have perfect support)
            if abs(item.lz) == 0:
                support_scores.append(1.0)
                continue
            
            # Calculate item bottom surface coordinates
            x1, y1, z1 = item.lx, item.ly, item.lz
            x2, y2 = item.rx , item.ry
            bottom_area = item.width * item.length
            
            supported_area = 0
            
            # Check support from other items
            for other_item in sorted(self.pallet.items, key=lambda obj: obj.lx):
                # Skip self or items above this one
                if other_item.id == item.id or other_item.lz >= item.lz or other_item.rz > item.lz:
                    continue
                
                # Calculate other item top surface coordinates
                ox1, oy1 = other_item.lx, other_item.ly
                ox2, oy2 = other_item.rx, other_item.ry
                oz2 = other_item.rz
                
                # Check if other item's top is directly below this item's bottom
                if abs(oz2 - z1) < 2:
                    # Calculate overlap area
                    x_overlap = max(0, min(x2, ox2) - max(x1, ox1))
                    y_overlap = max(0, min(y2, oy2) - max(y1, oy1))
                    
                    if x_overlap > 0 and y_overlap > 0:
                        supported_area += x_overlap * y_overlap
            
            # Calculate support ratio
            area_ratio = supported_area / bottom_area if bottom_area > 0 else 0
            score = area_ratio
            
            support_scores.append(score)
        
        # Calculate overall score as average of all item scores
        if not support_scores:
            return 0.0

        min_score = min(support_scores)
        score = min_score

        return score
    

    def get_item_scores(self) -> pd.DataFrame:
        """
        Return surface support scores for individual items
            
        Returns:
            DataFrame with item identifiers and support details
        """
        results = []
        for item in sorted(self.pallet.items, key=lambda obj: obj.lx):
        
            # Skip items directly on the ground (they have perfect support)
            if abs(item.lz) == 0:
                results.append({
                    'item': item.id,
                    'support_score': 1.0
                })
                continue
            
            # Calculate item bottom surface coordinates
            x1, y1, z1 = item.lx, item.ly, item.lz
            x2, y2 = item.rx , item.ry
            bottom_area = item.width * item.length
            
            supported_area = 0
            
            # Check support from other items
            for other_item in sorted(self.pallet.items, key=lambda obj: obj.lx):
                # Skip self or items above this one
                if other_item.id == item.id or other_item.lz >= item.lz or other_item.rz > item.lz:
                    continue
                
                # Calculate other item top surface coordinates
                ox1, oy1 = other_item.lx, other_item.ly
                ox2, oy2 = other_item.rx, other_item.ry
                oz2 = other_item.rz

                # Check if other item's top is directly below this item's bottom
                if abs(oz2 - z1) < 2:
                    # Calculate overlap area
                    x_overlap = max(0, min(x2, ox2) - max(x1, ox1))
                    y_overlap = max(0, min(y2, oy2) - max(y1, oy1))
                    
                    if x_overlap > 0 and y_overlap > 0:
                        supported_area += x_overlap * y_overlap
            
            # Calculate area support ratio
            area_ratio = supported_area / bottom_area if bottom_area > 0 else 0
            score = area_ratio 
            
            results.append({
                'item': item.id,
                'support_score': score
            })
        
        return pd.DataFrame(results)


class PillarScore:
    """
    Class for calculating the Pillar Score KPI.
    
    This KPI penalizes tall, slender, poorly supported 'pillar' (tower) structures,
    reflecting the risk of instability due to vertical stacking without adequate support.
    A score of 1.0 indicates a safe packing with no dangerous pillars.
    A score of 0.0 indicates severe vertical instability.
    """

    def __init__(
        self, 
        pallet: Pallet, 
        min_pillar_length: int = 3, 
        slenderness_threshold: float = 1.3,
        lateral_support_threshold: float = 0.8,
        base_support_threshold: float = 1.51,
        max_penalty: float = 1.0,
        get_side_support=None,    # Function: df -> pd.Series (side support per item)
        get_surface_support=None  # Function: df -> pd.Series (surface support per item)
    ):
        """
        Args:
            pallet: The pallet whose kpis are to be calculated
            min_pillar_length: minimal item chain length for a structure to be counted as pillar 
            slenderness_threshold: threshold up to which a structure counts as to slender to be stable on its own
            lateral_support_threshold: threshold up to which a structure is counted as standing unsupported from the side
            base_support_threshold: threshold up to which a structure is counted as standing unsupported from the ground
            max_penalty: maximum applied penalty
            get_side_support: method applied to calculate the side support for each item
            get_surface_support: method applied to calculate the surfache support of each item
        """
        self.pallet = pallet
        self.min_pillar_length = min_pillar_length
        self.slenderness_threshold = slenderness_threshold
        self.lateral_support_threshold = lateral_support_threshold
        self.base_support_threshold = base_support_threshold
        self.max_penalty = max_penalty
        # Allow user to pass their side/surface support calculators
        self.get_side_support = get_side_support
        self.get_surface_support = get_surface_support

    def _is_stacked_above(self, item_a, item_b):
        # Return True if item_a is directly above item_b (XY overlap, z1 == z2+height within tolerance)
        tol = 0.1
        overlap_x = (min(item_a.rx, item_b.rx) 
                    - max(item_a.lx, item_b.lx)) > 0
        overlap_y = (min(item_a.ry, item_b.ry) 
                    - max(item_a.ly, item_b.ly)) > 0
        correct_z = abs(item_a.lz - (item_b.rz)) < tol
        return overlap_x and overlap_y and correct_z

    def _find_pillar_chain(self, item, used_items) -> List[Item]:
        # Trace vertically both up and down to get all items in pillar chain
        chain = [item]
        # Downwards
        curr = item
        while True:
            found = False
            for other in self.pallet.items:
                if other.id == curr.id or other.id in used_items:
                    continue
                if self._is_stacked_above(curr, other):
                    chain.insert(0, other)
                    curr = other
                    found = True
                    break
            if not found:
                break
        # Upwards
        curr = item
        while True:
            found = False
            for other in self.pallet.items:
                if other.id == curr.id or other.id in used_items:
                    continue
                if self._is_stacked_above(other, curr):
                    chain.append(other)
                    curr = other
                    found = True
                    break
            if not found:
                break
        return chain

    def calculate(self,):
        """
        Calculate the Pillar Score KPI
                
        Returns:
            float: Score between 0.0 and 1.0
        """

        used_items = set()
        pillar_penalty_total = 0.0

        # Optionally get per-item side support and surface support
        side_support_map = {}
        surface_support_map = {}
        if self.get_side_support:
            sside = self.get_side_support()
            side_support_map = dict(zip(sside['item'], sside['side_support_score']))
        if self.get_surface_support:
            ssurf = self.get_surface_support()
            surface_support_map = dict(zip(ssurf['item'], ssurf['support_score']))

        for item in self.pallet.items:
            if item.id in used_items:
                continue

            pillar_chain: List[Item] = self._find_pillar_chain(item, used_items)
            if len(pillar_chain) < self.min_pillar_length:
                continue

            # Mark all items in this chain as used
            for p in pillar_chain:
                used_items.add(p.id)

            z_bottom = pillar_chain[0].lz
            z_top = pillar_chain[-1].rz
            height = z_top - z_bottom
            base_item = pillar_chain[0]
            base_area = base_item.width * base_item.length
            slenderness = height / (np.sqrt(base_area) + 1e-6)

            # Mean side support and base surface support
            lateral_support = np.mean([
                side_support_map.get(p.id, 1.0) for p in pillar_chain
            ]) if side_support_map else 1.0
            base_support = surface_support_map.get(base_item.id, 1.0) if surface_support_map else 1.0

            # Only penalize if truly pillar-like and poorly supported
            if (slenderness > self.slenderness_threshold and
                lateral_support < self.lateral_support_threshold and
                base_support < self.base_support_threshold):

                # Penalty grows with height, slenderness, and poor support
                penalty = (height / self.pallet.height) * (slenderness / self.slenderness_threshold)
                penalty *= (1 - lateral_support) * max(1 - base_support, 0.1)
                pillar_penalty_total += penalty

        score = 1.0 - min(pillar_penalty_total, self.max_penalty)  # Clamp to [0,1]
        return max(0.0, score)


if __name__ == "__main__":
    """
    This file is used to generate a stability score for pallet layouts based on KPIs.
    Source code for KPI and score calculation has been taken from 'https://arxiv.org/abs/2601.11325' and has been adapted to fit the local data format.  
    Stability score and KPIs are added to the input json files. 
    """

    directory = pathlib.Path(__file__).resolve().parent / "Pallet_Generation" / "Jsons" / "Pallets"

    for file_path in sorted(directory.iterdir()):
        if not file_path.is_file():
            continue

        with open(file_path) as f:
            packing_plan = json.load(f)

        pallet = Pallet.from_json(packing_plan)    
        evaluator = BedBppKPIEvaluator(pallet)
        packing_plan["KPIs"] = evaluator.evaluate()

        with open(file_path, "w") as file:
            json.dump(packing_plan, file, indent=4)