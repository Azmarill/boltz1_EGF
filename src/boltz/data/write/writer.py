from dataclasses import asdict, replace
import json
from pathlib import Path
from typing import Literal

import numpy as np
from pytorch_lightning import LightningModule, Trainer
from pytorch_lightning.callbacks import BasePredictionWriter
import torch
from torch import Tensor

from boltz.data.types import (
    Interface,
    Record,
    Structure,
)
from boltz.data.write.mmcif import to_mmcif
from boltz.data.write.pdb import to_pdb


class BoltzWriter(BasePredictionWriter):
    """Custom writer for predictions."""

    def __init__(
        self,
        data_dir: str,
        output_dir: str,
        output_format: Literal["pdb", "mmcif"] = "mmcif",
    ) -> None:
        """Initialize the writer.

        Parameters
        ----------
        output_dir : str
            The directory to save the predictions.

        """
        super().__init__(write_interval="batch")
        if output_format not in ["pdb", "mmcif"]:
            msg = f"Invalid output format: {output_format}"
            raise ValueError(msg)

        self.data_dir = Path(data_dir)
        self.output_dir = Path(output_dir)
        self.output_format = output_format
        self.failed = 0

        # Create the output directories
        self.output_dir.mkdir(parents=True, exist_ok=True)

    def write_on_batch_end(
        self,
        trainer: Trainer,  # noqa: ARG002
        pl_module: LightningModule,  # noqa: ARG002
        prediction: dict[str, Tensor],
        batch_indices: list[int],  # noqa: ARG002
        batch: dict[str, Tensor],
        batch_idx: int,  # noqa: ARG002
        dataloader_idx: int,  # noqa: ARG002
    ) -> None:
        """Write the predictions to disk."""
        if prediction["exception"]:
            self.failed += 1
            return

        # Get the records
        records: list[Record] = batch["record"]

        # Get the predictions
        coords = prediction["coords"]
        coords = coords.unsqueeze(0)

        pad_masks = prediction["masks"]

        # Get ranking
        if "confidence_score" in prediction:
            argsort = torch.argsort(prediction["confidence_score"], descending=True)
            idx_to_rank = {idx.item(): rank for rank, idx in enumerate(argsort)}
        # Handles cases where confidence summary is False
        else:
            idx_to_rank = {i: i for i in range(len(records))}

        # Iterate over the records
        for record, coord, pad_mask in zip(records, coords, pad_masks):
            # Load the structure
            path = self.data_dir / f"{record.id}.npz"
            structure: Structure = Structure.load(path)

            # Compute chain map with masked removed, to be used later
            chain_map = {}
            for i, mask in enumerate(structure.mask):
                if mask:
                    chain_map[len(chain_map)] = i

            # Remove masked chains completely
            structure = structure.remove_invalid_chains()

            for model_idx in range(coord.shape[0]):
                # Get model coord
                model_coord = coord[model_idx]
                # Unpad
                coord_unpad = model_coord[pad_mask.bool()]
                coord_unpad = coord_unpad.cpu().numpy()

                # New atom table
                atoms = structure.atoms
                atoms["coords"] = coord_unpad
                atoms["is_present"] = True

                # Mew residue table
                residues = structure.residues
                residues["is_present"] = True

                # Update the structure
                interfaces = np.array([], dtype=Interface)
                new_structure: Structure = replace(
                    structure,
                    atoms=atoms,
                    residues=residues,
                    interfaces=interfaces,
                )

                # Update chain info
                chain_info = []
                for chain in new_structure.chains:
                    old_chain_idx = chain_map[chain["asym_id"]]
                    old_chain_info = record.chains[old_chain_idx]
                    new_chain_info = replace(
                        old_chain_info,
                        chain_id=int(chain["asym_id"]),
                        valid=True,
                    )
                    chain_info.append(new_chain_info)

                # Save the structure
                struct_dir = self.output_dir / record.id
                struct_dir.mkdir(exist_ok=True)

                # Get plddt's
                plddts = None
                if "plddt" in prediction:
                    plddts = prediction["plddt"][model_idx]

                # Create path name
                outname = f"{record.id}_model_{idx_to_rank[model_idx]}"

                # Save the structure
                if self.output_format == "pdb":
                    path = struct_dir / f"{outname}.pdb"
                    with path.open("w") as f:
                        f.write(to_pdb(new_structure, plddts=plddts))
                elif self.output_format == "mmcif":
                    path = struct_dir / f"{outname}.cif"
                    with path.open("w") as f:
                        f.write(to_mmcif(new_structure, plddts=plddts))
                else:
                    path = struct_dir / f"{outname}.npz"
                    np.savez_compressed(path, **asdict(new_structure))

                # Save confidence summary
                if "plddt" in prediction:
                    path = (
                        struct_dir
                        / f"confidence_{record.id}_model_{idx_to_rank[model_idx]}.json"
                    )
                    confidence_summary_dict = {}
                    for key in [
                        "confidence_score",
                        "ptm",
                        "iptm",
                        "ligand_iptm",
                        "protein_iptm",
                        "complex_plddt",
                        "complex_iplddt",
                        "complex_pde",
                        "complex_ipde",
                    ]:
                        confidence_summary_dict[key] = prediction[key][model_idx].item()
                    confidence_summary_dict["chains_ptm"] = {
                        idx: prediction["pair_chains_iptm"][idx][idx][model_idx].item()
                        for idx in prediction["pair_chains_iptm"]
                    }
                    confidence_summary_dict["pair_chains_iptm"] = {
                        idx1: {
                            idx2: prediction["pair_chains_iptm"][idx1][idx2][
                                model_idx
                            ].item()
                            for idx2 in prediction["pair_chains_iptm"][idx1]
                        }
                        for idx1 in prediction["pair_chains_iptm"]
                    }
                    with path.open("w") as f:
                        f.write(
                            json.dumps(
                                confidence_summary_dict,
                                indent=4,
                            )
                        )

                    # Save plddt
                    plddt = prediction["plddt"][model_idx]
                    path = (
                        struct_dir
                        / f"plddt_{record.id}_model_{idx_to_rank[model_idx]}.npz"
                    )
                    np.savez_compressed(path, plddt=plddt.cpu().numpy())

                # Save pae
                if "pae" in prediction:
                    pae = prediction["pae"][model_idx]
                    path = (
                        struct_dir
                        / f"pae_{record.id}_model_{idx_to_rank[model_idx]}.npz"
                    )
                    np.savez_compressed(path, pae=pae.cpu().numpy())

                # Save pde
                if "pde" in prediction:
                    pde = prediction["pde"][model_idx]
                    path = (
                        struct_dir
                        / f"pde_{record.id}_model_{idx_to_rank[model_idx]}.npz"
                    )
                    np.savez_compressed(path, pde=pde.cpu().numpy())

                # Save EGF structure
                # EGF予測結果の保存処理を追加
            if "coords_egf" in prediction:
                coords_egf = prediction["coords_egf"].unsqueeze(0)
                pad_masks_egf = prediction["masks_egf"] if "masks_egf" in prediction else pad_masks

                for model_idx in range(coords_egf.shape[1]):
                    # EGFモデルの座標を取得
                    model_coord_egf = coords_egf[0, model_idx]
                        # Unpad
                    coord_unpad_egf = model_coord_egf[pad_masks_egf.bool()]
                    coord_unpad_egf = coord_unpad_egf.cpu().numpy()

                        # atom table更新（EGF）
                    atoms_egf = structure.atoms
                    atoms_egf["coords"] = coord_unpad_egf
                    atoms_egf["is_present"] = True

                        # residue table更新（EGF）
                    residues_egf = structure.residues
                    residues_egf["is_present"] = True

                        # 構造情報を更新（EGF用）
                    new_structure_egf: Structure = replace(
                        structure,
                        atoms=atoms_egf,
                        residues=residues_egf,
                        interfaces=interfaces,
                   )

                        # 構造を保存するディレクトリ指定（EGF）
                    struct_dir_egf = self.output_dir / record.id
                    struct_dir_egf.mkdir(exist_ok=True)

                        # plddt (EGF用) の取得（存在する場合）
                    plddts_egf = None
                    if "plddt_egf" in prediction:
                        plddts_egf = prediction["plddt_egf"][model_idx]

                        # EGF構造のファイル名生成
                    outname_egf = f"{record.id}_egf_model_{idx_to_rank[model_idx]}"

                        # EGF構造を保存
                    if self.output_format == "pdb":
                        path_egf = struct_dir_egf / f"{outname_egf}.pdb"
                        with path_egf.open("w") as f:
                            f.write(to_pdb(new_structure_egf, plddts=plddts_egf))
                    elif self.output_format == "mmcif":
                        path_egf = struct_dir_egf / f"{outname_egf}.cif"
                        with path_egf.open("w") as f:
                            f.write(to_mmcif(new_structure_egf, plddts=plddts_egf))
                    else:
                        path_egf = struct_dir_egf / f"{outname_egf}.npz"
                        np.savez_compressed(path_egf, **asdict(new_structure_egf))

                       # EGF用のconfidenceやplddtも同様に保存
                    if "plddt_egf" in prediction:
                        path_egf_plddt = (
                            struct_dir_egf
                            / f"plddt_{record.id}_egf_model_{idx_to_rank[model_idx]}.npz"
                        )
                        np.savez_compressed(path_egf_plddt, plddt=plddts_egf.cpu().numpy())

    def on_predict_epoch_end(
        self,
        trainer: Trainer,  # noqa: ARG002
        pl_module: LightningModule,  # noqa: ARG002
    ) -> None:
        """Print the number of failed examples."""
        # Print number of failed examples
        print(f"Number of failed examples: {self.failed}")  # noqa: T201
