"""Preflight and ingest multiple battle folders under one parent directory."""
from dataclasses import dataclass
from pathlib import Path
from folder_router import resolve_battle_images
from battle_identity import extract_battle_identity
from battle_processor import process_battle, find_duplicate_battle, DuplicateBattleError


@dataclass(frozen=True)
class BatchItem:
    folder: Path
    status: str
    battle_key: str | None = None
    error: str | None = None
    duplicate_of: str | None = None


def battle_folders(parent):
    root = Path(parent)
    if not root.is_dir():
        raise ValueError(f'Batch parent is not a directory: {parent}')
    folders = sorted((p for p in root.iterdir() if p.is_dir()), key=lambda p: p.name.lower())
    if not folders:
        raise ValueError(f'No battle subfolders found in: {parent}')
    return folders


def preflight_batch(parent, db_path=None):
    """Validate each immediate subfolder without writing to SQLite."""
    items=[]
    seen={}
    for folder in battle_folders(parent):
        try:
            images=resolve_battle_images(folder)
            identity=extract_battle_identity(images['outcome'])
            if identity is not None:
                existing=find_duplicate_battle(identity, db_path=db_path)
                if existing:
                    items.append(BatchItem(folder, 'DUPLICATE', battle_key=existing, duplicate_of=existing))
                    continue
                if identity.key in seen:
                    items.append(BatchItem(folder, 'DUPLICATE', duplicate_of=seen[identity.key]))
                    continue
                seen[identity.key]=folder.name
            items.append(BatchItem(folder, 'READY'))
        except Exception as exc:
            items.append(BatchItem(folder, 'INVALID', error=str(exc)))
    return items


def ingest_batch(parent, db_path=None):
    """Process valid battle subfolders independently; duplicates are skipped safely."""
    items=[]
    for folder in battle_folders(parent):
        try:
            images=resolve_battle_images(folder)
            key=process_battle(images['outcome'], images['heroes'], images['ratios_bonuses'], db_path=db_path,
                               notes=f'Batch source folder: {folder.name}')
            items.append(BatchItem(folder, 'SAVED', battle_key=key))
        except DuplicateBattleError as exc:
            items.append(BatchItem(folder, 'DUPLICATE', battle_key=exc.battle_key, duplicate_of=exc.battle_key))
        except Exception as exc:
            items.append(BatchItem(folder, 'FAILED', error=str(exc)))
    return items
