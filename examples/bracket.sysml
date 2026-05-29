// Parametric bracket with centered hole — SysMLv2 with explicit SI unit
// annotations.  The bridge maps attribute operator = "difference" to a
// CSG Difference over the child parts.

package Bracket {

    part bracket {
        attribute operator = "difference";
        attribute length  = 100.0 [mm];
        attribute width   = 50.0 [mm];
        attribute height  = 30.0 [mm];

        part base {
            attribute length = 100.0 [mm];
            attribute width  = 50.0 [mm];
            attribute height = 30.0 [mm];
        }

        part hole {
            attribute height = 30.0 [mm];
            attribute radius = 5.0 [mm];
            attribute x = 50.0 [mm];   // center on bracket face
            attribute y = 25.0 [mm];
        }
    }

}
