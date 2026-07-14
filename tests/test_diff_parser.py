from app.utils.diff_parser import parse_file_patch, extract_added_lines

def test_diff_parser_extracts_added_lines():
    """
    Asserts that the parser correctly identifies the newly added lines 
    and computes their exact line numbers based on the hunk header.
    """
    patch_text = """@@ -10,3 +10,4 @@
 def example():
-    print("old")
+    print("new")
     return True
+    # Extra line
"""
    hunks = parse_file_patch(patch_text)
    added_lines = extract_added_lines(hunks)
    
    # We expect 2 added lines in the patch above
    assert len(added_lines) == 2
    
    # 1. The first added line should be mapped to line 11
    # Line 10: context `def example():`
    # Line 11: added `    print("new")`
    assert added_lines[0]['content'] == '    print("new")'
    assert added_lines[0]['line_number'] == 11
    
    # 2. The second added line should be mapped to line 13
    # Line 12: context `    return True`
    # Line 13: added `    # Extra line`
    assert added_lines[1]['content'] == '    # Extra line'
    assert added_lines[1]['line_number'] == 13
