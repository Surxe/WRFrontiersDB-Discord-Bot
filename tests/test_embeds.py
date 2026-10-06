from wrfdb_bot.services.lookup.embeds import reply_kwargs


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
