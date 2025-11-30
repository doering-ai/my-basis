############
### HEAD ###
############
### STANDARD
from typing import Annotated

### EXTERNAL
import pydantic as pyd
from pydantic_core import core_schema as pyd_schema
import pandas as pd
import regex as re

### INTERNAL
from ..infra import T, C


############
### BODY ###
############
class SyntaxUtils:
    @classmethod
    def fill_tree(cls, tree: dict[T, C]) -> None:
        for key, val in tree.items():
            if isinstance(val, dict):
                cls.fill_tree(val)  # type: ignore
            elif val is None:
                tree[key] = {}  # type:ignore

    @classmethod
    def tree_size(cls, tree: object) -> int:
        return sum(map(cls.tree_size, tree.values())) if isinstance(tree, dict) else 1

    @staticmethod
    def pyd_schemify(tvar: type) -> pyd.GetPydanticSchema:
        return pyd.GetPydanticSchema(lambda _, __: pyd_schema.is_instance_schema(cls=tvar))

    Regex = Annotated[re.Pattern, pyd_schemify(re.Pattern)]
    PydDataFrame = Annotated[pd.DataFrame, pyd_schemify(pd.DataFrame)]


nut = SyntaxUtils
