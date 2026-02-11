import json
import tree_sitter
from tree_sitter_go import language
import constants
import filter_models

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
        self.classes_info = None
        self.functions_info = None

    def create_tree_from_file(self, file_path: str) -> None:
        """
        Создаёт AST из файла по указанному пути.
        """
        try:
            with open(file_path, "r", encoding="utf8") as f:
                source_code = f.read()
        except FileNotFoundError:
            raise FileNotFoundError(f"Файл не найден: {file_path}")
        except UnicodeDecodeError:
            raise ValueError(f"Не удалось прочитать файл как UTF-8: {file_path}")

        source_code_bytes = bytes(source_code, "utf8")
        self._tree = self._parser.parse(source_code_bytes)
        self._source_code = source_code_bytes

    def get_language_info(self, node: tree_sitter.Node) -> filter_models.LanguageInfo:
        if node is None:
            return
        language_info = filter_models.LanguageInfo()
        language_info["language"] = self._language
        return language_info

    def get_imports_info(self, node: tree_sitter.Node):
        if node is None:
            return
        
        imports: list = []

        def _parse_import_statement(n) -> list[filter_models.ImportsInfo]:
            imports: list[filter_models.ImportsInfo] = []

            def collect_dotted_names(node):
                if node.type == "dotted_name":
                    module_name = self._source_code[node.start_byte:node.end_byte].decode("utf8")
                    alias = None

                    parent = node.parent
                    if parent and parent.type == "aliased_import":
                        children = parent.children
                        try:
                            idx = children.index(node)
                            # ищем "as" после dotted_name
                            for i in range(idx + 1, len(children)):
                                if children[i].type == "as":
                                    # следующий токен — это алиас (должен быть identifier)
                                    if i + 1 < len(children) and children[i + 1].type == "identifier":
                                        alias = self._source_code[children[i + 1].start_byte:children[i + 1].end_byte].decode("utf8")
                                    break
                        except ValueError:
                            pass

                    if alias:
                        imports.append(filter_models.ImportsInfo(
                            type="import",
                            modules=filter_models.ModuleInfo(module=module_name, alias=alias),
                            names=[]
                        ))
                    else:
                        imports.append(filter_models.ImportsInfo(
                            type="import",
                            modules=filter_models.ModuleInfo(module=module_name),
                            names=[]
                        ))
                else:
                    for child in node.children:
                        collect_dotted_names(child)

            collect_dotted_names(n)
            return imports

        def _parse_import_from_statement(n):
            module_node = n.child_by_field_name("module_name")
            module_name = self._source_code[module_node.start_byte:module_node.end_byte].decode("utf8") if module_node else ""

            names = []
            found_import = False

            def extract_name_from_dotted(node):
                """Извлекает имя из dotted_name (например, 'os.path' -> 'path')."""
                if node.type == "dotted_name":
                    identifiers = [child for child in node.children if child.type == "identifier"]
                    if identifiers:
                        return self._source_code[identifiers[-1].start_byte:identifiers[-1].end_byte].decode("utf8")
                elif node.type == "identifier":
                    return self._source_code[node.start_byte:node.end_byte].decode("utf8")
                return None

            for child in n.children:
                if child.type == "import":
                    found_import = True
                    continue
                
                if found_import:
                    if child.type == "aliased_import":
                        name_node = child.child_by_field_name("name")
                        alias_node = child.child_by_field_name("alias")
                        name = extract_name_from_dotted(name_node) if name_node else ""
                        alias = extract_name_from_dotted(alias_node) if alias_node else None
                        if name:
                            if alias:
                                names.append(filter_models.ImportNamesInfo(name=name, alias=alias))
                            else:
                                names.append(filter_models.ImportNamesInfo(name=name, alias=""))
                    
                    elif child.type == "*":
                        names.append(filter_models.ImportNamesInfo(name="*", alias=""))
                    
                    else:
                        name = extract_name_from_dotted(child)
                        if name:
                            names.append(filter_models.ImportNamesInfo(name=name, alias=""))

            return filter_models.ImportsInfo(
                type="import_from",
                modules=filter_models.ModuleInfo(module=module_name),
                names=names
            )

        for child in node.children:
            if child.type == "import_statement":
                imports.append(_parse_import_statement(child))
            elif child.type == "import_from_statement":
                imports.append(_parse_import_from_statement(child))

        return imports


    def get_code_info(self, node: tree_sitter.Node) -> filter_models.CodeInfo:
        if node is None:
            return
        
        language_info: filter_models.LanguageInfo
        imports_info: list[filter_models.ImportsInfo] = []
        classes_info: list[filter_models.ClassInfo] = []
        functions_info: list[filter_models.FunctionInfo] = []

        def _get_top_level_classes_info(n):
            if n.type == "class_definition":
                class_info = self.get_class_info(n)
                classes_info.append(class_info)
            for child in n.children:
                _get_top_level_classes_info(child)

        def _get_top_level_functions_info(n): # функции, объявленные вне классов
            if n.type == "class_definition":
                return
            if n.type == "function_definition":
                function_info = self.get_function_info(n)
                functions_info.append(function_info)
            for child in n.children:
                _get_top_level_functions_info(child)       

        _get_top_level_classes_info(node)
        _get_top_level_functions_info(node)
        imports_info = self.get_imports_info(node)
        language_info = self.get_language_info(node)

        code_info: filter_models.CodeInfo = {}
        code_info["language"] = language_info
        code_info["imports"] = imports_info
        code_info["classes"] = classes_info
        code_info["functions"] = functions_info

        return code_info
        
    def get_class_info(self, node: tree_sitter.Node) -> filter_models.ClassInfo:
        if node is None:
            return
        
        class_info: filter_models.ClassInfo = {}

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
        
        def _extract_class_functions(n) -> list[filter_models.FunctionInfo]:
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

    def get_function_info(self, node: tree_sitter.Node) -> filter_models.FunctionInfo:
        if node is None:
            return {}
        
        info: filter_models.FunctionInfo = {}

        decorators = []
        parent = node.parent
        if parent and parent.type == "decorated_definition":
            for child in parent.children:
                if child.type == "decorator":
                    decorator_text = self._source_code[child.start_byte:child.end_byte].decode("utf8")
                    if decorator_text.startswith("@"):
                        decorator_text = decorator_text[1:].strip()
                    decorators.append(decorator_text)
        
        info["decorators"] = decorators

        def _extract_function_parameters(n) -> list:
            parameters_node = n.child_by_field_name("parameters")
            if not parameters_node:
                return []
            
            parameters = []
            for child in parameters_node.children:
                if child.type in ("(", ")", ","):
                    continue
                param: filter_models.FunctionParameterInfo = {}
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
    
    def extract_context(self, file_path: str) -> dict:
        """
        Анализирует файл и возвращает плоский контекст для поиска.
        Безопасно обрабатывает отсутствующие ключи.
        """
        self.create_tree_from_file(file_path)
        info = self.get_code_info(self._tree.root_node)

        # 1. Язык
        language = info.get("language", {}).get("language", "unknown").strip()

        # 2. Импорты — собираем все имена
        imports = set()
        imports_list = info.get("imports", [])

        for imp_group in imports_list:
            # Обработка случая, когда элемент — список (из-за ошибки с append/extend)
            if isinstance(imp_group, list):
                for imp in imp_group:
                    self._collect_imports_from_item_safe(imp, imports)
            else:
                self._collect_imports_from_item_safe(imp_group, imports)

        # 3. Классы
        classes = []
        for cls in info.get("classes", []):
            name = cls.get("name", "").strip()
            if name:
                classes.append(name)

        # 4. Функции верхнего уровня
        functions = []
        for fn in info.get("functions", []):
            name = fn.get("name", "").strip()
            if name:
                functions.append(name)

        return {
            "language": language,
            "imports": sorted(imports),
            "classes": classes,
            "functions": functions,
        }

    def _collect_imports_from_item_safe(self, imp_item, imports_set):
        """Безопасное извлечение имён из одного элемента импорта."""
        if not isinstance(imp_item, dict):
            return

        imp_type = imp_item.get("type", "")
        
        if imp_type == "import":
            modules = imp_item.get("modules", {})
            module = modules.get("module", "").strip()
            if module:
                imports_set.add(module)

        elif imp_type == "import_from":
            names_list = imp_item.get("names", [])
            for name_info in names_list:
                if isinstance(name_info, dict):
                    name = name_info.get("name", "").strip()
                    if name and name != "*":
                        imports_set.add(name)

    def make_info_in_json_file(self, info: filter_models.CodeInfo, filename: str) -> None:
        with open(filename, "w", encoding="utf8") as f:
            json.dump(info, f, ensure_ascii=False, indent=2)