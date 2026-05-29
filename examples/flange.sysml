// Flange with four bolt holes — demonstrates nested CSG differences with
// explicit SI unit annotations.

package Flange {

    part flange {
        attribute operator = "difference";
        attribute length  = 120.0 [mm];
        attribute width   = 80.0 [mm];
        attribute height  = 20.0 [mm];

        // --- Base plate ------------------------------------------------
        part plate {
            attribute length = 120.0 [mm];
            attribute width  = 80.0 [mm];
            attribute height = 20.0 [mm];
        }

        // --- Bolt hole 1 (bottom-left) ---------------------------------
        part hole1 {
            attribute operator = "difference";
            part bolt {
                attribute height = 20.0 [mm];
                attribute radius = 3.0 [mm];
                attribute x = 15.0 [mm];
                attribute y = 15.0 [mm];
            }
        }

        // --- Bolt hole 2 (bottom-right) --------------------------------
        part hole2 {
            attribute operator = "difference";
            part bolt {
                attribute height = 20.0 [mm];
                attribute radius = 3.0 [mm];
                attribute x = 105.0 [mm];
                attribute y = 15.0 [mm];
            }
        }

        // --- Bolt hole 3 (top-left) ------------------------------------
        part hole3 {
            attribute operator = "difference";
            part bolt {
                attribute height = 20.0 [mm];
                attribute radius = 3.0 [mm];
                attribute x = 15.0 [mm];
                attribute y = 65.0 [mm];
            }
        }

        // --- Bolt hole 4 (top-right) -----------------------------------
        part hole4 {
            attribute operator = "difference";
            part bolt {
                attribute height = 20.0 [mm];
                attribute radius = 3.0 [mm];
                attribute x = 105.0 [mm];
                attribute y = 65.0 [mm];
            }
        }
    }

}
