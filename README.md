# sysmlcad

Parametric CAD shape modeling with pluggable backends.

```python
from sysmlcad import Box, Cylinder, Sphere, Difference, Parameter, export

length = Parameter("L", 100)
box = Box(length, 50, 30)
hole = Cylinder(30, 5)
part = box - hole

print(export(part, backend="openscad"))
```
