# MSFS-tools

Various tools that are useful to Microsoft Flight Simulator add-on developers. Or at least to myself when I develop such add-ons.

## template-expand.py

This Python script reads an aircraft model XML file and expands the template calls in it. It is a work in progress. I don't know whether it
will ever be "finished" and complete. But now it is able to expand the whole DA62_interior.xml from the SDK samples. Whether the expansion is
correct I don't know yet. But at least it will help in understanding what the real low-level API of this stuff is, that is hidden
under layer upon layer of templates.

Use: `python3 template-expand.py --verbose --include ~/Downloads/ModelBehaviorDefs a.xml`

(That is on macOS or Linux. The Unix command line is my preferred environment. But something similar will work on Windows, too.)

Where the `~/Downloads/ModelBehaviorDefs` is where I have copied the OneStore/fs-base-aircraft-common/ModelBehaviorDefs from MSFS and
fixed the XML syntax errors in it. (The fixes I did are in `ModelBehaviorDefs-fixes.diff`.)
