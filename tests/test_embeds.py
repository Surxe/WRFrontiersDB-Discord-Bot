from wrfdb_bot.services.lookup.embeds import reply_kwargs
from wrfdb_bot.services.lookup.views import LookupButton


class TestReplyKwargs:
    def test_reply_embeds_for_matches_and_text_for_misses(self, index):
        results = [index.resolve('Alpha'), index.resolve('zzqx @everyone')]
        kwargs = reply_kwargs(results)
        assert len(kwargs['embeds']) == 1
        embed = kwargs['embeds'][0]
        assert embed.title == 'Alpha'
        assert embed.url.endswith('/robots/alpha/')
        assert embed.fields[0].name == 'Also matches'
        assert 'No match for' in kwargs['content']
        assert kwargs['allowed_mentions'].everyone is False

    def test_robot_shows_its_torso_description(self, index):
        embed = reply_kwargs([index.resolve('Alpha')])['embeds'][0]
        assert (embed.fields[-1].name, embed.fields[-1].value) == ('Alpha Torso', 'Pulls a target in.')
        assert all(f.name != 'Alpha Torso' for f in reply_kwargs([index.resolve('Kate Sinclair')])['embeds'][0].fields)

    def test_reply_marks_fuzzy_and_missing_page(self, index):
        fuzzy = reply_kwargs([index.resolve('Kate Sinclar')])['embeds'][0]
        assert 'closest match' in fuzzy.footer.text
        unlinked = reply_kwargs([index.resolve('Unlinked')])['embeds'][0]
        assert unlinked.url is None
        assert 'no page on the site yet' in unlinked.footer.text

    def test_footer_names_the_data_version(self, index):
        assert index.version == '2026-01-01'
        embed = reply_kwargs([index.resolve('Alpha')], index.version)['embeds'][0]
        assert embed.footer.text.endswith(' - Data 2026-01-01')
        assert reply_kwargs([index.resolve('Alpha')])['embeds'][0].footer.text == 'Robot'


class TestLookupButtons:
    def test_a_button_per_other_match_carrying_its_object(self, index):
        result = index.resolve('Alpha')
        view = reply_kwargs([result])['view']
        assert [b.item.custom_id for b in view.children] == [
            f'wrf:lookup:{o.object_type.name}:{o.object_id}' for o in result.other_matches
        ]
        assert [b.item.label for b in view.children][0] == result.other_matches[0].display_name

    def test_buttons_for_suggestions(self, index):
        result = index.resolve('Kate Sinc Mayflwr')
        assert result.entry is None and result.suggestions
        view = reply_kwargs([result])['view']
        assert len(view.children) == len(result.suggestions)

    def test_no_view_without_other_matches_or_suggestions(self, index):
        assert 'view' not in reply_kwargs([index.resolve('Kate Sinclair')])
        assert 'view' not in reply_kwargs([index.resolve('zzqx')])

    def test_no_button_for_an_answered_query_and_no_repeats(self, index):
        alpha = index.resolve('Alpha')
        first_other = index.resolve(alpha.other_matches[0].hint)
        view = reply_kwargs([alpha, alpha, first_other])['view']
        ids = [b.item.custom_id for b in view.children]
        assert len(ids) == len(set(ids))
        assert f'wrf:lookup:{first_other.entry.object_type.name}:{first_other.entry.object_id}' not in ids

    def test_button_round_trips_to_its_entry(self, index):
        other = index.resolve('Alpha').other_matches[0]
        match = LookupButton.__discord_ui_compiled_template__.fullmatch(
            f'wrf:lookup:{other.object_type.name}:{other.object_id}'
        )
        assert index.entry(match['type_name'], match['object_id']) is other
        assert index.resolve(other.hint).entry is other
        assert index.entry('Module', 'gone') is None
