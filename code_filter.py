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
    
    def TreeTraversal(self, node: tree_sitter.Node) -> None:
        if node is None:
            return
        print("Type: ", node.type)
        for child in node.children:
            self.TreeTraversal(child)