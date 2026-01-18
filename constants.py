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

PY_LANGUAGE = tree_sitter.Language(ts_python.language())
BASH_LANGUAGE = tree_sitter.Language(ts_bash.language())
C_SHARP_LANGUAGE = tree_sitter.Language(ts_c_sharp.language())
CPP_LANGUAGE = tree_sitter.Language(ts_cpp.language())
GO_LANGUAGE = tree_sitter.Language(ts_go.language())
JAVA_LANGUAGE = tree_sitter.Language(ts_java.language())
JAVASCRIPT_LANGUAGE = tree_sitter.Language(ts_javascript.language())
RUST_LANGUAGE = tree_sitter.Language(ts_rust.language())
SQL_LANGUAGE = tree_sitter.Language(ts_sql.language())