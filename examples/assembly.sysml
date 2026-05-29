// Multiple components assembled into a bracket assembly.
// Each top-level part is placed in an Assembly by the bridge.

package BracketAssembly {

    part basePlate {
        attribute length = 100.0 [mm];
        attribute width  = 80.0 [mm];
        attribute height = 10.0 [mm];
    }

    part mountingBlock {
        attribute length = 40.0 [mm];
        attribute width  = 30.0 [mm];
        attribute height = 50.0 [mm];
        attribute x = 30.0 [mm];    // position on base plate
        attribute y = 25.0 [mm];
    }

    part supportRib {
        attribute length = 10.0 [mm];
        attribute width  = 30.0 [mm];
        attribute height = 30.0 [mm];
        attribute x = 30.0 [mm];    // alongside the mounting block
        attribute y = 25.0 [mm];
        attribute z = 10.0 [mm];    // sits on top of base plate
    }

}
