import dataclasses

from conftest import SITE_URL

from wrfdb_bot.services.lookup.index import LookupIndex


class TestResolve:
    def test_resolve_exact_name_any_case(self, index):
        result = index.resolve('kate sinclair')
        assert result.entry.object_id == 'DA_Pilot_Rare_KateSinclair.0'
        assert result.entry.url == f'{SITE_URL}/pilots/kate-sinclair/'
        assert not result.is_fuzzy

    def test_resolve_quoted_pilot_name(self, index):
        assert index.resolve('Hammer Petrova').entry.object_id == 'DA_Pilot_Common1.0'

    def test_resolve_shared_name_prefers_type_priority(self, index):
        result = index.resolve('Vanguard')
        assert result.entry.object_type.name == 'Pilot'
        assert [e.object_id for e in result.other_matches] == ['DA_Talent_Leader1.0']

    def test_resolve_type_prefix_selects_type(self, index):
        result = index.resolve('talent: vanguard')
        assert result.entry.object_id == 'DA_Talent_Leader1.0'
        assert result.entry.url == f'{SITE_URL}/pilot_talents/vanguard/'
        assert result.other_matches == ()

    def test_resolve_multi_word_type_prefix(self, index):
        assert index.resolve('Pilot Class:Assault').entry.object_id == 'DA_Class_Brawler.0'

    def test_resolve_unknown_prefix_is_part_of_name(self, index):
        result = index.resolve('nonsense: Scourge')
        assert result.entry.object_id == 'DA_Module_Weapon_Scourge.0'
        assert result.is_fuzzy

    def test_resolve_robot_links_by_slug_map(self, index):
        result = index.resolve('Alpha')
        assert result.entry.object_type.name == 'VirtualBot'
        assert result.entry.url == f'{SITE_URL}/robots/alpha/'
        assert {e.display_name for e in result.other_matches} == {
            'Alpha Chassis',
            'Alpha Shoulder Left',
            'Alpha Shoulder Right',
            'Alpha Torso',
        }

    def test_resolve_robot_part_aliases(self, index):
        assert index.resolve('alpha chassis').entry.object_id == 'DA_Module_ChassisAlpha.1'
        assert index.resolve('Alpha Shoulder Right').entry.object_id == 'DA_Module_ShoulderRAlpha.0'
        assert index.resolve('alpha left shoulder').entry.object_id == 'DA_Module_ShoulderLAlpha.0'

    def test_resolve_fuzzy_typo(self, index):
        result = index.resolve('Kate Sinclar')
        assert result.entry.object_id == 'DA_Pilot_Rare_KateSinclair.0'
        assert result.is_fuzzy

    def test_resolve_fuzzy_partial_name(self, index):
        assert index.resolve('kate').entry.object_id == 'DA_Pilot_Rare_KateSinclair.0'

    def test_resolve_tied_fuzzy_gives_suggestions(self, index):
        result = index.resolve('gun')
        assert result.entry is None
        assert {'Railgun', 'Gun Nut'} <= {e.name for e in result.suggestions}

    def test_resolve_no_match(self, index):
        result = index.resolve('zzqx')
        assert result.entry is None
        assert result.suggestions == ()

    def test_resolve_skips_unpublished_modules(self, index):
        assert 'DA_Module_Weapon_Secret.0' not in {e.object_id for e in index.entries}

    def test_resolve_without_site_slug_has_no_url(self, index):
        result = index.resolve('Unlinked')
        assert result.entry.object_id == 'DA_Module_Unlinked.0'
        assert result.entry.url is None


class TestNicknames:
    def test_nickname_resolves_exactly(self, index):
        result = index.resolve('marcus')
        assert result.entry.object_id == 'DA_Pilot_Rare_MarcusShedd.0'
        assert result.entry.url == f'{SITE_URL}/pilots/marcus-shedd/'
        assert not result.is_fuzzy

    def test_full_name_still_reaches_the_other_pilot(self, index):
        assert index.resolve('Marcus Davis').entry.object_id == 'DA_Pilot_Common35.0'

    def test_nickname_with_type_prefix(self, index):
        assert index.resolve('pilot:marcus').entry.object_id == 'DA_Pilot_Rare_MarcusShedd.0'
        assert index.resolve('talent:marcus').entry is None

    def test_exact_name_beats_nickname(self, store):
        names = dataclasses.replace(store.snapshot.names, nicknames={'DA_Pilot_Common1.0': ['Scourge']})
        snapshot = dataclasses.replace(store.snapshot, names=names)
        index = LookupIndex.from_snapshot(snapshot)
        assert index.resolve('scourge').entry.object_id == 'DA_Module_Weapon_Scourge.0'

    def test_chassis_answers_to_legs(self, index):
        result = index.resolve('alpha legs')
        assert result.entry.object_id == 'DA_Module_ChassisAlpha.1'
        assert result.entry.display_name == 'Alpha Chassis'
        assert not result.is_fuzzy

    def test_autocomplete_puts_nickname_first(self, index):
        assert [e.display_name for e in index.autocomplete('marcus')][0] == 'Marcus Shedd'

    def test_without_nickname_shared_first_name_gives_suggestions(self, store):
        names = dataclasses.replace(store.snapshot.names, nicknames={})
        index = LookupIndex.from_snapshot(dataclasses.replace(store.snapshot, names=names))
        result = index.resolve('marcus')
        assert result.entry is None
        assert {'Marcus Davis', 'Marcus Shedd'} <= {e.name for e in result.suggestions}


class TestAbbreviations:
    def test_expands_words(self, index):
        result = index.resolve('r alpha')
        assert result.entry.object_id == 'relic-alpha'
        assert not result.is_fuzzy

    def test_plain_part_name_is_the_top_mark(self, index):
        result = index.resolve('r alp shoulder')
        assert result.entry.object_id == 'DA_Module_ShoulderRelicAlpha01.0'
        assert result.entry.display_name == 'Relic Alpha Shoulder Mk. II'

    def test_multi_word_expansion(self, index):
        assert index.resolve('r alp shoulder mk2').entry.object_id == 'DA_Module_ShoulderRelicAlpha01.0'

    def test_longest_shorthand_first(self, index):
        for query in ('r alp 2', 'r alp mk 2', 'r alp mk. 2', 'r alp shoulder 2'):
            assert index.resolve(query).entry.object_id == 'DA_Module_ShoulderRelicAlpha01.0', query

    def test_suggestions_are_distinct(self, index):
        result = index.resolve('relic alp shoulder mk')
        assert len(result.suggestions) == len(set(map(id, result.suggestions)))

    def test_real_name_is_never_expanded(self, index):
        assert index.resolve('vanguard').entry.object_id == 'DA_Pilot_Common3.0'

    def test_fuzzy_after_expansion(self, index):
        result = index.resolve('r alpah')
        assert result.entry.object_id == 'relic-alpha'
        assert result.is_fuzzy

    def test_autocomplete_expands(self, index):
        assert index.autocomplete('r alp')[0].object_id == 'relic-alpha'


class TestHints:
    def test_hint_is_plain_name_when_unique(self, index):
        assert index.resolve('kate sinclair').entry.hint == 'Kate Sinclair'

    def test_hint_uses_prefix_for_lower_priority_type(self, index):
        talent = index.resolve('talent:vanguard').entry
        assert talent.hint == 'talent:Vanguard'
        assert index.resolve(talent.hint).entry is talent

    def test_hint_uses_alias_for_robot_part(self, index):
        part = index.resolve('alpha chassis').entry
        assert part.hint == 'Alpha Chassis'

    def test_every_hint_resolves_to_its_entry(self, index):
        for entry in index.entries:
            result = index.resolve(entry.hint)
            assert result.entry is entry and not result.is_fuzzy, entry.hint


class TestDescriptions:
    def test_description_is_the_objects_own_without_meta(self, index):
        assert index.resolve('Scourge').entry.description == 'Sustains a focused beam.'

    def test_description_with_placeholders_is_dropped(self, index):
        assert index.resolve('talent:vanguard').entry.description == ''


class TestAutocomplete:
    def test_autocomplete_finds_partial(self, index):
        names = [e.display_name for e in index.autocomplete('kat')]
        assert names[0] == 'Kate Sinclair'

    def test_autocomplete_respects_prefix(self, index):
        entries = index.autocomplete('talent:van')
        assert entries and all(e.object_type.name == 'PilotTalent' for e in entries)

    def test_autocomplete_empty_text(self, index):
        assert index.autocomplete('') == []
