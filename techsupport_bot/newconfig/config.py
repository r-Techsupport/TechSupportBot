import json
from dataclasses import MISSING, fields
from pathlib import Path
from typing import Any, get_args, get_origin

import discord

from .schema import ConfigSchema


class Config(ConfigSchema):
    def __init__(self, guild: discord.Guild):
        self.guild = guild
        json_data = self._load_json(Path(".guildConfig") / f"{guild.id}.json")

        self._apply_config(json_data)

    def _load_json(self, path: Path) -> dict[str, Any]:
        if path.exists():
            try:
                with path.open("r", encoding="utf-8") as f:
                    return json.load(f)
            except json.JSONDecodeError:
                print(f"Warning: Failed to parse JSON in {path}")
        return {}

    def _apply_config(self, data: dict[str, Any]) -> None:
        print(data)
        for f in fields(ConfigSchema):
            print(f"A: {f}")
            name = f.name
            value = data.get(name, MISSING)

            if value is MISSING:
                # Default or default_factory or None
                if f.default is not MISSING:
                    setattr(self, name, f.default)
                elif f.default_factory is not MISSING:
                    setattr(self, name, f.default_factory())
                else:
                    setattr(self, name, None)
                continue

            expected_type = f.type
            print(expected_type)

            # Apply if type matches exactly
            if isinstance(value, expected_type):
                print("A")
                setattr(self, name, value)
            else:
                # Leave default silently
                if f.default is not MISSING:
                    setattr(self, name, f.default)
                elif f.default_factory is not MISSING:
                    setattr(self, name, f.default_factory())
                else:
                    setattr(self, name, None)

    def serialize(self) -> dict[str, Any]:
        return {
            f.name: getattr(self, f.name)
            for f in fields(ConfigSchema)
            if not isinstance(getattr(self, f.name), discord.abc.Messageable)
        }

    def save(self) -> None:
        path = Path(".guildConfig") / f"{self.guild.id}.json"
        path.parent.mkdir(parents=True, exist_ok=True)
        with path.open("w", encoding="utf-8") as f:
            json.dump(self.serialize(), f, indent=4)
