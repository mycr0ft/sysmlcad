// Subtract a cylindrical through-hole from a block.
//
// This is the canonical subtractive (difference) pattern:
//   operator = "difference"  on the parent part
//   first child              = the base shape (the "positive")
//   remaining children       = the shapes to remove ("negatives")
//
// The bridge maps this to a Difference(positive, [negative1, negative2, ...]).

package SubtractiveExample {

    part blockWithHole {
        attribute operator = "difference";
        attribute length  = 100.0 [mm];
        attribute width   = 60.0 [mm];
        attribute height  = 40.0 [mm];

        // --- Positive: the base block ---------------------------------
        part block {
            attribute length = 100.0 [mm];
            attribute width  = 60.0 [mm];
            attribute height = 40.0 [mm];
        }

        // --- Negative: a through-hole (cylinder taller than block) -----
        part throughHole {
            // A cylinder that is the full height of the block.
            // Because the hole is taller (or equal), it cuts all the
            // way through — a "through-hole".
            attribute height = 40.0 [mm];
            attribute radius = 10.0 [mm];
            attribute x = 50.0 [mm];   // center on the block face
            attribute y = 30.0 [mm];
        }
    }

}
