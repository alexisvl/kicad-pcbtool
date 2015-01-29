"""KiCad schematic symbol library

This can load a KiCad schematic library so that it can be manipulated as a
set of objects and re-exported.
"""

import re
import shlex

FILL_FG = 1
FILL_BG = -1
FILL_NONE = 0

KICAD_TO_FILL = {"F": FILL_FG, "f": FILL_BG, "N": FILL_NONE}
FILL_TO_KICAD = {FILL_FG: "F", FILL_BG: "f", FILL_NONE: "N"}

# Pin electrical types
PIN_INPUT = "I"
PIN_OUTPUT = "O"
PIN_BIDI = "B"
PIN_TRISTATE = "T"
PIN_PASSIVE = "P"
PIN_UNSPECIFIED = "U"
PIN_POWER_IN = "W"
PIN_POWER_OUT = "w"
PIN_OPEN_COLL = "C"
PIN_OPEN_EMIT = "E"
PIN_NC = "N"

# Pin orientations
PIN_RIGHT = "R"
PIN_LEFT = "L"
PIN_UP = "U"
PIN_DOWN = "D"

# Pin styles
PIN_HIDDEN = "N"
PIN_ACTIVELOW = "I"
PIN_CLOCK = "C"
PIN_LOWCLOCK = "IC"
PIN_LOWIN =  "L"
PIN_CLOCKLOW = "CL"
PIN_LOWOUT = "V"
PIN_FALLING = "F"
PIN_NONLOGIC = "NX"

def readfile (f):
    """Read in a file, returning a list of symbol objects."""
    objects = []
    while True:
        obj = KicadSchSymbol.createFromLibFile (f)
        if obj is None:
            break
        objects.append (obj)
    return objects

def writefile (f, objects):
    """Write a list of objects out to a file."""
    f.write ("EESchema-LIBRARY Version 2.3\n")
    f.write ("#encoding utf-8\n")
    for i in objects:
        i.writeOut (f)
    f.write ("#\n")
    f.write ("#End Library\n")


class KicadSchSymbol (object):
    """This represents a full schematic symbol. It contains a set of elements
    which can be manipulated.

    There is nothing else in a library file, so a file is just a list of these.
    """

    def __init__ (self):
        self.definition = None
        self.referenceField = None
        self.valueField = None
        self.footprintField = None
        self.otherFields = []

        self.footprintFilters = []
        self.aliases = []
        self.graphics = []
        self.pins = []

    def writeOut (self, f):
        """Write the symbol into a file"""
        f.write ("#\n")
        f.write ("# %s\n" % self.definition.name)
        f.write ("#\n")
        self.definition.writeOut (f)
        self.referenceField.writeOut (f)
        self.valueField.writeOut (f)
        self.footprintField.writeOut (f)
        for i in self.otherFields:
            i.writeOut (f)
        if self.aliases:
            f.write ("ALIAS ")
            f.write (" ".join (self.aliases))
            f.write ("\n")
        if self.footprintFilters:
            f.write ("$FPLIST\n ")
            f.write (" ".join (self.footprintFilters))
            f.write ("\n$ENDFPLIST\n")
        f.write ("DRAW\n")
        for i in self.graphics:
            i.writeOut (f)
        for i in self.pins:
            i.writeOut (f)
        f.write ("ENDDRAW\n")
        f.write ("ENDDEF\n")

    @classmethod
    def createFromLibFile (cls, f):
        """Create a KicadSchSymbol from a library file. Creates just one;
        returns None at EOF.
        """
        newobj = cls ()

        state = "root"

        for line in f:
            line = line.partition ("#")[0].strip ()
            if not line:
                continue
            if state == "root":
                if line.startswith ("DEF "):
                    newobj.definition = Definition (line)
                elif line.startswith ("F0 "):
                    newobj.referenceField = Field (line)
                elif line.startswith ("F1 "):
                    newobj.valueField = Field (line)
                elif line.startswith ("F2 "):
                    newobj.footprintField = Field (line)
                elif re.match (r"F\d+ ", line):
                    newobj.otherFields.append (Field (line))
                elif line.startswith ("ALIAS "):
                    newobj.aliases.extend (line.split ()[1:])
                elif line == "$FPLIST":
                    state = "fplist"
                elif line == "DRAW":
                    state = "draw"
                elif line == "ENDDEF":
                    return newobj
                elif line.startswith ("EESchema-LIBRARY"):
                    continue
                else:
                    raise ValueError ("cannot interpret line: " + line)

            elif state == "fplist":
                if line == "$ENDFPLIST":
                    state = "root"
                else:
                    newobj.footprintFilters.extend (i.strip () for i in line.split ())

            elif state == "draw":
                if line.startswith ("A "):
                    newobj.graphics.append (Arc (line))
                elif line.startswith ("C "):
                    newobj.graphics.append (Circle (line))
                elif line.startswith ("P "):
                    newobj.graphics.append (Polyline (line))
                elif line.startswith ("S "):
                    newobj.graphics.append (Rectangle (line))
                elif line.startswith ("T "):
                    newobj.graphics.append (Text (line))
                elif line.startswith ("X "):
                    newobj.pins.append (Pin (line))
                elif line == "ENDDRAW":
                    state = "root"
                else:
                    raise ValueError ("cannot interpret line: " + line)

    # KiCad has some horrid data duplication that means a few things must be
    # edited in multiple places. Use these properties whenever you can to fix
    # that.
    @property
    def name (self):
        return self.definition.name
    @name.setter
    def name (self, v):
        self.definition.name = v
        self.valueField.text = v

    @property
    def reference (self):
        return self.definition.reference
    @reference.setter
    def reference (self, v):
        self.definition.reference = v
        self.referenceField.text = v


class Definition (object):
    def __init__ (self, line):
        line = line.split ()
        self.name = line[1]
        self.reference = line[2]
        self.text_offset = int (line[4])
        self.draw_numbers = bool (line[5] == "Y")
        self.draw_names = bool (line[6] == "Y")
        self.unit_count = int (line[7])
        self.units_locked = bool (line[8] == "L")
        self.is_power = bool (line[9] == "P")

    def writeOut (self, f):
        line = "DEF {name} {ref} 0 {toff} {dnums} {dnames} {units} {locked} {power}\n"
        f.write (line.format (
            name = self.name,
            ref = self.reference,
            toff = self.text_offset,
            dnums = ("Y" if self.draw_numbers else "N"),
            dnames = ("Y" if self.draw_names else "N"),
            units = self.unit_count,
            locked = ("L" if self.units_locked else "F"),
            power = ("P" if self.is_power else "N")))

class Field (object):
    def __init__ (self, line):
        line = shlex.split (line)
        self.num = int (line[0][1:])
        self.text = line[1]
        self.posx = int (line[2])
        self.posy = int (line[3])
        self.size = int (line[4])
        self.vertical = bool (line[5] == "V")
        self.visible = bool (line[6] == "V")
        self.horiz_just = line[7] # L R or C
        self.vert_just = line[8] # L R or C

    def writeOut (self, f):
        line = "F{num} \"{text}\" {posx} {posy} {size} {orient} {visible} {hjust} {vjust}\n"
        f.write (line.format (
            num = self.num,
            text = self.text,
            posx = self.posx,
            posy = self.posy,
            size = self.size,
            orient = ("V" if self.vertical else "H"),
            visible = ("V" if self.visible else "I"),
            hjust = self.horiz_just,
            vjust = self.vert_just))

class Arc (object):
    def __init__ (self, line):
        line = line.split ()
        self.posx = int(line[1])
        self.posy = int(line[2])
        self.radius = int(line[3])
        self.start_angle = int(line[4])
        self.end_angle = int(line[5])
        self.unit = int(line[6])
        self.convert = int(line[7])
        self.thickness = int(line[8])
        self.fill = KICAD_TO_FILL[line[9]]
        self.startx = int(line[10])
        self.starty = int(line[11])
        self.endx = int(line[12])
        self.endy = int(line[13])

    def writeOut (self, f):
        line = "A {posx} {posy} {radius} {sangle} {eangle} {unit} {conv} {thick} {fill} {sx} {sy} {ex} {ey}\n"
        f.write (line.format (
            posx = self.posx,
            posy = self.posy,
            radius = self.radius,
            sangle = self.start_angle,
            eangle = self.end_angle,
            unit = self.unit,
            conv = self.convert,
            thick = self.thickness,
            fill = FILL_TO_KICAD[self.fill],
            sx = self.startx,
            sy = self.starty,
            ex = self.endx,
            ey = self.endy))

class Circle (object):
    def __init__ (self, line):
        line = line.split ()
        self.posx = int (line[1])
        self.posy = int (line[2])
        self.radius = int (line[3])
        self.unit = int (line[4])
        self.convert = int (line[5])
        self.thickness = int (line[6])
        self.fill = KICAD_TO_FILL[line[7]]

    def writeOut (self, f):
        line = "C {posx} {posy} {radius} {unit} {convert} {thickness} {fill}\n"
        f.write (line.format (
            posx = self.posx,
            posy = self.posy,
            radius = self.radius,
            unit = self.unit,
            convert = self.convert,
            thickness = self.thickness,
            fill = FILL_TO_KICAD[self.fill]))

class Polyline (object):
    def __init__ (self, line):
        line = line.split ()
        self.unit = int (line[2])
        self.convert = int (line[3])
        self.thickness = int(line[4])
        self.fill = KICAD_TO_FILL[line[-1]]
        
        points = [int(i) for i in line[5:-1]]
        # Pairwise (x y) (x y)
        self.points = list (zip (points[::2], points[1::2]))

    def writeOut (self, f):
        line = "P {npoints} {unit} {convert} {thickness} {points} {fill}\n"
        f.write (line.format (
            npoints = len (self.points),
            unit = self.unit,
            convert = self.convert,
            thickness = self.thickness,
            fill = FILL_TO_KICAD[self.fill],
            points = " ".join(" %d %d" % i for i in self.points)))

class Rectangle (object):
    def __init__ (self, line):
        line = line.split ()
        self.startx = int (line[1])
        self.starty = int (line[2])
        self.endx = int (line[3])
        self.endy = int (line[4])
        self.unit = int (line[5])
        self.convert = int (line[6])
        self.thickness = int (line[7])
        self.fill = KICAD_TO_FILL[line[8]]

    def writeOut (self, f):
        line = "S {startx} {starty} {endx} {endy} {unit} {convert} {thickness} {fill}\n"

        f.write (line.format (
            startx = self.startx,
            starty = self.starty,
            endx = self.endx,
            endy = self.endy,
            unit = self.unit,
            convert = self.convert,
            thickness = self.thickness,
            fill = self.fill))

class Text (object):
    def __init__ (self, line):
        line = line.split ()
        self.vertical = bool (int (line[1]) != 0)
        self.posx = int (line[2])
        self.posy = int (line[3])
        self.size = int (line[4])
        # line[5] is text_type. fuckin documentation doesn't even explain this
        self.unit = int (line[6])
        self.convert = int (line[7])
        self.text = line[8].replace ("~", " ")
        self.italic = bool (line[9] == "Italic")
        self.bold = bool (int (line[10]))
        self.horiz_just = line[11]
        self.vert_just = line[12]

    def writeOut (self, f):
        line = "T {vert} {posx} {posy} {size} 0 {unit} {conv} {text}  {italic} {bold} {hjust} {vjust}\n"

        f.write (line.format (
            vert = (900 if self.vertical else 0),
            posx = self.posx,
            posy = self.posy,
            size = self.size,
            unit = self.unit,
            conv = self.convert,
            text = self.text.replace (" ", "~"),
            italic = ("Italic" if self.italic else "Normal"),
            bold = (1 if self.bold else 0),
            hjust = self.horiz_just,
            vjust = self.vert_just))


class Pin (object):
    def __init__ (self, line):
        line = line.split ()
        self.name = line[1]
        self.num = line[2]
        self.posx = int (line[3])
        self.posy = int (line[4])
        self.length = int (line[5])
        self.direction = line[6]
        self.name_size = int (line[7])
        self.num_size = int (line[8])
        self.unit = int (line[9])
        self.convert = int (line[10])
        self.elec_type = line[11]
        if len (line) > 12:
            self.style = line[12]
        else:
            self.style = None

    def writeOut (self, f):
        line = "X {name} {num} {posx} {posy} {length} {direction} {name_size} {num_size} {unit} {convert} {elec_type}{style}\n"

        f.write (line.format (
            name = self.name,
            num = self.num,
            posx = self.posx,
            posy = self.posy,
            length = self.length,
            direction = self.direction,
            name_size = self.name_size,
            num_size = self.num_size,
            unit = self.unit,
            convert = self.convert,
            elec_type = self.elec_type,
            style = ("" if self.style is None else (" " + self.style))))


def script1():
    # open conn-100mil.lib.old and split the CONN-100MIL-M-* into shrouded and
    # unshrouded versions
    import copy
    with open ("conn-100mil.lib.old") as f:
        symbs = readfile (f)

    newsymbs = []
    for i in symbs:
        if i.definition.name.startswith ("CONN-100MIL-M"):
            i.footprintFilters.remove (i.definition.name + "-SHROUD")
            i.footprintField.text = "conn-100mil:" + i.footprintFilters[0]
            i.footprintField.visible = False

            shrouded = copy.deepcopy (i)
            shrouded.name = shrouded.name + "-SHROUD"
            shrouded.footprintFilters[0] += "-SHROUD"
            shrouded.footprintField.text = "conn-100mil:" + shrouded.footprintFilters[0]
            newsymbs.append (shrouded)
        else:
            i.footprintField.text = "conn-100mil:" + i.footprintFilters[0]
            i.footprintField.visible = False
    symbs.extend (newsymbs)

    with open ("conn-100mil.lib", "w") as f:
        writefile (f, symbs)

if __name__ == '__main__':
    script1 ()

