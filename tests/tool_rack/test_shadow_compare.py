import unittest

from strategy_core.shadow_compare import (
    PaperEntry,
    compare_shadow_to_paper,
)


def territory(seq,ts,name,side):
    return {
        "seq":seq,
        "ts":ts,
        "ticker":"KX1",
        "event_type":"TERRITORY",
        "territory":name,
        "side":side,
        "tool":"RAIL" if "RAIL" in name else None,
        "overlay":["RELEASE_WATCHER"],
        "action":"WAIT",
        "accepted_side":None,
        "opportunity_id":None,
        "reason":"owner",
        "observed_ask":None,
        "max_price":None,
        "release_boundary":None,
        "metadata":{},
    }


def intent(seq,ts,side,ask,op):
    return {
        "seq":seq,
        "ts":ts,
        "ticker":"KX1",
        "event_type":"INTENT",
        "territory":"DOWN_RAIL",
        "side":"NO",
        "tool":"RAIL",
        "overlay":["RELEASE_WATCHER"],
        "action":"ENTER",
        "accepted_side":side,
        "opportunity_id":op,
        "reason":"COMMANDER_ACCEPTED_TOOL_INTENT",
        "observed_ask":ask,
        "max_price":0.40,
        "release_boundary":None,
        "metadata":{},
    }


class ShadowCompareTests(unittest.TestCase):
    def test_same_side_match_reports_delay_and_price_chase(self):
        timeline={"events":[
            territory(1,1000,"DOWN_RAIL","NO"),
            intent(2,1010,"NO",0.30,"OP1"),
        ]}
        entries=[
            PaperEntry(
                index=0,ts=1040,ticker="KX1",trade_id="7",
                side="NO",price=0.43,reason="legacy"
            )
        ]
        report=compare_shadow_to_paper(timeline,entries)
        row=report["matches"][0]
        self.assertEqual(row["classification"],"MATCHED_SAME_SIDE")
        self.assertEqual(row["delay_seconds"],30)
        self.assertAlmostEqual(row["price_delta"],0.13)
        self.assertEqual(report["summary"]["matched_same_side"],1)

    def test_duplicate_actionable_events_same_opportunity_count_once(self):
        timeline={"events":[
            territory(1,1000,"DOWN_RAIL","NO"),
            intent(2,1010,"NO",0.39,"OP1"),
            intent(3,1020,"NO",0.35,"OP1"),
        ]}
        entries=[]
        report=compare_shadow_to_paper(timeline,entries)
        self.assertEqual(
            report["summary"]["shadow_actionable_events"],
            2,
        )
        self.assertEqual(
            report["summary"]["shadow_unique_opportunities"],
            1,
        )
        self.assertEqual(
            report["summary"]["missed_shadow"],
            1,
        )

    def test_same_time_other_ticker_never_matches(self):
        timeline={"events":[
            territory(1,1000,"DOWN_RAIL","NO"),
            intent(2,1010,"NO",0.30,"OP1"),
        ]}
        entries=[
            PaperEntry(
                index=0,ts=1015,ticker="KX2",trade_id="8",
                side="NO",price=0.31,reason="legacy"
            )
        ]
        report=compare_shadow_to_paper(timeline,entries)
        self.assertEqual(
            report["summary"]["matched_same_side"],
            0,
        )
        self.assertEqual(
            report["summary"]["paper_only"],
            1,
        )
        self.assertEqual(
            report["summary"]["missed_shadow"],
            1,
        )

    def test_opposite_paper_entry_is_called_out(self):
        timeline={"events":[
            territory(1,1000,"DOWN_RAIL","NO"),
            intent(2,1010,"NO",0.30,"OP1"),
        ]}
        entries=[
            PaperEntry(
                index=0,ts=1020,ticker="KX1",trade_id="8",
                side="YES",price=0.35,reason="legacy"
            )
        ]
        report=compare_shadow_to_paper(timeline,entries)
        self.assertEqual(
            report["matches"][0]["classification"],
            "OPPOSITE_PAPER_ENTRY",
        )
        self.assertEqual(
            report["summary"]["opposite_paper_entry"],
            1,
        )

    def test_same_side_pairing_wins_over_earlier_opposite_paper_entry(self):
        timeline={"events":[
            territory(1,1000,"ALTERNATING_MOUNTAIN","NO"),
            intent(2,1100,"NO",0.30,"NO_OP"),
        ]}
        entries=[
            PaperEntry(
                index=0,ts=1090,ticker="KX1",trade_id="10",
                side="YES",price=0.52,reason="legacy"
            ),
            PaperEntry(
                index=1,ts=1110,ticker="KX1",trade_id="11",
                side="NO",price=0.35,reason="legacy"
            ),
        ]
        report=compare_shadow_to_paper(
            timeline,
            entries,
            before_seconds=120,
            after_seconds=120,
        )
        rows={
            row["paper"]["trade_id"]: row
            for row in report["paper_comparisons"]
        }
        self.assertEqual(
            rows["10"]["classification"],
            "PAPER_ONLY",
        )
        self.assertEqual(
            rows["11"]["classification"],
            "MATCHED_SAME_SIDE",
        )

    def test_missed_shadow_and_paper_only_against_rail_are_counted(self):
        timeline={"events":[
            territory(1,1000,"DOWN_RAIL","NO"),
            intent(2,1010,"NO",0.30,"OP1"),
        ]}
        entries=[
            PaperEntry(
                index=0,ts=1200,ticker="KX1",trade_id="9",
                side="YES",price=0.30,reason="legacy"
            )
        ]
        report=compare_shadow_to_paper(
            timeline,
            entries,
            after_seconds=60,
        )
        self.assertEqual(
            report["summary"]["missed_shadow"],
            1,
        )
        self.assertEqual(
            report["summary"]["paper_only_against_shadow_territory"],
            1,
        )


if __name__=="__main__":
    unittest.main()
