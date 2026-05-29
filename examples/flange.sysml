// Flange with multiple bolt holes — demonstrates nested CSG differences
//
// The top-level part is a union of a base plate and a boss, with
// bolt holes subtracted.  Each hole is an operator="difference" group.

package Flange {

    part flange {
        attribute operator = "difference";
        attribute length  = 120.0;
        attribute width   = 80.0;
        attribute height  = 20.0;
        attribute boltDiameter = 6.0;
        attribute boltHeight   = 20.0;

        // --- Base plate ------------------------------------------------
        part plate {
            attribute length = 120.0;
            attribute width  = 80.0;
            attribute height = 20.0;
        }

        // --- Bolt hole 1 (bottom-left) ---------------------------------
        part hole1 {
            attribute operator = "difference";
            part bolt {
                attribute height = 20.0;
                attribute radius = 3.0;
                attribute x = 15.0;
                attribute y = 15.0;
            }
        }

        // --- Bolt hole 2 (bottom-right) --------------------------------
        part hole2 {
            attribute operator = "difference";
            part bolt {
                attribute height = 20.0;
                attribute radius = 3.0;
                attribute x = 105.0;
                attribute y = 15.0;
            }
        }

        // --- Bolt hole 3 (top-left) ------------------------------------
        part hole3 {
            attribute operator = "difference";
            part bolt {
                attribute height = 20.0;
                attribute radius = 3.0;
                attribute x = 15.0;
                attribute y = 65.0;
            }
        }

        // --- Bolt hole 4 (top-right) -----------------------------------
        part hole4 {
            attribute operator = "difference";
            part bolt {
                attribute height = 20.0;
                attribute radius = 3.0;
                attribute x = 105.0;
                attribute y = 65.0;
            }
        }
    }

}
