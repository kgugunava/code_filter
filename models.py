from typing import TypedDict, List

class FunctionParameterInfo(TypedDict, total=False):
    name: str
    type: str
    default_value: str

class FunctionInfo(TypedDict, total=False):
    name: str
    parameters: List[FunctionParameterInfo]
    return_type: str

class ClassInfo(TypedDict, total=False):
    name: str
    superclasses: List[str]
    functions: List[FunctionInfo]

class CodeInfo(TypedDict, total=False):
    classes: List[ClassInfo]
    functions: List[FunctionInfo]