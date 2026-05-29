// Flange with four bolt through-holes.
//
// Subtractive pattern:
//   plate       — the base shape (child 1 of "flange")
//   hole1..hole4 — cylinders to remove (children 2..N of "flange")
// The bridge maps operator="difference" → Difference(plate, [hole1..hole4]).

package Flange {

    part flange {
        attribute operator = "difference";
        attribute length  = 120.0 [mm];
        attribute width   = 80.0 [mm];
        attribute height  = 20.0 [mm];

        // --- Child 1: the positive ------------------------------------------
        part plate {
            attribute length = 120.0 [mm];
            attribute width  = 80.0 [mm];
            attribute height = 20.0 [mm];
        }

        // --- Children 2..N: negatives (through-holes) -----------------------
        // Each cylinder is positioned on the plate face.
        // The bridge treats all child parts of a "difference" as negatives
        // (except the first, which is the positive).

        part hole1 {
            attribute height = 20.0 [mm];
            attribute radius = 3.0 [mm];
            attribute x = 15.0 [mm];
            attribute y = 15.0 [mm];
        }

        part hole2 {
            attribute height = 20.0 [mm];
            attribute radius = 3.0 [mm];
            attribute x = 105.0 [mm];
            attribute y = 15.0 [mm];
        }

        part hole3 {
            attribute height = 20.0 [mm];
            attribute radius = 3.0 [mm];
            attribute x = 15.0 [mm];
            attribute y = 65.0 [mm];
        }

        part hole4 {
            attribute height = 20.0 [mm];
            attribute radius = 3.0 [mm];
            attribute x = 105.0 [mm];
            attribute y = 65.0 [mm];
        }
    }

}
