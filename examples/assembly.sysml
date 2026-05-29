// Multiple components assembled into a bracket assembly
//
// Each top-level part is placed in an Assembly by the bridge.

package BracketAssembly {

    part basePlate {
        attribute length = 100.0;
        attribute width  = 80.0;
        attribute height = 10.0;
    }

    part mountingBlock {
        attribute length = 40.0;
        attribute width  = 30.0;
        attribute height = 50.0;
        attribute x = 30.0;    // position on base plate
        attribute y = 25.0;
    }

    part supportRib {
        attribute length = 10.0;
        attribute width  = 30.0;
        attribute height = 30.0;
        attribute x = 30.0;    // alongside the mounting block
        attribute y = 25.0;
        attribute z = 10.0;    // sits on top of base plate
    }

}
