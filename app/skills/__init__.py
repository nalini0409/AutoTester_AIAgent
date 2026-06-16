import importlib
import inspect
import pkgutil
from pathlib import Path

from .base_skill import BaseSkill


def discover_skills() -> list[BaseSkill]:
    """Auto-discover all BaseSkill subclasses in this directory.

    To add a new skill: create a file named *_skill.py in this directory
    with a class that extends BaseSkill and implements analyze().
    """
    skills = []
    package_dir = Path(__file__).parent
    package_name = __name__

    for module_info in pkgutil.iter_modules([str(package_dir)]):
        if not module_info.name.endswith("_skill") or module_info.name == "base_skill":
            continue
        try:
            module = importlib.import_module(f".{module_info.name}", package=package_name)
            for _, obj in inspect.getmembers(module, inspect.isclass):
                if (
                    issubclass(obj, BaseSkill)
                    and obj is not BaseSkill
                    and not inspect.isabstract(obj)
                ):
                    skills.append(obj())
        except Exception as e:
            print(f"Warning: could not load skill '{module_info.name}': {e}")

    return skills
