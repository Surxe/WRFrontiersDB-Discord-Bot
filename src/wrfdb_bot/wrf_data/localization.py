"""Reading localized text from WRFrontiersDB-Data objects."""

LocalizationKey = dict


def default_string(localization_key: LocalizationKey | None) -> str:
    """English text of a localization key, or "" if it has none.

    Mirrors the Site's getDefaultString: a key with Key+TableNamespace prefers `en`
    (proper English), otherwise `InvariantString` comes first.
    """
    if not localization_key:
        return ''
    if localization_key.get('Key') and localization_key.get('TableNamespace'):
        order = ('en', 'InvariantString')
    else:
        order = ('InvariantString', 'en')
    for field in order:
        text = localization_key.get(field)
        if text:
            return text
    return ''
