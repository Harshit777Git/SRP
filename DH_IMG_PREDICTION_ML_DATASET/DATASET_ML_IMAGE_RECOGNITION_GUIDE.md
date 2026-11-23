# Sucker Rod Pump (SRP) Downhole Dynamometer Card Dataset
## Image Pattern Recognition for SRP Fault & State Diagnostics

### 1. Dataset Overview
This dataset contains standardized, labeled **Downhole Dynamometer Card Images (224×224 pixels)** and **Surface-Downhole Dual Cards (448×224 pixels)** specifically formatted for training Computer Vision (CV) and Deep Learning (DL) models (e.g., ResNet, EfficientNet, MobileNet, Vision Transformers, and custom CNNs) to identify downhole faults and operating states.

Every downhole card in this dataset was generated through numerical solution of the **Gibbs 1-Dimensional Damped Wave Equation PDE**, preserving the real physical fluid dynamics, valve opening/closing thresholds, and rod string harmonics.

### 2. Dataset Structure
```
Downhole_Card_ML_Dataset/
├── DOWNHOLE_CARD_DATASET_INDEX.csv     # Master metadata index linking images to well, stroke, and labels
├── DOWNHOLE_CARD_COORDINATES.csv       # 100-point numerical coordinate time series for 1D CNNs / LSTMs
├── train_dynacard_vision_model.py      # Standalone PyTorch training pipeline
├── DATASET_ML_IMAGE_RECOGNITION_GUIDE.md # This documentation
├── splits/
│   ├── train.csv                       # Stratified Training Set (70%)
│   ├── val.csv                         # Stratified Validation Set (15%)
│   └── test.csv                        # Stratified Held-out Test Set (15%)
└── images/
    ├── labeled_by_fault/               # Organized for torchvision.datasets.ImageFolder
    │   ├── Normal_Operation/
    │   ├── Fluid_Pound/
    │   ├── Gas_Interference/
    │   ├── Severe_Gas_Lock/
    │   ├── Traveling_Valve_Leak/
    │   ├── Standing_Valve_Leak/
    │   ├── Worn_Pump_Barrel/
    │   ├── Blocked_Intake/
    │   ├── High_Wellbore_Friction/
    │   ├── High_Fluid_Damping/
    │   ├── Tagging_Down_Hard/
    │   └── Unanchored_Tubing_Slip/
    ├── by_well/                        # Organized by well_id (e.g. prairie-001, canyon-015)
    └── dual_card/                      # Side-by-side surface (left) and downhole (right) cards
```

### 3. Diagnostic Class Taxonomy
| Class ID | Class Folder | Fault Mechanism | Characteristic Dynacard Signature |
| :---: | :--- | :--- | :--- |
| **0** | `Normal_Operation` | Healthy / Full Pump Fillage | Classic rectangular / trapezoidal full work area |
| **1** | `Fluid_Pound` | Incomplete Pump Fillage | Sharp horizontal lower shelf, sudden bottom impact |
| **2** | `Gas_Interference` | Compressible Gas in Chamber | Rounded concave polytropic compression delay on downstroke |
| **3** | `Severe_Gas_Lock` | Gas Locked Pump | Thin diagonal band, negligible net work area |
| **4** | `Traveling_Valve_Leak` | TV Cut / Worn Ball & Seat | Slanted right edge, delayed load pickup, drooping upstroke |
| **5** | `Standing_Valve_Leak` | SV Cut / Fluid Loss | Slanted left edge, delayed load drop, elevated downstroke |
| **6** | `Worn_Pump_Barrel` | Plunger Clearance Slippage | Rounded corners, elliptical shape, reduced gross displacement |
| **7** | `Blocked_Intake` | Restricted Wellbore Inflow | Deep underfilling, early vacuum decompression |
| **8** | `High_Wellbore_Friction` | Dogleg / Contact Drag | Widened upper and lower boundary hysteresis loop |
| **9** | `High_Fluid_Damping` | Viscous Heavy Crude | Bulging rounded card with high viscous drag hysteresis |
| **10** | `Tagging_Down_Hard` | Plunger Mechanical Impact | Sharp downward load spike at lower turnaround |
| **11** | `Unanchored_Tubing_Slip` | Tubing Breathing & Stretch | Tilted parallelogram from tubing elongation |

### 4. Fast ML Training Quickstart

#### Using the Provided Standalone PyTorch Script:
Run directly from terminal:
```bash
cd "C:\Users\HARSHIT\OneDrive - TAS\Desktop\Master Dataset\Downhole_Card_ML_Dataset"
python train_dynacard_vision_model.py --epochs 15 --batch-size 32 --lr 0.001
```

Or train with a pre-trained ResNet-18 backbone:
```bash
python train_dynacard_vision_model.py --epochs 10 --resnet
```

#### Zero-Code Loading via Torchvision:
```python
from torchvision.datasets import ImageFolder
from torchvision import transforms

dataset = ImageFolder(
    root="Downhole_Card_ML_Dataset/images/labeled_by_fault",
    transform=transforms.Compose([
        transforms.Resize((224, 224)),
        transforms.ToTensor(),
        transforms.Normalize(mean=[0.485, 0.456, 0.406], std=[0.229, 0.224, 0.225])
    ])
)
print("Detected classes:", dataset.classes)
```

### 5. Summary Statistics
- **Total Labeled Images**: 792
- **Training Samples**: 549 (70%)
- **Validation Samples**: 112 (15%)
- **Test Samples**: 131 (15%)
- **Image Resolution**: 224×224 pixels (Downhole), 448×224 pixels (Dual Card)
- **Coordinate Points**: 100 points normalized and raw per card
