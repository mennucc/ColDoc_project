Metadata
==============

Here we explain all metadata that may be associated to blobs, and their meaning.

As explained in the previous section, the metadata is associated to the UUID
(and not to the specific blob, as specified by language and file type)

Environment
-----------

Before proceeding, though, we clarify what we mean by `environment`.

`LaTeX` uses environments to delimit text elements, as in this example

.. code:: latex
  
  \begin{Theorem}
    The hypothesis implies the thesis.
  \end{Theorem}

Internally `ColDoc` identifies such environment as `E_Theorem` . The prefix `E_` helps identifying
environments, and avoiding name collisions.

By passing the option `--split-environment environment` to `blob_inator`, you may specify
which environments to split.

For example, `E_document` is the part between `\\begin{document}` and `\\end{document}`;
note that  this blob is always splitted since the option `--split-environment document` is
already present as default into `blob_inator`.


`ColDoc` uses other `environments` :

- `main_file` is the main blob, the root of the tree

- `preamble` is the preamble, that is the part between `\\documentclass` and `\\begin{document}` ;
  this blob is always splitted, unless he argument `--dont-split-preamble` is passed to `blob_inator`
  (but this may break some parts of the portal).

- `input` or `include` are used for blobs that contain text from a LaTeX file that
  was include using `\\input` or `\\include`

- `input_preamble` is used for blobs that contain code from a LaTeX file that
  was include using `\\input` while inside the preamble

- `usepackage` is used for blobs that contain packages; these are copied
  if found in the same directory of the main file

- `bibliography` is used for blobs that contain bibliography,
  as specified by the `\\bibliography` command

- `section` is used for sections

- `paragraph` is used for long paragraphs of text (as specified by the `--split-paragraph` option)

- `graphic_file` is used for blobs containing images (usually inserted using `\\includegraphics`
    or other commands specified with the option `--split-graphic` of `blob_inator`)

Metadata key list
-----------------

This is the list of all keys in the metadata storage, and the meaning of their values.
Note that a key may be repeated multiple times.

These keys are `static` : they are instantiated when
the blob is first added to the tree (e.g. by using `blob_inator`),
but are not changed when the blob content is subsequently edited.

- `coldoc` , the nickname of the ColDoc that this blob is part of

- `environ` , the value is the environ that contained this blob . See the previous section
  for details.

- `optarg` , the optional argument of the environment, as in this example.

  .. code:: tex

    \begin{Theorem}[Foobar's theorem]
      The hypothesis implies the thesis.
    \end{Theorem}

  where the `optarg` would be equal to `Foobar's theorem`.

- `lang` , the languages available for this blob; more than one language may be available.

- `extension` , the extentions available  for this blob; more than one extension may be available,
  for example a graphical file may be available a `.jpeg` and `.svg`. For blobs containined
  LaTeX, only `.tex` is allowed.

- `author` the list of people that contributed to this blob (this does not distinguish
  if somebody contributed only to a certain language version).

- `original_filename` , the filename whose content was copied in this
   blob (and children of this blob) by `blob_inator`; the extension of
   the filename (if any) is stripped; the path is not absolute, but is
   relative to the directory where the main LaTeX file was located.
   
   An exception of the above are pseudo-filenames starting starting with '/'
   (currently either '/preamble.tex' or '/document.tex' or '/main.tex')
   that indicate the original preamble and document part of the input;
   the code will also create language symlinks for them.

- `uuid` , the UUID of this blob

- `parent_uuid` , the UUID of the parent of this blob; all blob have one, but for the
  blob with `environ=main_file`

- `child_uuid` , the UUID of the children of this blob; there may be none, one, or more than one

- `access` can be `open` , `public` or `private` . See the section on permissions.

- `creation_date`

- `modification_date` ; this is updated when the blob content is edited
  (this does not distinguish which language version was edited).

- `latex_date` ; this is updated when the view (html and pdf) of this blob was last compiled
    (this does not distinguish which language version was edited - the system
    automatically recompiles the language last edited).

These keys are derived from the content of the blob.  Any direct
change to this database would be lost as soon as the blob is changed.
(In Django, they are stored in a SQL database for convenience; this
database is called `ExtraMetadata`.)

- `M_` followed by a `name` that was provided as `--metadata-command name` . E.g. if 
  `blob_inator` was invoked with the command

  .. code:: shell

    blob_inator --metadata-command label --split-environment Theorem

  to parse this input

  .. code:: latex

    \begin{Theorem}\label{tautol}
      The hypothesis implies the thesis.
    \end{Theorem}

  then the metadata for that blob would contain `environ=E_Theorem` and `M_label={tautol}`

- `S_` followed by an environment and then followed by `_M_name` ; this is used by metadata
  extracted from environments that are deeper in the tree than the current blob,
  but that are not splitted in a child blob. As in this example:

  .. code:: shell

    blob_inator --metadata-command label --split-environment Theorem

  to parse this input

  .. code:: latex

    \begin{Theorem}\label{tautol}
      The hypothesis implies the thesis.
      \begin{equation}\label{eq:forall}
        \forall x
      \end{equation}
    \end{Theorem}

  then a blob will contain this Theorem, and its metadata would contain
  `M_label={tautol}` and `S_E_equation_M_label={eq:forall}`

Metadata in source code
------------------------

Metadata is represented and operated on by a Python Class.

The class interface is described as the base class `MetadataBase` in `ColDoc.classes`

This interface is implemented in the `FMetadata` class, that stores
metadata in a file (this is independent of Django); and `DMetadata`, that
stores metadata in the Django databases.

To write code that works with both implementations, it is important to
use the `get` method, that always returns a list of values
(even for properties that are known to be single valued).

The keys `coldoc`, `uuid`, `environ` are known to be single valued,
and for convenience there is a Python `property` that returns the
single value (or `None`).


Note that in `DMetadata` some objects are not strings:

- `author` is a `models.ManyToManyField` on the internal `User` class

- `coldoc` is a `models.ForeignKey` on the `DColDoc` model.
