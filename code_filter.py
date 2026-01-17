import tree_sitter
import tree_sitter_python as ts_python
import tree_sitter_bash as ts_bash
import tree_sitter_c_sharp as ts_c_sharp
import tree_sitter_cpp as ts_cpp
import tree_sitter_go as ts_go
import tree_sitter_java as ts_java
import tree_sitter_javascript as ts_javascript
import tree_sitter_rust as ts_rust
import tree_sitter_sql as ts_sql

import json


import tree_sitter

PY_LANGUAGE = tree_sitter.Language(ts_python.language())
BASH_LANGUAGE = tree_sitter.Language(ts_bash.language())
C_SHARP_LANGUAGE = tree_sitter.Language(ts_c_sharp.language())
CPP_LANGUAGE = tree_sitter.Language(ts_cpp.language())
GO_LANGUAGE = tree_sitter.Language(ts_go.language())
JAVA_LANGUAGE = tree_sitter.Language(ts_java.language())
JAVASCRIPT_LANGUAGE = tree_sitter.Language(ts_javascript.language())
RUST_LANGUAGE = tree_sitter.Language(ts_rust.language())
SQL_LANGUAGE = tree_sitter.Language(ts_sql.language())

class Filter:

    def __init__(self, language: str):

        language = language.lower()

        self._language = language

        if self._language == 'python':
            self._parser_language = PY_LANGUAGE
        elif self._language == 'bash':
            self._parser_language = BASH_LANGUAGE
        elif self._language == 'c_sharp' or self._language == 'csharp' or self._language == 'C#':
            self._parser_language = C_SHARP_LANGUAGE
        elif self._language == 'cpp' or self._language == 'c++':
            self._parser_language = CPP_LANGUAGE
        elif self._language == 'go' or self._language == 'golang':
            self._parser_language = GO_LANGUAGE
        elif self._language == 'java':
            self._parser_language = JAVA_LANGUAGE
        elif self._language == 'javascript' or self._language == 'js':
            self._parser_language = JAVASCRIPT_LANGUAGE
        elif self._language == 'rust':
            self._parser_language = RUST_LANGUAGE
        elif self._language == 'sql':
            self._parser_language = SQL_LANGUAGE

        self._parser = tree_sitter.Parser(self._parser_language)
        self.tree = None

    def CreateTree(self, source_code: str) -> None:
        source_code_bytes = bytes(source_code, "utf8")
        self._tree = self._parser.parse(source_code_bytes)
        self._source_code = source_code_bytes
    
    def GetFunctionInfo(self, node: tree_sitter.Node) -> dict:
        if node is None:
            return
        
        info = {
            "name": "",
            "parameters": [{"name": "", "type": "", "default_value": ""}],
            "return_type": "",
            "body": ""
        }

        def _extract_function_parameters(n) -> list:
            parameters_node = n.child_by_field_name("parameters")
            if not parameters_node:
                return []
            parameters = []
            for child in parameters_node.children:
                if child.type in ("(", ")", ","):
                    continue
                param = {"name": "", "type": "", "default_value": ""}
                if child.type == "identifier":
                    param["name"] = self._source_code[child.start_byte:child.end_byte].decode("utf8")
                elif child.type == "typed_parameter":
                    name_node = child.child_by_field_name("name") or child.children[0]
                    type_node = child.child_by_field_name("type") or child.children[2]
                    param["name"] = self._source_code[name_node.start_byte:name_node.end_byte].decode("utf8")
                    param["type"] = self._source_code[type_node.start_byte:type_node.end_byte].decode("utf8")
                elif child.type == "default_parameter":
                    name_node = child.child_by_field_name("name") or child.children[0]
                    default_value_node = child.child_by_field_name("value") or child.children[2]
                    param["name"] = self._source_code[name_node.start_byte:name_node.end_byte].decode("utf8")
                    param["default"] = self._source_code[default_value_node.start_byte:default_value_node.end_byte].decode("utf8")
                elif child.type == "typed_default_parameter":
                    name_node = child.child_by_field_name("name")
                    type_node = child.child_by_field_name("type")
                    default_value_node = child.child_by_field_name("value")
                    param["name"] = self._source_code[name_node.start_byte:name_node.end_byte].decode("utf8")
                    param["type"] = self._source_code[type_node.start_byte:type_node.end_byte].decode("utf8")
                    param["default"] = self._source_code[default_value_node.start_byte:default_value_node.end_byte].decode("utf8")
                parameters.append(param)
            return parameters  

        def _traverse(n):
            text = self._source_code[n.start_byte:n.end_byte].decode("utf8", errors="ignore")
            if n.type == "function_definition":
                name_node = n.child_by_field_name("name")

                if name_node:
                    name = self._source_code[name_node.start_byte:name_node.end_byte].decode("utf8", errors="ignore")
                    info["name"] = name
                    info["parameters"] = _extract_function_parameters(n)

                return_type_node = n.child_by_field_name("return_type")

                if return_type_node:
                    info["return_type"] = self._source_code[return_type_node.start_byte:return_type_node.end_byte].decode("utf8")
                    
                body_node = n.child_by_field_name("body")

                if body_node:
                    info["body"] = self._source_code[body_node.start_byte:body_node.end_byte].decode("utf8")

            for child in n.children:
                _traverse(child)

        _traverse(node)

        return info
    
    def MakeInfoInJSON(self, info: dict, filename: str) -> None:
        with open(filename, "w", encoding="utf8") as f:
            json.dump(info, f, ensure_ascii=False, indent=2)