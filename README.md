# MSFS-tools

Various tools that are useful to Microsoft Flight Simulator add-on developers. Or at least to myself when I develop such add-ons.

## template-expand.py

This Python script reads an aircraft model XML file and expands the template calls in it. It is a work in progress. I don't know whether it
will ever be "finished" and complete.

Use: `python3 template-expand.py --verbose --include ~/Downloads/ModelBehaviorDefs a.xml`

Where the `~/Downloads/ModelBehaviorDefs` is where I have copied the OneStore/fs-base-aircraft-common/ModelBehaviorDefs from MSFS and
fixed the XML syntax errors in it. (The fixes I did are in `ModelBehaviorDefs-fixes.diff`.)

There are lots of things in ModelBehaviorDefs code that aren't yet handled. 
