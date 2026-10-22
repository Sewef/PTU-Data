import sys
import types
import unittest

try:
    import aiohttp  # noqa: F401
except ModuleNotFoundError:
    aiohttp_stub = types.ModuleType("aiohttp")
    aiohttp_stub.ClientSession = object
    sys.modules["aiohttp"] = aiohttp_stub

import filter_levelup_moves
import update_moves_from_pokeapi


class MoveReminderTests(unittest.TestCase):
    def test_displaced_level_one_moves_become_move_reminder_entries(self):
        level_up = {
            "sun-moon": [
                (1, 1, "brave-bird"),
                (1, 2, "poison-jab"),
                (1, 3, "peck"),
                (1, 4, "sand-attack"),
                (1, 5, "leer"),
                (1, 6, "fury-cutter"),
                (55, None, "brave-bird"),
            ]
        }

        natural, reminder = update_moves_from_pokeapi.split_move_reminder_entries(level_up)

        self.assertEqual(
            reminder["sun-moon"],
            [(1, 1, "brave-bird"), (1, 2, "poison-jab")],
        )
        self.assertNotIn((1, 1, "brave-bird"), natural["sun-moon"])
        self.assertNotIn((1, 2, "poison-jab"), natural["sun-moon"])
        self.assertIn((55, None, "brave-bird"), natural["sun-moon"])

    def test_four_or_fewer_starting_moves_are_unchanged(self):
        level_up = {
            "sword-shield": [
                (1, 1, "peck"),
                (1, 2, "sand-attack"),
                (5, None, "leer"),
            ]
        }

        natural, reminder = update_moves_from_pokeapi.split_move_reminder_entries(level_up)

        self.assertEqual(natural, level_up)
        self.assertEqual(reminder, {})

    def test_lower_legacy_level_wins_during_deduplication(self):
        moves = [
            {"Move": "Brave Bird", "Level": 65, "Type": "Flying"},
            {
                "Move": "Brave Bird",
                "Level": 1,
                "Type": "Flying",
                "Tags": ["Legacy", "Sun/Moon"],
            },
        ]

        filtered = filter_levelup_moves.filter_levelup(moves, is_evolved=False)

        self.assertEqual(
            filtered,
            [
                {
                    "Move": "Brave Bird",
                    "Level": 1,
                    "Type": "Flying",
                    "Tags": ["Legacy", "Sun/Moon"],
                }
            ],
        )

    def test_smeargle_keeps_every_sketch_level(self):
        pokedex = [
            {
                "Species": "Smeargle",
                "Evolution": [{"Stade": 1, "Species": "Smeargle", "Condition": ""}],
                "Moves": {
                    "Level Up Move List": [
                        {"Move": "Sketch", "Level": level, "Type": "Normal"}
                        for level in (1, 11, 21, 31, 41, 51, 61, 71, 81, 91)
                    ]
                },
            }
        ]

        processed = filter_levelup_moves.process_pokedex(pokedex)

        self.assertEqual(
            [entry["Level"] for entry in processed[0]["Moves"]["Level Up Move List"]],
            [1, 11, 21, 31, 41, 51, 61, 71, 81, 91],
        )

    def test_bdsp_slug_matches_pokeapi(self):
        self.assertIn("brilliant-diamond-shining-pearl", update_moves_from_pokeapi.VERSION_GROUPS)
        self.assertNotIn(
            "brilliant-diamond-and-shining-pearl",
            update_moves_from_pokeapi.VERSION_GROUPS,
        )

    def test_form_mapping_keys_do_not_fall_back_to_base_species(self):
        entry = {"Species": "Samurott", "Form": "Hisui"}

        self.assertEqual(
            update_moves_from_pokeapi.mapping_key_for_entry(entry),
            "Samurott Hisui",
        )

    def test_duplicate_species_are_distinguished_by_form(self):
        entries = [
            {"Species": "Basculegion", "Form": "Male"},
            {"Species": "Basculegion", "Form": "Female"},
        ]

        keys = [update_moves_from_pokeapi.mapping_key_for_entry(entry) for entry in entries]

        self.assertEqual(keys, ["Basculegion Male", "Basculegion Female"])


class BuildMovesIntegrationTests(unittest.IsolatedAsyncioTestCase):
    async def test_missing_pokemon_slug_uses_species_default_variety(self):
        requested_urls = []

        async def fake_fetch_json(_session, url, **_kwargs):
            requested_urls.append(url)
            if url.endswith("/pokemon/frillish"):
                return None
            if url.endswith("/pokemon-species/frillish"):
                return {
                    "evolves_from_species": None,
                    "varieties": [
                        {"is_default": True, "pokemon": {"name": "frillish-male"}}
                    ],
                }
            if url.endswith("/pokemon/frillish-male"):
                return {
                    "species": {"url": "https://example.test/species/frillish"},
                    "moves": [],
                }
            self.fail(f"Unexpected URL: {url}")

        original_fetch_json = update_moves_from_pokeapi.fetch_json
        update_moves_from_pokeapi.fetch_json = fake_fetch_json
        try:
            result = await update_moves_from_pokeapi.build_moves_for_pokemon(
                object(), "frillish", 4, 9, {}
            )
        finally:
            update_moves_from_pokeapi.fetch_json = original_fetch_json

        self.assertEqual(result, {"level_up": [], "machine": [], "tutor": [], "egg": []})
        self.assertTrue(any(url.endswith("/pokemon/frillish-male") for url in requested_urls))

    async def test_displaced_moves_are_emitted_as_tutor_not_level_one(self):
        def detail(version_group, level, order=None, method="level-up"):
            return {
                "level_learned_at": level,
                "order": order,
                "version_group": {"name": version_group},
                "move_learn_method": {"name": method},
            }

        pokemon = {
            "species": {"url": "https://example.test/species/farfetchd"},
            "moves": [
                {
                    "move": {"name": "brave-bird"},
                    "version_group_details": [
                        detail("sun-moon", 1, 1),
                        detail("sun-moon", 55),
                        detail("sword-shield", 65),
                    ],
                },
                {
                    "move": {"name": "poison-jab"},
                    "version_group_details": [
                        detail("sun-moon", 1, 2),
                        detail("sword-shield", 0, method="machine"),
                    ],
                },
                {"move": {"name": "peck"}, "version_group_details": [detail("sun-moon", 1, 3)]},
                {"move": {"name": "sand-attack"}, "version_group_details": [detail("sun-moon", 1, 4)]},
                {"move": {"name": "leer"}, "version_group_details": [detail("sun-moon", 1, 5)]},
                {"move": {"name": "fury-cutter"}, "version_group_details": [detail("sun-moon", 1, 6)]},
            ],
        }

        async def fake_fetch_json(_session, url, **_kwargs):
            if url.endswith("/pokemon/farfetchd"):
                return pokemon
            return {"evolves_from_species": None}

        async def fake_get_move_type(_session, slug, _cache):
            return "Poison" if slug == "poison-jab" else "Flying"

        original_fetch_json = update_moves_from_pokeapi.fetch_json
        original_get_move_type = update_moves_from_pokeapi.get_move_type
        update_moves_from_pokeapi.fetch_json = fake_fetch_json
        update_moves_from_pokeapi.get_move_type = fake_get_move_type
        try:
            result = await update_moves_from_pokeapi.build_moves_for_pokemon(
                object(), "farfetchd", 4, 9, {}
            )
        finally:
            update_moves_from_pokeapi.fetch_json = original_fetch_json
            update_moves_from_pokeapi.get_move_type = original_get_move_type

        tutor_names = {entry["Move"] for entry in result["tutor"]}
        self.assertIn("Brave Bird", tutor_names)
        self.assertIn("Poison Jab", tutor_names)
        self.assertFalse(
            any(
                entry["Move"] in {"Brave Bird", "Poison Jab"} and entry["Level"] == 1
                for entry in result["level_up"]
            )
        )
        self.assertTrue(
            any(entry["Move"] == "Brave Bird" and entry["Level"] == 65 for entry in result["level_up"])
        )


if __name__ == "__main__":
    unittest.main()
