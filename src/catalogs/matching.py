"""Default catalog matching conventions and provider adapter lookup."""


class GenericMatching:
    """Conservative defaults for catalogs without specialized conventions.

    Methods receive catalog-relative PurePosixPath objects. Aliases receive the
    normalized filename name and return normalized alternatives. Station names
    are returned as raw text for the engine to normalize. Variant families
    return (family_key, attribute_set), or None when not recognized.
    """

    def filename_name(self, path):
        return path.stem

    def aliases(self, path, name):
        return ()

    def callsigns(self, path):
        return ()

    def station_name(self, path):
        return None

    def is_generic_network(self, path):
        return False

    def variant_family(self, path):
        return None


GENERIC_MATCHING = GenericMatching()


def matching_adapter(catalog):
    """Resolve a provider or legacy catalog ID to its matching adapter."""
    adapter = getattr(catalog, "matching", None)
    if adapter is not None:
        return adapter
    if isinstance(catalog, str) and catalog:
        from . import find_catalog
        provider = find_catalog(catalog)
        if provider is not None:
            return getattr(provider, "matching", GENERIC_MATCHING)
    return GENERIC_MATCHING
