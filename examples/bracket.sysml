// Parametric bracket with centered hole — demonstrates subtractive geometry
// with explicit role annotations on operands.

package Bracket {

    part bracket {
        attribute operator = "difference";
        attribute length  = 100.0 [mm];
        attribute width   = 50.0 [mm];
        attribute height  = 30.0 [mm];

        // --- Positive: the base shape (material to keep) -----------------
        part base {
            attribute role = "positive";
            attribute length = 100.0 [mm];
            attribute width  = 50.0 [mm];
            attribute height = 30.0 [mm];
        }

        // --- Negative: the shape to remove (a through-hole) --------------
        part hole {
            attribute role = "negative";
            attribute height = 30.0 [mm];
            attribute radius = 5.0 [mm];
            attribute x = 50.0 [mm];   // center on bracket face
            attribute y = 25.0 [mm];
        }
    }

}
