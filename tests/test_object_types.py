from wrfdb_bot.wrf_data.object_types import display_name


def test_display_name_prefers_the_first_alias():
    assert display_name('Alpha', ['Alpha Chassis', 'Alpha Legs']) == 'Alpha Chassis'


def test_display_name_without_aliases_is_the_name():
    assert display_name('Railgun', ()) == 'Railgun'
