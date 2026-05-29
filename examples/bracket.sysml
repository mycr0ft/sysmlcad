// Parametric bracket with centered hole — SysMLv2 → CAD bridge example
//
// Convention used by the sysmlcad bridge:
//   - attribute operator = "difference" → CSG Difference
//   - attribute operator = "union"       → CSG Union
//   - length/width/height                → Box
//   - height/radius                      → Cylinder
//   - x/y/z                              → Translate
//   - part def with export_params        → Module (future)

package Bracket {

    part bracket {
        // This part holds params AND is a CSG root
        attribute operator = "difference";
        attribute length  = 100.0;
        attribute width   = 50.0;
        attribute height  = 30.0;
        attribute holeRadius = 5.0;

        part base {
            attribute length = 100.0;
            attribute width  = 50.0;
            attribute height = 30.0;
        }

        part hole {
            attribute height = 30.0;
            attribute radius = 5.0;
            attribute x = 50.0;   // translate to center of bracket
            attribute y = 25.0;
        }
    }

}
