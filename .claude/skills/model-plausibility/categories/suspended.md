# Suspended objects, rope and cable

- **Study real rigging first** (guides, photos), then build what they show. A tire swing hangs from a round turn plus two half hitches on the branch, and its loop goes round the tire's cross-section, closed by two half hitches on top.
- **The load path is the shape.**
  - Loaded rope runs straight: the hanging part is vertical, and the tire hangs right under the point where the rope leaves the branch (the branch's side, not its middle).
  - The loop lies tight on what it binds.
  - Turns lie against each other.
  - Free tails hang under gravity and rest on what is below them.
- **Bends are at least about one rope diameter.** Rope parts never pass through each other; they lie against each other at two radii apart.
- **Rope is made of strands.** Model three strands (Z-lay, one turn per about 3 diameters) along one continuous centreline, with plain smooth normals. A single tube with area-weighted normals reads as a bent metal pipe.
- **Measure it.** The rope audit fails the build on rope-to-rope distance under 1.9 R, bends under 0.75 D, or the loop off the tyre (see `tire_swing.py`). `model.route` checks that the hanging rope reaches the tire. A point where the rope spans a gap (under the bead, across the hole) touches nothing, so do not use it as a route end.
- **The support is outside the model** (the branch, a hook, a beam). Name it in the plan's `supports`; list the route points on it in `free`.
