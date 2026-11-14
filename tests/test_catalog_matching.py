from contextlib import contextmanager
import unittest

from src.automatic_run import run_automatic
from src.callsign_matching import build_callsign_index, build_station_name_index
from src.catalogs.matching import GenericMatching
from src.matching_engine import build_network_index
from src.name_matching import build_name_index
from src.variants import select_variant


class CustomMatching(GenericMatching):
    def filename_name(self, path):
        return "Example News"

    def aliases(self, path, name):
        return ("examplenetwork",)

    def callsigns(self, path):
        return ("WXYZ",) if path.parts[0] == "stations" else ()

    def station_name(self, path):
        return "Example City" if path.parts[0] == "stations" else None

    def is_generic_network(self, path):
        return path.parts[0] == "networks"

    def variant_family(self, path):
        return ("example",), ({"hd"} if "high" in path.stem else set())


class CustomCatalog:
    id = "custom"
    accepts_legacy_paths = True
    matching = CustomMatching()

    def options(self, data_dir):
        return ["networks/logo.png"]

    @contextmanager
    def resolve(self, data_dir, path):
        yield path


class CatalogMatchingTests(unittest.TestCase):
    def test_provider_controls_interpretation(self):
        catalog = CustomCatalog()
        paths = ["networks/logo.png", "stations/local.png"]
        self.assertEqual(set(build_name_index(paths, catalog)["examplenews"]), set(paths))
        self.assertEqual(set(build_name_index(paths, catalog)["examplenetwork"]), set(paths))
        self.assertEqual(build_callsign_index(paths, catalog), {"WXYZ": (paths[1],)})
        self.assertEqual(build_station_name_index(paths, catalog), {"examplecity": (paths[1],)})
        self.assertEqual(build_network_index(paths, catalog)["example"], [(("example", "news"), paths[0])])
        self.assertEqual(select_variant(["x/logo.png", "x/logo-high.png"], "hd", catalog), "x/logo-high.png")

    def test_automatic_run_uses_actual_provider_adapter(self):
        catalog = CustomCatalog()
        settings = {"automatic_groups": [{"group": "1", "strategy": "exact"}]}
        calls = []
        result = run_automatic("/data", settings, [{"id": 1, "group_id": 1, "name": "Example News"}],
                               [1], [catalog], lambda *args: calls.append(args))
        self.assertEqual(result["applied"], 1)
        self.assertEqual(calls[0][5], "custom:networks/logo.png")

    def test_unrecognized_catalog_has_conservative_defaults(self):
        paths = ["countries/canada/local/cbc-cblt-ca.png", "countries/canada/ctv-ca.png"]
        self.assertEqual(build_name_index(paths, "unknown")["ctvca"], (paths[1],))
        self.assertFalse(build_callsign_index(paths, "unknown"))
        self.assertFalse(build_station_name_index(paths, "unknown"))
        self.assertFalse(build_network_index(paths, "unknown"))
        self.assertIsNone(select_variant(["x/logo.png", "x/logo-hd.png"], "hd", "unknown"))

    def test_provider_without_adapter_does_not_borrow_registered_rules(self):
        class PlainCatalog:
            id = "tv_logos"

        path = "countries/canada/ctv-ca.png"
        self.assertEqual(build_name_index([path], PlainCatalog())["ctvca"], (path,))
        self.assertFalse(build_network_index([path], PlainCatalog()))


if __name__ == "__main__":
    unittest.main()
