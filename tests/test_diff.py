"""Tests for the semantic diff engine."""

from gitledger.diff import semantic_diff


class TestSemanticDiff:
    def test_added_field(self):
        old = '{"a": 1}'
        new = '{"a": 1, "b": 2}'
        diffs = semantic_diff(old, new, "test.json")
        assert len(diffs) == 1
        assert diffs[0].field == "b"
        assert diffs[0].old_value is None
        assert diffs[0].new_value == 2

    def test_removed_field(self):
        old = '{"a": 1, "b": 2}'
        new = '{"a": 1}'
        diffs = semantic_diff(old, new, "test.json")
        assert len(diffs) == 1
        assert diffs[0].field == "b"
        assert diffs[0].old_value == 2
        assert diffs[0].new_value is None

    def test_changed_field(self):
        old = '{"score": 0.5}'
        new = '{"score": 0.9}'
        diffs = semantic_diff(old, new, "test.json")
        assert len(diffs) == 1
        assert diffs[0].field == "score"
        assert diffs[0].old_value == 0.5
        assert diffs[0].new_value == 0.9

    def test_nested_change(self):
        old = '{"config": {"retry": 3}}'
        new = '{"config": {"retry": 5}}'
        diffs = semantic_diff(old, new, "test.json")
        assert len(diffs) == 1
        assert diffs[0].field == "config.retry"

    def test_no_change(self):
        data = '{"a": 1, "b": 2}'
        diffs = semantic_diff(data, data, "test.json")
        assert diffs == []

    def test_both_none(self):
        diffs = semantic_diff(None, None, "test.json")
        assert diffs == []

    def test_new_file(self):
        diffs = semantic_diff(None, '{"a": 1}', "test.json")
        assert len(diffs) == 1
        assert diffs[0].field == "<root>"

    def test_deleted_file(self):
        diffs = semantic_diff('{"a": 1}', None, "test.json")
        assert len(diffs) == 1
        assert diffs[0].field == "<root>"

    def test_list_change(self):
        old = '{"items": [1, 2, 3]}'
        new = '{"items": [1, 2, 4]}'
        diffs = semantic_diff(old, new, "test.json")
        assert len(diffs) == 1
        assert diffs[0].field == "items[2]"

    def test_list_length_change(self):
        old = '{"items": [1, 2]}'
        new = '{"items": [1, 2, 3]}'
        diffs = semantic_diff(old, new, "test.json")
        assert len(diffs) == 1
        assert diffs[0].field == "items[2]"

    def test_type_change(self):
        old = '{"value": "hello"}'
        new = '{"value": 42}'
        diffs = semantic_diff(old, new, "test.json")
        assert len(diffs) == 1
        assert diffs[0].old_value == "hello"
        assert diffs[0].new_value == 42

    def test_non_json_content(self):
        diffs = semantic_diff("plain text v1", "plain text v2", "readme.txt")
        assert len(diffs) == 1
        assert diffs[0].field == "<raw>"

    def test_identical_non_json_content(self):
        diffs = semantic_diff("same text", "same text", "readme.txt")
        assert diffs == []

    def test_list_shrink(self):
        old = '{"items": [1, 2, 3]}'
        new = '{"items": [1]}'
        diffs = semantic_diff(old, new, "test.json")
        assert len(diffs) == 2
        fields = {d.field for d in diffs}
        assert "items[1]" in fields
        assert "items[2]" in fields
        for d in diffs:
            if d.field == "items[1]":
                assert d.old_value == 2
                assert d.new_value is None
            if d.field == "items[2]":
                assert d.old_value == 3
                assert d.new_value is None
