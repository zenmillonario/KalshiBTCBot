import unittest

from strategy_core.adapters.r22_physical_packet import (
    frame_from_r22_physical_packet,
)
from strategy_core.shadow_engine import (
    ToolRackShadowEngine,
)


class R22PhysicalPacketAdapterTests(unittest.TestCase):
    def packet(
        self,
        *,
        side="NO",
        release=False,
        release_side=None,
        legacy_heist=False,
    ):
        sg = -1 if side == "NO" else 1
        af = {
            "command_pilot": {
                "side": side,
                "actual_ema9_compass": {
                    "side": side,
                    "kind": "CONTINUATION",
                },
                "heist_owns_territory": legacy_heist,
            }
        }
        facts = {
            "evidence": {
                "territory_context": {
                    "e30d30": sg * 2.0,
                    "e30d60": sg * 4.0,
                    "rail_parallel_ema_geometry": True,
                    "rail_persistence_proven": True,
                    "rail_recent_owner_wall_count": 2,
                    "rail_wall_rollovers_observed": 1,
                    "rail_price_supported": True,
                    "simple_mountain_alternating": False,
                    "regular_clean_mountain": True,
                    "territory_handoff_proven": release,
                    "terrain_release_catcher_ready": release,
                    "territory_handoff_side": release_side,
                    "terrain_release_catcher_side": release_side,
                    "qualified_heist_handoff_from_rail": legacy_heist,
                    "terrain_tool": (
                        "HEIST" if legacy_heist else "RAIL"
                    ),
                }
            },
            "routes": {
                "rail_flow_entry": {
                    "eligible": False,
                    "side": side,
                }
            },
        }
        return af, facts

    def frame(self, af, facts, *, yes=0.70, no=0.30):
        return frame_from_r22_physical_packet(
            af=af,
            facts=facts,
            now_ts=1000,
            ticker="KX1",
            contract_age_s=20,
            yes_ask=yes,
            no_ask=no,
            quote_current=True,
            depth_available=True,
        )

    def test_legacy_route_false_cannot_starve_tool_rack_rail(self):
        af, facts = self.packet(side="NO")
        out = ToolRackShadowEngine().evaluate(
            self.frame(af, facts)
        )
        self.assertEqual(
            out["owned_territory"],
            "DOWN_RAIL",
        )
        self.assertEqual(
            out["commander_action"],
            "ENTER",
        )
        self.assertEqual(
            out["accepted_side"],
            "NO",
        )

    def test_adapter_derives_up_rail_from_physical_slopes(self):
        af, facts = self.packet(side="YES")
        out = ToolRackShadowEngine().evaluate(
            self.frame(
                af,
                facts,
                yes=0.30,
                no=0.70,
            )
        )
        self.assertEqual(
            out["owned_territory"],
            "UP_RAIL",
        )
        self.assertEqual(
            out["commander_action"],
            "ENTER",
        )
        self.assertEqual(
            out["accepted_side"],
            "YES",
        )

    def test_legacy_release_label_alone_cannot_trigger_release_watcher(self):
        af, facts = self.packet(
            side="NO",
            release=True,
            release_side="YES",
        )
        out = ToolRackShadowEngine().evaluate(
            self.frame(af, facts)
        )
        self.assertEqual(
            out["owned_territory"],
            "DOWN_RAIL",
        )
        self.assertEqual(
            out["commander_action"],
            "ENTER",
        )
        self.assertEqual(
            out["accepted_tool"],
            "RAIL",
        )

    def test_legacy_heist_label_alone_cannot_take_tool_rack_authority(self):
        af, facts = self.packet(
            side="NO",
            legacy_heist=True,
        )
        out = ToolRackShadowEngine().evaluate(
            self.frame(af, facts)
        )
        self.assertEqual(
            out["owned_territory"],
            "DOWN_RAIL",
        )
        self.assertEqual(
            out["active_tool"],
            "RAIL",
        )


if __name__ == "__main__":
    unittest.main()
