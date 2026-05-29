// Subtract a cylindrical through-hole from a block.
//
// Demonstrates the explicit role convention:
//   role = "positive"  — the shape being kept
//   role = "negative"  — the shape being removed

package SubtractiveExample {

    part blockWithHole {
        attribute operator = "difference";
        attribute length  = 100.0 [mm];
        attribute width   = 60.0 [mm];
        attribute height  = 40.0 [mm];

        // --- Positive: the base block ---------------------------------
        part block {
            attribute role = "positive";
            attribute length = 100.0 [mm];
            attribute width  = 60.0 [mm];
            attribute height = 40.0 [mm];
        }

        // --- Negative: a through-hole (cylinder) ----------------------
        part throughHole {
            attribute role = "negative";
            attribute height = 40.0 [mm];
            attribute radius = 10.0 [mm];
            attribute x = 50.0 [mm];
            attribute y = 30.0 [mm];
        }
    }

}
