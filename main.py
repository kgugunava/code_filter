from code_filter import Filter

code_filter = Filter("python")


code_filter.create_tree_from_file("./sample_test.py")

print(code_filter.extract_context("./sample_test.py"))