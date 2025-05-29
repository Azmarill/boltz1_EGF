# Boltz-1 Protein Structure Prediction with EGF

This repository provides an implementation of Boltz-1 enhanced by the Entropy Guided Folding (EGF) method, originally developed for AlphaFold2 and adapted here for the Boltz-1 model.

---

## Overview

Boltz-1 is a deep learning-based model designed for accurate protein structure prediction. This repository integrates Entropy Guided Folding (EGF), originally introduced for AlphaFold2, which refines predictions by maximizing the entropy of predicted distograms, thereby potentially enhancing prediction accuracy and confidence.

---

## Installation

Please follow the official installation instructions provided by Boltz-1:

[Official Boltz-1 Installation Guide](https://github.com/jwohlwend/boltz)

Ensure Boltz-1 is correctly installed before proceeding.

---

## Usage

### Basic Inference

To perform inference without EGF:

```bash
python main.py predict path/to/protein.fasta --out_dir ./results
```

### Enhanced Inference with EGF

To enable EGF during inference:

```bash
python main.py predict path/to/protein.fasta --use_egf --egf_lr 0.01 --out_dir ./results
```

* `--use_egf`: Activates EGF optimization.
* `--egf_lr`: Specifies the learning rate for EGF optimization (default is `0.01`).

---

## Output Files

Inference results will be stored under the specified `out_dir`:

```
results/
└── predictions/
    └── protein1/
        ├── pdistogram.npy                # Predicted distogram without EGF
        ├── sample_atom_coords.npy        # Predicted atom coordinates without EGF
        ├── pdistogram_egf.npy            # Refined distogram after EGF
        └── sample_atom_coords_egf.npy    # Refined atom coordinates after EGF
```

---

## Advanced Options

Customize inference parameters:

* `--recycling_steps`: Number of recycling iterations (default: 3)
* `--sampling_steps`: Number of diffusion sampling steps (default: 200)
* `--diffusion_samples`: Number of samples generated during inference (default: 1)
* `--output_format`: Output format (`pdb` or `mmcif`, default: `mmcif`)

Example usage:

```bash
python main.py predict protein.fasta --use_egf --egf_lr 0.005 --recycling_steps 5 --output_format pdb
```

---

## Technical Details (EGF)

EGF was initially developed for AlphaFold2 as described [here](https://github.com/Fenglaboratory/EGF). The method refines predictions by maximizing entropy in distance distributions, sharpening predictions and reducing structural ambiguity.

During inference:

* Optimizes copies of pairwise embeddings via gradient descent.
* Maximizes entropy to yield clearer, more confident structural predictions.

---

## System Requirements

* Python 3.9 or newer
* PyTorch Lightning
* PyTorch
* CUDA-enabled GPU recommended for optimal performance

---

## Citation

If you use this enhanced Boltz-1 model, please cite both the original Boltz-1 paper and the EGF method:

```bibtex
@article{original_boltz1_paper,
  title={Boltz-1: Accurate Protein Structure Prediction},
  author={Authors},
  journal={Journal},
  year={Year}
}

@article{egf_method,
  title={Entropy Guided Folding for Enhanced Protein Structure Prediction},
  author={Authors},
  journal={Journal},
  year={Year}
}
```

---

## Contact & Contribution

Submit issues or contribute improvements via pull requests.

---

© 2024 Your Organization or Your Name
