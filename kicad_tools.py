import sexpdata

S = sexpdata.Symbol

# Why the hell does B.Adhes get coded as B\.Adhes? What sexp format escapes
# that?
sexpdata.Symbol._lisp_quoted_specials.remove (('.', r'\.'))

def symbtostr (s):
    if isinstance (s, S):
        return s.value ()
    else:
        return str (s)

# Sexp manipulators
def get_from (sexp, kind):
    """From (blah (blah blah) (blah blah) (kind thingiwant)), return cdr
    Returns None otherwise"""
    for i in sexp[1:]:
        if symbtostr (i[0]) == kind:
            return i[1:]
    return None

def sub_in (sexp, kind, cdr):
    """Replace (kind . cdr) in (blah (blah blah) (kind . othercdr)), or add it
    if it's not there to begin with."""
    for i in range (1, len (sexp)):
        if symbtostr (sexp[i][0]) == kind:
            sexp[i] = [S(kind)] + cdr
            break
    else:
        sexp.append ([S(kind)] + cdr)

class KicadPCB (object):

    def __init__ (self, filename):
        with open (filename) as f:
            sexptree = sexpdata.load (f)

        self.nets = {}

        # Decode all the objects into classes
        self.children = []
        for i in sexptree[1:]:
            item_id = i[0]

            if item_id == S("net"):
                child = NetSexp(self, i)
                self.children.append (child)
                self.nets[child.net_id] = child.net_name

            elif item_id == S("gr_text"):
                child = TextSexp (self, i)
                self.children.append (child)

            elif item_id == S("via"):
                child = ViaSexp (self, i)
                self.children.append (child)

            elif item_id == S("segment"):
                child = SegmentSexp (self, i)
                self.children.append (child)

            else:
                child = GenericSexp(self, i)
                self.children.append (child)

    def out (self):
        return [S("kicad_pcb")] + [i.out() for i in self.children]
    
    def write (self, filename):
        # "Maximum line length exceeded", fuck you!!
        # What bleeding moron thought sexps should be read line-by-line?!
        with open (filename, 'w') as f:
            f.write ("(kicad_pcb\n")
            for i in self.children:
                sexpdata.dump (i.out (), f)
                f.write ("\n")
            f.write (")\n")


    def find_types (self, kind):
        """Return all children of the given type"""
        return [i for i in self.children if isinstance (i, kind)]

    def delete (self, item):
        """Delete the item from children"""
        indices = []
        for i, elem in enumerate (self.children):
            if elem is item:
                indices.append (i)
        for i in indices[::-1]:
            del self.children[i]


class GenericSexp (object):
    def __init__ (self, pcb, sexp):
        self.sexp = sexp
        self.name = sexp[0].value ()

    def out (self):
        return self.sexp

class NetSexp (object):
    # Immutable!
    def __init__ (self, pcb, sexp):
        self.sexp = sexp
        self.net_id = sexp[1]
        self.net_name = symbtostr (sexp[2])

    def out (self):
        return self.sexp

class TextSexp (object):
    def __init__ (self, pcb, sexp):
        self.sexp = sexp

    @property
    def text (self):
        return self.sexp[1]
    @text.setter
    def text (self, v):
        self.sexp[1] = v

    def out (self):
        return self.sexp

class ViaSexp (object):
    def __init__ (self, pcb, sexp):
        self.sexp = sexp
        self.pcb = pcb

    def out (self):
        return self.sexp

    @property
    def pos (self):
        return get_from (self.sexp, "at")
    @pos.setter
    def pos (self, v):
        sub_in (self.sexp, "at", v)

    @property
    def size (self):
        return get_from (self.sexp, "size")[0]
    @size.setter
    def size (self, v):
        sub_in (self.sexp, "size", [v])

    @property
    def drill (self):
        return get_from (self.sexp, "drill")[0]
    @drill.setter
    def drill (self, v):
        sub_in (self.sexp, "drill", [v])

    @property
    def annulus (self):
        return (self.size - self.drill) / 2
    @annulus.setter
    def annulus (self, v):
        self.size = 2. * v + self.size

    @property
    def net (self):
        return self.pcb.nets[get_from (self.sexp, "net")[0]]
    @net.setter
    def net (self, v):
        for net_id in self.pcb.nets:
            net_value = self.pcb.nets[net_id]
            if net_value == v:
                sub_in (self.sexp, "net", [net_id])
                break
        else:
            raise ValueError ("Tried to set nonexisting net")

class SegmentSexp (object):
    def __init__ (self, pcb, sexp):
        self.sexp = sexp
        self.pcb = pcb

    def out (self):
        return self.sexp

    @property
    def start (self):
        return get_from (self.sexp, "start")
    @start.setter
    def start (self, v):
        sub_in (self.sexp, "start", v)

    @property
    def end (self):
        return get_from (self.sexp, "end")
    @end.setter
    def end (self, v):
        sub_in (self.sexp, "end", v)

    @property
    def width (self):
        return get_from (self.sexp, "width")[0]
    @width.setter
    def width (self, v):
        sub_in (self.sexp, "width", [v])

    @property
    def layer (self):
        return get_from (self.sexp, "layer")[0]
    @layer.setter
    def layer (self, v):
        sub_in (self.sexp, "layer", [v])

    @property
    def net (self):
        return self.pcb.nets[get_from (self.sexp, "net")[0]]
    @net.setter
    def net (self, v):
        for net_id in self.pcb.nets:
            net_value = self.pcb.nets[net_id]
            if net_value == v:
                sub_in (self.sexp, "net", [net_id])
                break
        else:
            raise ValueError ("Tried to set nonexisting net")

###############################################################################

def remove_stacked_vias (pcb):
    """KiCad's new renderer has a thing for making stacks of vias at the
    exact same position. This will remove all but one of them.

    Returns (number of stacks cleaned up, number of vias cleaned up)
    """

    vias = pcb.find_types (ViaSexp)
    vias_by_pos = {}
    
    vias_to_delete = []
    n_stacks = 0

    for via in vias:
        pos = tuple (via.pos)
        if pos in vias_by_pos:
            vias_by_pos[pos].append (via)
        else:
            vias_by_pos[pos] = [via]

    for pos in vias_by_pos:
        stack = vias_by_pos[pos]
        if len (stack) > 1:
            vias_to_delete.extend (stack[1:])
            n_stacks += 1

    for via in vias_to_delete:
        pcb.delete (via)

    return n_stacks, len (vias_to_delete)
