import json
import tree_sitter
import constants
import models

class Filter:

    def __init__(self, language: str):

        language = language.lower()

        self._language = language

        if self._language == 'python':
            self._parser_language = constants.PY_LANGUAGE
        elif self._language == 'bash':
            self._parser_language = constants.BASH_LANGUAGE
        elif self._language == 'c_sharp' or self._language == 'csharp' or self._language == 'C#':
            self._parser_language = constants.C_SHARP_LANGUAGE
        elif self._language == 'cpp' or self._language == 'c++':
            self._parser_language = constants.CPP_LANGUAGE
        elif self._language == 'go' or self._language == 'golang':
            self._parser_language = constants.GO_LANGUAGE
        elif self._language == 'java':
            self._parser_language = constants.JAVA_LANGUAGE
        elif self._language == 'javascript' or self._language == 'js':
            self._parser_language = constants.JAVASCRIPT_LANGUAGE
        elif self._language == 'rust':
            self._parser_language = constants.RUST_LANGUAGE
        elif self._language == 'sql':
            self._parser_language = constants.SQL_LANGUAGE

        self._parser = tree_sitter.Parser(self._parser_language)
        self.tree = None

    def create_tree(self, source_code: str) -> None:
        source_code_bytes = bytes(source_code, "utf8")
        self._tree = self._parser.parse(source_code_bytes)
        self._source_code = source_code_bytes

    def get_code_info(self, node: tree_sitter.Node) -> models.CodeInfo:
        if node is None:
            return
        
        classes_info: list[models.ClassInfo] = []

        def _traverse(n):
            if n.type == "class_definition":
                class_info = self.get_class_info(n)
                classes_info.append(class_info)
            for child in n.children:
                _traverse(child)

        _traverse(node)

        code_info: models.CodeInfo = {}
        code_info["classes"] = classes_info

        return code_info
        
        
        
    def get_class_info(self, node: tree_sitter.Node) -> models.ClassInfo:
        if node is None:
            return
        
        class_info: models.ClassInfo = {}

        name_node = node.child_by_field_name("name")
        if name_node:
            name = self._source_code[name_node.start_byte:name_node.end_byte].decode("utf8", errors="ignore")
            class_info["name"] = name

        def _extract_class_superclasses(n) -> list:
            superclasses_node = n.child_by_field_name("superclasses")
            if superclasses_node is None:
                return []
            superclasses = []
            for child in superclasses_node.children:
                if child.type in ("(", ")", ","):
                    continue
                if child.type == "identifier":
                    name = self._source_code[child.start_byte:child.end_byte].decode("utf8")
                    superclasses.append(name)
            return superclasses
        
        def _extract_class_functions(n) -> list[models.FunctionInfo]:
            functions_info = []

            body_node = n.child_by_field_name("body")
            if not body_node:
                return functions_info

            def _traverse(n):
                if n.type == "function_definition":
                    function_info = self.get_function_info(n)
                    functions_info.append(function_info)
                for child in n.children:
                    _traverse(child)

            _traverse(body_node)

            return functions_info
        
        class_info["superclasses"] = _extract_class_superclasses(node)
        class_info["functions"] = _extract_class_functions(node)

        return class_info
            
            
    
    def get_function_info(self, node: tree_sitter.Node) -> models.FunctionInfo:
        if node is None:
            return {}
        
        info: models.FunctionInfo = {}

        def _extract_function_parameters(n) -> list:
            parameters_node = n.child_by_field_name("parameters")

            if not parameters_node:
                return []
            
            parameters = []

            for child in parameters_node.children:
                if child.type in ("(", ")", ","):
                    continue
                param: models.FunctionParameterInfo = {}
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
                    param["default_value"] = self._source_code[default_value_node.start_byte:default_value_node.end_byte].decode("utf8")
                elif child.type == "typed_default_parameter":
                    name_node = child.child_by_field_name("name")
                    type_node = child.child_by_field_name("type")
                    default_value_node = child.child_by_field_name("value")
                    param["name"] = self._source_code[name_node.start_byte:name_node.end_byte].decode("utf8")
                    param["type"] = self._source_code[type_node.start_byte:type_node.end_byte].decode("utf8")                 
                    param["default_value"] = self._source_code[default_value_node.start_byte:default_value_node.end_byte].decode("utf8")
                
                parameters.append(param)

            return parameters  
        
        name_node = node.child_by_field_name("name")

        if name_node:
            name = self._source_code[name_node.start_byte:name_node.end_byte].decode("utf8", errors="ignore")
            info["name"] = name
            info["parameters"] = _extract_function_parameters(node)

        return_type_node = node.child_by_field_name("return_type")

        if return_type_node:
            info["return_type"] = self._source_code[return_type_node.start_byte:return_type_node.end_byte].decode("utf8")

        return info
    
    
    def make_info_in_json_file(self, info: models.CodeInfo, filename: str) -> None:
        with open(filename, "w", encoding="utf8") as f:
            json.dump(info, f, ensure_ascii=False, indent=2)