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
    ):
        sg = -1 if side == "NO" else 1
        af = {
            "command_pilot": {
                "side": side,
                "actual_ema9_compass": {
                    "side": side,
                    "kind": "CONTINUATION",
                },
                "heist_owns_territory": False,
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
                    "qualified_heist_handoff_from_rail": False,
                    "terrain_tool": "RAIL",
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

    def test_legacy_route_false_cannot_starve_tool_rack_rail(self):
        af, facts = self.packet(side="NO")
        frame = frame_from_r22_physical_packet(
            af=af,
            facts=facts,
            now_ts=1000,
            ticker="KX1",
            contract_age_s=20,
            yes_ask=0.70,
            no_ask=0.30,
            quote_current=True,
            depth_available=True,
        )
        out = ToolRackShadowEngine().evaluate(
            frame
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
        frame = frame_from_r22_physical_packet(
            af=af,
            facts=facts,
            now_ts=1000,
            ticker="KX1",
            contract_age_s=20,
            yes_ask=0.30,
            no_ask=0.70,
            quote_current=True,
            depth_available=True,
        )
        out = ToolRackShadowEngine().evaluate(
            frame
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


if __name__ == "__main__":
    unittest.main()
