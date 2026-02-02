from typing import TypedDict, List

from tree_sitter_go import language

class LanguageInfo(TypedDict, total=False):
    language: str

class ModuleInfo(TypedDict, total=False):
    module: str
    alias: str

class ImportNamesInfo(TypedDict, total=False):
    name: str
    alias: str

class ImportsInfo(TypedDict, total=False):
    type: str
    modules: ModuleInfo
    names: List[ImportNamesInfo]

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
    language: LanguageInfo
    imports: List[ImportsInfo]
    classes: List[ClassInfo]
    functions: List[FunctionInfo]