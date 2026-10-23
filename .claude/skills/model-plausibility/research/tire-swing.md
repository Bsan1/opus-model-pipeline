# Tire swing (rope, knots, tyre)
Researched: 21 October 2026, for `tire_swing.py` (written down 23 October 2026 from the generator's notes)
## Sources
- Tire swing guides (Bob Vila; Instructables): the rigging. A round turn with two half hitches on the branch; the rope goes over the tyre's front shoulder, under the bead and up the back, and is tied round the standing part on top.
- Laid rope references: three strands twisted right-handed (Z-lay) round each other, the yarns twisted the other way, so the surface yarns run roughly along the rope; the strands press into each other.
## Adopted
- Three separate strand tubes along one centreline, one turn per lay of about 3 diameters, with plain smooth normals -> `build_rope`.
- Loaded parts straight, the tyre hanging right under where the rope leaves the branch's side; bends of at least one diameter; free tails hanging under gravity -> the rope path and `rope_audit`.
- A tall-sidewall 195/80 R13 tyre (63 cm outer diameter, a 33 cm bead opening) -> `TIRE_*` sizes.
## Rejected
- A single tube with a ripple texture: it read as a bent metal pipe (lessons L1).
