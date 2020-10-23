Blob and UUID
==============

Tree of UUIDs
-------------

Any content in ColDoc is identified by an UUID, an unique identifier.

Each UUID has associated to it a list of metadata
(see next section).

The ColDoc is a tree of UUIDs, connected by a parent-children
relationship.

There is a special UUID called `root_uuid` usually 001. It is the root
of the tree.  (The `root_uuid` may be changed, it is stored as field
`root_uuid` in the `DColDoc` model, but this is untested and may break the portal.)

Relationship between blobs and UUID
-----------------------------------

Any blob is identified by an UUID.

Vice versa, an UUID may refer to many blobs that have the
same semantic content but are available in

- different langages (English, Italian..) and/or

- different  content type (LaTeX, HTML, PDF, JPEG ...).

All these are blobs that are referred by the same UUID.

The list of languages is stored in the metadata `lang` , the list
of content types is stored in `extension` (as filename extensions).
(See next section).

The author can enter in the ColDoc system translations of
a LaTeX blob in different languages; and can upload
the same picture/graphic in different formats.
(But this is still mostly TODO).

Currently the code is designed in this way:

- if the blob contains LaTeX then the only extension is `.tex` and
  there may be multiple languages;

- if the blob contains a LaTeX package then the only extension is `.sty` and
  the list of languages is empty;

- if the blob contains a LaTeX bibliography then the only extension is `.bib` and
  the list of languages is empty;

- all other cases are graphical blobs: the list of
  extensions explains all available content type; the list of
  languages is empty.  (TODO it may be useful to have a graphical file
  available in different languages)

Blobs and views
---------------

The ColDoc portal also will convert the `blobs` into `views`:
for each UUID (but not the `root_uuid`) that contains LaTeX,
it will convert LaTeX to PDF and HTML; (TODO it
may also convert images to different formats).
This `view` contains only the material of that blob.

The ColDoc portal also will convert the entire document tree in
a `main` view, available in PDF and HTML.
The `main` view is internally associated to the `root_uuid`.

There are two versions of the `main` view.

- a version containing all the material, visible to `editors`;
  this `main` view is stored in the directory
  `blobs/UUID/0/0/1` of the root uuid;

- a reduced version, containing only the `public` and `open` parts;
  this is visible to anybody. (See the section on permissions).
  This reduced version view is stored in the directory
  `anon/UUID/0/0/1`.

For graphical content, there is no much difference between `blobs`
and `views`, so an user that has `view_view` access will
be able to view the blobs.
(The precise definition of `graphical content` is encoded in
`ColDoc.utils.is_image_blob`)
