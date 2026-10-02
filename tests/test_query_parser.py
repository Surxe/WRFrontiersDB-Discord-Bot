from wrfdb_bot.services.lookup.lookup_key import to_lookup_key
from wrfdb_bot.services.lookup.query_parser import MAX_QUERIES_PER_MESSAGE, extract_queries, split_type_prefix


class TestToLookupKey:
    def test_lookup_key_normalizes_case_and_separators(self):
        assert to_lookup_key('Kate  Sinclair') == 'kate-sinclair'
        assert to_lookup_key('kate-sinclair') == 'kate-sinclair'

    def test_lookup_key_drops_apostrophes_and_quotes(self):
        assert to_lookup_key("Kate's Rig") == 'kates-rig'
        assert to_lookup_key('Kate’s Rig') == 'kates-rig'
        assert to_lookup_key('"Hammer" Petrova') == 'hammer-petrova'

    def test_lookup_key_empty_for_punctuation_only(self):
        assert to_lookup_key(' -- ') == ''


class TestExtractQueries:
    def test_extract_queries_in_order(self):
        assert extract_queries('try [[Kate Sinclair]] and [[ alpha ]]!') == ['Kate Sinclair', 'alpha']

    def test_extract_queries_ignores_code(self):
        content = 'syntax is `[[name]]`, e.g.\n```\n[[block]]\n```\nreal: [[Scourge]]'
        assert extract_queries(content) == ['Scourge']

    def test_extract_queries_deduplicates_case_insensitively(self):
        assert extract_queries('[[Alpha]] [[alpha]]') == ['Alpha']

    def test_extract_queries_limits_count(self):
        content = ' '.join(f'[[q{i}]]' for i in range(MAX_QUERIES_PER_MESSAGE + 3))
        assert len(extract_queries(content)) == MAX_QUERIES_PER_MESSAGE

    def test_extract_queries_skips_empty_and_overlong(self):
        assert extract_queries('[[ ]] [[' + 'x' * 500 + ']]') == []


class TestSplitTypePrefix:
    def test_split_type_prefix_present(self):
        assert split_type_prefix('talent: Vanguard') == ('talent', 'Vanguard')

    def test_split_type_prefix_absent(self):
        assert split_type_prefix('Vanguard') == (None, 'Vanguard')

    def test_split_type_prefix_needs_both_sides(self):
        assert split_type_prefix(':Vanguard') == (None, ':Vanguard')
        assert split_type_prefix('talent:') == (None, 'talent:')
