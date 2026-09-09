import torch
import json
import pathlib
import math
from tqdm import tqdm


class VoxelPreprocessor:
    def __init__(self, packing_plan, label, space_dims=(1200, 2000, 800), downsample_factor=16):
        """
        Creates a 2 Channel 3d Voxel representation of a pallet. 
        First channel encodes the Item positions on the pallet by setting all locations containing an item to 0.5 and their border surfaces to 1 in the Voxel. 
        Second channel additionally encodes the mass distribution on the pallet by setting all locations containing an item to the normalized items weight in the Voxel. 
        Pallet dimensions are downsampled by a factor of 16 to preserve storage space and improve learning speed (roughly 7GB per file vs 28MB).
        """
        self.packing_plan = packing_plan
        self.downsample_factor = downsample_factor
        self.space_dims = tuple(d // self.downsample_factor for d in space_dims)
        self.label = label

    def voxelize_stack(self):
        X, Z, Y = self.space_dims
        voxel_grid = torch.zeros(X, Z, Y, dtype=torch.float32)
        weight_grid = torch.zeros_like(voxel_grid)

        max_weight = max(item["weight"] for item in self.packing_plan["items"])
        for item in self.packing_plan["items"]:
            x  = item["lx"] // self.downsample_factor
            y  = item["ly"] // self.downsample_factor
            z  = item["lz"] // self.downsample_factor

            dx = math.ceil(item["rx"] / self.downsample_factor)
            dy = math.ceil(item["ry"] / self.downsample_factor)
            dz = math.ceil(item["rz"] / self.downsample_factor)

            voxel_grid[x:dx, z:dz, y:dy] = 0.5

            # mark shell/borders
            voxel_grid[x,    z:dz, y:dy] = 1.0
            voxel_grid[dx-1, z:dz, y:dy] = 1.0

            voxel_grid[x:dx, z,    y:dy] = 1.0
            voxel_grid[x:dx, dz-1, y:dy] = 1.0

            voxel_grid[x:dx, z:dz, y]    = 1.0
            voxel_grid[x:dx, z:dz, dy-1] = 1.0

            weight_grid[x:dx, z:dz, y:dy] = item["weight"] / max_weight

        voxel = torch.stack([voxel_grid, weight_grid], dim=0)
        return voxel

    def __getitem__(self):
        is_stable = True if self.packing_plan["movement_values_adams_fall"]["is_stable"] == "True" else False
        voxel = self.voxelize_stack()
        return voxel, torch.tensor(is_stable, dtype=torch.bool)


if __name__ == "__main__":
    """
    Loads the pallet dataset and transforms them into ready to use Voxel representation to save time during ResNet training.     
    Works only on data with stability labels.
    """
    
    input_dir = pathlib.Path(__file__).parent.parent / "Pallet_Generation" / "Jsons" / "Pallets" 
    output_dir = pathlib.Path(__file__).parent / "Preprocessed_Data"

    for file_path in tqdm(sorted(input_dir.iterdir()), desc="Running test"):
        if not file_path.is_file():
            continue

        with open(file_path) as f:
            packing_plan = json.load(f)

        preprocessor = VoxelPreprocessor(packing_plan, False)
        voxel, is_stable = preprocessor.__getitem__()

        torch.save((voxel, is_stable), str(output_dir / f"{packing_plan['id']}.pt"))

