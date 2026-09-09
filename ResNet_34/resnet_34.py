import os
import pathlib
import json
import torch
import torch.nn as nn
from torch.utils.data import Dataset, DataLoader, random_split
from tqdm import tqdm


# ============================================================
# Dataset
# ============================================================

class PrecomputedVoxelDataset(Dataset):
    def __init__(self, input_dir):
        self.files = sorted([
            os.path.join(input_dir, f)
            for f in os.listdir(input_dir)
            if f.endswith(".pt")
        ])

    def __getitem__(self, idx):
        voxel, is_stable = torch.load(self.files[idx])
        return voxel, is_stable

    def __len__(self):
        return len(self.files)


# ============================================================
# ResNet blocks
# ============================================================

class BasicBlock3D(nn.Module):
    expansion = 1

    def __init__(self, in_planes, planes, stride=1, downsample=None):
        super().__init__()

        self.conv1 = self.conv3x3x3(in_planes, planes, stride)
        self.bn1 = nn.BatchNorm3d(planes)
        self.relu = nn.ReLU(inplace=True)

        self.conv2 = self.conv3x3x3(planes, planes)
        self.bn2 = nn.BatchNorm3d(planes)

        self.downsample = downsample

    def forward(self, x):
        identity = x

        out = self.conv1(x)
        out = self.bn1(out)
        out = self.relu(out)

        out = self.conv2(out)
        out = self.bn2(out)

        if self.downsample is not None:
            identity = self.downsample(x)

        out += identity
        out = self.relu(out)

        return out

    def conv3x3x3(self, in_planes, out_planes, stride=1):
        return nn.Conv3d(in_planes, out_planes, kernel_size=3, stride=stride, padding=1, bias=False)


class Bottleneck3D(nn.Module):
    expansion = 4

    def __init__(self, in_planes, planes, stride=1, downsample=None):
        super().__init__()

        self.conv1 = nn.Conv3d(in_planes, planes, kernel_size=1, bias=False)
        self.bn1 = nn.BatchNorm3d(planes)

        self.conv2 = nn.Conv3d(planes, planes, kernel_size=3, stride=stride, padding=1, bias=False)
        self.bn2 = nn.BatchNorm3d(planes)

        self.conv3 = nn.Conv3d(planes, planes * self.expansion, kernel_size=1, bias=False)
        self.bn3 = nn.BatchNorm3d(planes * self.expansion)

        self.relu = nn.ReLU(inplace=True)
        self.downsample = downsample

    def forward(self, x):
        identity = x

        out = self.relu(self.bn1(self.conv1(x)))
        out = self.relu(self.bn2(self.conv2(out)))
        out = self.bn3(self.conv3(out))

        if self.downsample is not None:
            identity = self.downsample(x)

        out += identity
        out = self.relu(out)

        return out


# ============================================================
# 3D ResNet
# ============================================================

class VoxelResNet(nn.Module):
    def __init__(self, block=BasicBlock3D, layers=(3, 4, 6, 3)):
        super().__init__()

        self.stem_out = 32

        self.initial = nn.Sequential(
            nn.Conv3d(
                2,
                self.stem_out,
                kernel_size=3,
                stride=1,
                padding=2,
                bias=False
            ),
            nn.BatchNorm3d(self.stem_out),
            nn.ReLU(inplace=True),
            nn.MaxPool3d( kernel_size=3, stride=2, padding=1)
        )

        self.in_planes = self.stem_out

        # Current architecture.
        # layer1 also downsamples.
        self.layer1 = self._make_layer(block, 64, layers[0], stride=1)
        self.layer2 = self._make_layer(block, 128, layers[1], stride=2)
        self.layer3 = self._make_layer(block, 256, layers[2], stride=2)
        self.layer4 = self._make_layer(block, 512, layers[3], stride=2)

        self.global_pool = nn.AdaptiveAvgPool3d((1, 1, 1))
        self.fc = nn.Linear(512 * block.expansion,1)

    def _make_layer(self, block, planes, blocks, stride=1):
        downsample = None

        out_planes = planes * block.expansion

        if stride != 1 or self.in_planes != out_planes:
            downsample = nn.Sequential(
                nn.Conv3d(
                    self.in_planes,
                    out_planes,
                    kernel_size=1,
                    stride=stride,
                    bias=False
                ),
                nn.BatchNorm3d(out_planes),
            )

        layers = [block(self.in_planes, planes, stride=stride, downsample=downsample)]

        self.in_planes = out_planes

        for _ in range(1, blocks):
            layers.append(block(self.in_planes, planes))

        return nn.Sequential(*layers)

    def forward(self, x):
        x = self.initial(x)

        x = self.layer1(x)
        x = self.layer2(x)
        x = self.layer3(x)
        x = self.layer4(x)

        x = self.global_pool(x)
        x = torch.flatten(x, 1)

        # Raw logit.
        # No sigmoid here because BCEWithLogitsLoss expects logits.
        return self.fc(x)


# ============================================================
# Training
# ============================================================

def train_for_one_epoch(model, dataloader, optimizer, criterion, device):
    model.train()

    running_loss = 0.0
    n_seen = 0

    for voxels, is_stable in dataloader:

        voxels = voxels.to(device=device, dtype=torch.float32)

        targets = is_stable.to(device=device, dtype=torch.float32).unsqueeze(1)

        optimizer.zero_grad(set_to_none=True)

        logits = model(voxels)

        loss = criterion(logits, targets)

        loss.backward()
        optimizer.step()

        batch_size = voxels.size(0)

        running_loss += loss.item() * batch_size
        n_seen += batch_size

    return running_loss / max(1, n_seen)


# ============================================================
# Evaluation
# ============================================================

@torch.no_grad()
def evaluate_cls(model, dataloader, criterion, device):
    model.eval()

    total_loss = 0.0
    total_n = 0

    all_probs = []
    all_true = []

    for voxels, is_stable in dataloader:

        x = voxels.to(device=device, dtype=torch.float32)

        y = is_stable.to(  device=device, dtype=torch.float32).unsqueeze(1)

        logits = model(x)

        loss = criterion( logits, y)

        total_loss += loss.item() * x.size(0)
        total_n += x.size(0)

        probs = torch.sigmoid(logits)

        all_probs.append(probs.squeeze(1).cpu())

        all_true.append(y.squeeze(1).cpu().int())

    probs = torch.cat(all_probs)
    y_true = torch.cat(all_true)

    # --------------------------------------------------------
    # Fixed 0.5 threshold metrics
    # --------------------------------------------------------

    y_hat_05 = (probs >= 0.5).int()

    tp05 = int(((y_hat_05 == 1) & (y_true == 1)).sum())
    tn05 = int(((y_hat_05 == 0) & (y_true == 0)).sum())
    fp05 = int(((y_hat_05 == 1) & (y_true == 0)).sum())
    fn05 = int(((y_hat_05 == 0) & (y_true == 1)).sum())

    precision05 = tp05 / max(1, tp05 + fp05)
    recall05 = tp05 / max(1, tp05 + fn05)

    f1_05 = (2 * precision05 * recall05 / max(1e-12, precision05 + recall05))

    accuracy05 = ((tp05 + tn05) / max(1, tp05 + tn05 + fp05 + fn05))

    positive_rate05 = y_hat_05.float().mean().item()

    # --------------------------------------------------------
    # Search threshold maximizing validation F1
    # --------------------------------------------------------

    thresholds = torch.linspace(0.05, 0.95, steps=19)

    best = {
        "thr": 0.5,
        "f1": -1.0,
        "prec": 0.0,
        "rec": 0.0
    }

    for t in thresholds:

        y_hat = (probs >= t).int()

        tp = int(((y_hat == 1) & (y_true == 1)).sum())
        fp = int(((y_hat == 1) & (y_true == 0)).sum())
        fn = int(((y_hat == 0) & (y_true == 1)).sum())

        precision = tp / max(1, tp + fp)
        recall = tp / max(1, tp + fn)

        f1 = (2 * precision * recall / max(1e-12, precision + recall))

        if f1 > best["f1"]:
            best.update(
                thr=float(t),
                f1=float(f1),
                prec=float(precision),
                rec=float(recall)
            )

    # --------------------------------------------------------
    # Metrics using best threshold
    # --------------------------------------------------------

    y_hat = (probs >= best["thr"]).int()

    tp = int(((y_hat == 1) & (y_true == 1)).sum())
    tn = int(((y_hat == 0) & (y_true == 0)).sum())
    fp = int(((y_hat == 1) & (y_true == 0)).sum())
    fn = int(((y_hat == 0) & (y_true == 1)).sum())

    accuracy = ((tp + tn)/ max(1, tp + tn + fp + fn))

    positive_rate = y_hat.float().mean().item()

    # --------------------------------------------------------
    # ROC-AUC
    # --------------------------------------------------------

    order = torch.argsort(probs, descending=True)

    y_sort = y_true[order]

    tp_cum = torch.cumsum((y_sort == 1), dim=0).float()
    fp_cum = torch.cumsum((y_sort == 0), dim=0).float()

    positives = float((y_true == 1).sum().item()) or 1.0
    negatives = float((y_true == 0).sum().item()) or 1.0

    tpr = tp_cum / positives
    fpr = fp_cum / negatives

    fpr_roc = torch.cat([torch.tensor([0.0]), fpr,torch.tensor([1.0])])
    tpr_roc = torch.cat([torch.tensor([0.0]), tpr, torch.tensor([1.0])])
    roc_auc = torch.trapz(tpr_roc,fpr_roc).item()

    # --------------------------------------------------------
    # PR-AUC
    # --------------------------------------------------------

    precision_curve = (tp_cum / torch.clamp(tp_cum + fp_cum, min=1.0))
    recall_curve = (tp_cum / positives)

    first_precision = (precision_curve[0].item() if precision_curve.numel() > 0 else 1.0)
    recall_pr = torch.cat([torch.tensor([0.0]), recall_curve, torch.tensor([1.0])])
    precision_pr = torch.cat([ torch.tensor([first_precision]), precision_curve, torch.tensor([0.0])])
    pr_auc = torch.trapz( precision_pr, recall_pr).item()
    avg_loss = ( total_loss / max(1, total_n))

    metrics = {

        # Best validation threshold
        "threshold": best["thr"],
        "F1": best["f1"],
        "precision": best["prec"],
        "recall": best["rec"],
        "accuracy": float(accuracy),
        "positive_rate": positive_rate,

        # Fixed 0.5 metrics
        "F1_05": float(f1_05),
        "precision_05": float(precision05),
        "recall_05": float(recall05),
        "accuracy_05": float(accuracy05),
        "positive_rate_05": float(positive_rate05),

        "confusion": {
            "tp": tp,
            "fp": fp,
            "fn": fn,
            "tn": tn
        },

        "ROC_AUC": roc_auc,
        "PR_AUC": pr_auc,
    }

    return avg_loss, metrics


# ============================================================
# Logging
# ============================================================

def log(txt: str):

    log_dir = (pathlib.Path(__file__).parent / "Log_Files")

    log_dir.mkdir(  parents=True, exist_ok=True)

    with open( log_dir / "stability_log.txt", "a") as f:
        f.write(txt)


# ============================================================
# Main
# ============================================================

if __name__ == "__main__":
    """
    Trains a nn with standard ResNet-34 architecture on a precomputed dataset (voxel_data_preperation.py) to rate pallets for their stability against binary ground truth input.
    """

    input_dir = (pathlib.Path(__file__).parent / "Preprocessed_Data")
    output_dir = (pathlib.Path(__file__).parent / "Checkpoint_Models")
    output_dir.mkdir(parents=True, exist_ok=True)

    full_dataset = PrecomputedVoxelDataset(input_dir)

    # --------------------------------------------------------
    # Reproducible 80 / 20 split
    # --------------------------------------------------------

    train_size = int(0.8 * len(full_dataset))

    remaining = (len(full_dataset) - train_size)

    val_size = remaining 

    split_generator = (torch.Generator().manual_seed(42))

    (train_dataset, val_dataset,) = random_split(
        full_dataset,
        [
            train_size,
            val_size,
        ],
        generator=split_generator
    )

    print(
        f"Dataset: {len(full_dataset)} | "
        f"Train: {len(train_dataset)} | "
        f"Val: {len(val_dataset)} | "
    )

    # --------------------------------------------------------
    # DataLoaders
    # --------------------------------------------------------

    train_loader = DataLoader(
        train_dataset,
        batch_size=8,
        shuffle=True,
        num_workers=0
    )

    val_loader = DataLoader(
        val_dataset,
        batch_size=8,
        shuffle=False
    )

    # --------------------------------------------------------
    # Model
    # --------------------------------------------------------

    device = torch.device("cuda" if torch.cuda.is_available() else "cpu")
    print("Device:", device)

    model = VoxelResNet().to(device)

    # --------------------------------------------------------
    # Training configuration
    # --------------------------------------------------------

    criterion = nn.BCEWithLogitsLoss()

    optimizer = torch.optim.AdamW(
        model.parameters(),
        lr=1e-3,
        weight_decay=1e-4
    )

    scheduler = (
        torch.optim.lr_scheduler
        .ReduceLROnPlateau(
            optimizer,
            mode="min",
            factor=0.5,
            patience=3
        )
    )

    num_epochs = 100
    best_f1 = -1.0
    best_val_loss = float("inf")
    patience = 8
    epochs_without_improvement = 0

    # --------------------------------------------------------
    # Training loop
    # --------------------------------------------------------

    for epoch in tqdm(range(num_epochs), desc="Training epochs"):

        train_loss = train_for_one_epoch( model, train_loader, optimizer, criterion, device)

        val_loss, metrics = evaluate_cls( model, val_loader, criterion, device)

        # Scheduler responds to validation BCE
        scheduler.step(val_loss)

        current_lr = (optimizer.param_groups[0]["lr"])

        output_text = (
            f"Epoch {epoch + 1}/{num_epochs} | "
            f"Train={train_loss:.4f} | "
            f"Val={val_loss:.4f} | "
            f"F1={metrics['F1']:.3f} | "
            f"Acc={metrics['accuracy']:.3f} | "
            f"P={metrics['precision']:.3f} | "
            f"R={metrics['recall']:.3f} | "
            f"Thr={metrics['threshold']:.2f} | "
            f"Pred+={metrics['positive_rate']:.3f} | "
            f"F1@0.5={metrics['F1_05']:.3f} | "
            f"Acc@0.5={metrics['accuracy_05']:.3f} | "
            f"Pred+@0.5={metrics['positive_rate_05']:.3f} | "
            f"ROC={metrics['ROC_AUC']:.3f} | "
            f"PR={metrics['PR_AUC']:.3f} | "
            f"LR={current_lr:.6f}"
        )

        print(output_text)
        log(output_text + "\n")

        # ----------------------------------------------------
        # Save best model according to validation F1
        # ----------------------------------------------------

        if metrics["F1"] > best_f1:

            best_f1 = metrics["F1"]

            torch.save(
                {
                    "epoch": epoch,

                    "model_state_dict":
                        model.state_dict(),

                    "optimizer_state_dict":
                        optimizer.state_dict(),

                    "scheduler_state_dict":
                        scheduler.state_dict(),

                    "val_loss":
                        val_loss,

                    "val_f1":
                        metrics["F1"],

                    # Important:
                    # threshold selected ONLY from validation
                    "threshold":
                        metrics["threshold"],

                },
                output_dir
                / "stability_checkpoint.pth"
            )

            print(
                f"  -> Saved new best model "
                f"(F1={best_f1:.3f}, "
                f"threshold={metrics['threshold']:.2f})"
            )

        if val_loss < best_val_loss:
            best_val_loss = val_loss
            epochs_without_improvement = 0
        else:
            epochs_without_improvement += 1

        if epochs_without_improvement >= patience:
            print(
                f"Early stopping at epoch {epoch + 1}. "
                f"No validation-loss improvement for {patience} epochs."
            )
            break
