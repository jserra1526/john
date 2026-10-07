"""Milk optimisation: allocate seasonal milk to plants and products to maximise margin."""

from .data import DataError, ModelData, load_data
from .model import MilkModel, Solution, optimise

__all__ = ["DataError", "ModelData", "load_data", "MilkModel", "Solution", "optimise"]
