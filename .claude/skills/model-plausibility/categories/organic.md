# Plants, trees and natural arrangements

- **Growth logic:**
  - roots come out of buttresses at the trunk's base and enter the soil;
  - branches fork from the trunk, thin ones from thick ones;
  - leaves sit at the tips of the thin branches.
- **Foliage:**
  - leaf-shaped double-sided cards in clusters at the branch tips;
  - normals point out of the cluster, so the crown takes light as one volume;
  - the leaves stay out of the atlas (`finish_textured(untextured=...)`) with their own AO.
  The construction gate leaves foliage parts out.
- **Bark and surfaces:** dark patches in a video are often leaf shadows, not paint. Do not bake lighting into textures. Grime goes only where it really occurs.
- **Natural placement** (apples in a crate, stones along a bed edge) comes from physics, not from hand layout: `om.settle(bodies, colliders)`.
- **What the source never shows** (a crown above the frame) is built from the garden's sizes and colours with a known stylised technique, and marked `guess`.
