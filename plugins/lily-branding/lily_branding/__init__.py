"""Lily branding plugin — renames Odysseus to Lily across the UI."""


def register(host):
    import odysseus

    odysseus.log("info", "Lily branding active")
