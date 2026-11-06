# Tool Rack PID19832 Fade / Peak-Lock PAPER handoff — 2026-10-28

PAPER only. One Commander and passive PAPER executor remain unchanged.

Implemented from PID19832 forensics:
- Rail counter-fades are restrained: ordinary local Mountain pauses no longer pay against an owned smooth Rail. Whole-parent/full-arc turns and genuine repeatable Heist edges remain legal.
- +100% full-lot executable gain earns a 5% rolling peak-bid floor automatically.
- +150% tightens the rolling band to 3%; +600% to 2%. Floors are irreversible and use existing native full-remaining-lot depth rules.
- Physical/third-weakness logic still controls ordinary +50% first-arm and structural collection. It can tighten protection but cannot suppress the +100/+150 earned peak lock.
- PRIMARY full-arc ask <= .20 uses $25; >.20 through .30 uses $15; otherwise normal Mountain sizing. Tactical cheap fades cannot receive $25 from price alone.

No timer-based top exit was introduced. The stall timer remains a future study; this build uses observable executable peak giveback instead of guessing the top.

Validation controls include PID7516 recorded high-ROI replay: .15 basis -> .43 executable peak earns 3% floor .4171 and breaches at .41, while the physical leg is still classified as breathing.
