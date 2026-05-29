// Flange with four bolt through-holes.
//
// Demonstrates multiple negatives in a single difference operation.
// The positive is the base plate; each hole is a negative.

package Flange {

    part flange {
        attribute operator = "difference";

        // --- Positive: base plate -------------------------------------------
        part plate {
            attribute role = "positive";
            attribute length = 120.0 [mm];
            attribute width  = 80.0 [mm];
            attribute height = 20.0 [mm];
        }

        // --- Negatives: four bolt through-holes -----------------------------
        part hole1 {
            attribute role = "negative";
            attribute height = 20.0 [mm];
            attribute radius = 3.0 [mm];
            attribute x = 15.0 [mm];
            attribute y = 15.0 [mm];
        }

        part hole2 {
            attribute role = "negative";
            attribute height = 20.0 [mm];
            attribute radius = 3.0 [mm];
            attribute x = 105.0 [mm];
            attribute y = 15.0 [mm];
        }

        part hole3 {
            attribute role = "negative";
            attribute height = 20.0 [mm];
            attribute radius = 3.0 [mm];
            attribute x = 15.0 [mm];
            attribute y = 65.0 [mm];
        }

        part hole4 {
            attribute role = "negative";
            attribute height = 20.0 [mm];
            attribute radius = 3.0 [mm];
            attribute x = 105.0 [mm];
            attribute y = 65.0 [mm];
        }
    }

}
