# Rewrite a schematic library file to place the footprint specified in the
# footprint filter into the footprint field. This is interactive; it needs
# know the library in which the footprints reside.
#
# Usage: associate-fps libraryfile.lib [DEFAULTLIB]
#
# DEFAULTLIB defaults to IPC7351-Nominal

# Also appends to a REVIEWLIST file any items which could not be corrected
# or which were flagged for review.

import sys
import os

# Can specify a default footprint library other than IPC7351-Nominal
if len (sys.argv) > 2:
    DEFAULT_LIB = sys.argv[2]
else:
    DEFAULT_LIB = "IPC7351-Nominal"

# First, compile a list of the parts with their recommended footprints
parts = []
partName = None
footprints = None
reading_footprints = False
newpart = False
with open (sys.argv[1]) as in_file:
    for line in in_file:
        newpart = False
        if reading_footprints:
            if line == "$ENDFPLIST\n":
                reading_footprints = False
            else:
                footprints.append (line.strip ())
        elif line.startswith ("DEF "):
            # New part
            if partName is not None:
                parts.append ((partName, footprints))

            partName = line.split()[1]
            footprints = []
            newpart = True
        elif line == "$FPLIST\n":
            reading_footprints = True

if not newpart:
    parts.append ((partName, footprints))


# Now, ask about the parts
fpspecs = {}
to_review = set()
for partName, footprints in parts:
    if len (footprints) != 1:
        print ("Part: %-20s  WRONG FP COUNT\n" % partName)
        to_review.add (partName)
        continue

    print ("Part: %-20s  %s" % (partName, footprints[0]))
    fpspec = input ("enter for %s, - to flag for review, or library name? " % DEFAULT_LIB)
    if not fpspec.strip ():
        fpspecs[partName] = DEFAULT_LIB + ":" + footprints[0]
    elif fpspec.strip () == "-":
        fpspecs[partName] = None
        to_review.add (partName)
    else:
        fpspecs[partName] = fpspec.strip () + ":" + footprints[0]

print (fpspecs)

# Mistakes?
while True:
    partName = input ("Type part name to correct mistake, or enter: ").strip ()
    if not partName: break
    for ipartName, ifootprints in parts:
        if ipartName == partName:
            footprints = ifootprints
            break
    else:
        print ("Could not find part")
        continue

    fpspec = input ("enter for %s, - to flag for review, or library name? " % DEFAULT_LIB)
    if not fpspec.strip ():
        fpspecs[partName] = DEFAULT_LIB + ":" + footprints[0]
        to_review.discard (partName)
    elif fpspec.strip () == "-":
        fpspecs[partName] = None
        to_review.add (partName)
    else:
        to_review.discard (partName)
        fpspecs[partName] = fpspec.strip () + ":" + footprints[0]

# Write out the review list
with open ("REVIEWLIST", 'a') as reviewlist:
    for i in to_review:
        reviewlist.write ("%s\t%s\n" % (sys.argv[1], i))

# Now, rename the old library, open old and new, and write from old to new
# with modifications
os.rename (sys.argv[1], sys.argv[1] + ".fp-old")

with open (sys.argv[1] + ".fp-old") as in_file, open (sys.argv[1], 'w') as out_file:
    partName = None
    for line in in_file:
        if line.startswith ("DEF "):
            partName = line.split()[1]
            out_file.write (line)

        elif line.startswith ("F2 "):
            # This is the line that is to be rewritten
            fpspec = fpspecs.get (partName)
            if fpspec is None:
                out_file.write (line)
            else:
                out_file.write ("F2 \"%s\" 0 0 50 H I C CNN\n" % fpspec)

        else:
            out_file.write (line)

