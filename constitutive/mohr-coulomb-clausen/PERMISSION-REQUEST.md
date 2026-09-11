# Draft permission request

Edit and send. Do not commit a filled-in version with anyone's personal contact
details in it.

---

**Subject:** Permission to include your Mohr-Coulomb UMAT in an open-source teaching repository

Dear Johan,

I am putting together an open-source repository of Abaqus scripts for
large-displacement geotechnical analysis — ALE adaptive meshing, CEL, and a
worked suction caisson installation. It is teaching material in the first
instance: I have a visiting scholar arriving and I would rather hand over
something reusable than a folder of one-off scripts. It will be public on GitHub
under the MIT licence.

I would like to include your non-associated Mohr-Coulomb UMAT
(`MohrCoulombAbaqus.for`), the Tresca version, and the VUMAT port of the
Mohr-Coulomb model that I made for Abaqus/Explicit. The exact return to the
edges and the apex matters a great deal for penetration problems, where a large
share of the integration points near the tip sit on an edge or at the apex, and
the built-in Abaqus implementation rounds them.

Concretely I am asking:

1. Whether you are willing for the files to be redistributed publicly at all.
2. If so, under which licence — MIT and BSD-3-Clause are the two that fit the
   rest of the repository; GPL-3.0 would also work but would make that
   subdirectory copyleft, which I would keep separate from the rest.
3. How you would like to be credited, and which paper you would like cited.

If you would rather they were not redistributed, that is completely fine — I
will keep referring people to you instead, and the repository will fall back to
the Abaqus built-in model.

I would also be glad to send you the VUMAT port and its verification report
first, in case you want to check it before it carries your name.

Best regards,

<name>
<affiliation>

---

## Once permission is granted

Record here: the date, the form of the permission (email is fine — keep it), the
licence agreed, and the citation requested. Then update `PROVENANCE.md` and add
the `LICENSE` file.
