Metadata
==============

Here we explain all metadata that may be associated to blobs, and their meaning.

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

`ColDoc` uses other `environments` :

- `main_file` is the main blob, the root of the tree

- `preamble` is the preamble, that is the part between `\\documentclass` and `\\begin{document}` ;
  this blob is splitted if the argument `--split-preamble` is passed to `blob_inator`

- `document` is the part between `\\begin{document}` and `\\end{document}`;
  this blob is splitted if the argument `--split-environment document` is passed to `blob_inator`

- `input` or `include` are used for blobs that contain text from a LaTeX file that
  was include using `\\input` or `\\include`

- `input_preamble` is used for blobs that contain code from a LaTeX file that
  was include using `\\input` while inside the preamble

- `usepackage` is used for blobs that contain packages

- `paragraph` is used for long paragraphs of text (as specified by the `--split-paragraph` option)

Metadata key list
-----------------

This is the list of all keys in the metadata storage, and the meaning of their values.
Note that a key may be repeated multiple times.

- `coldoc` , the nickname of the ColDoc that this blob is part of

- `environ` , the value is the environ that contained this blob . See the previous section
  for details.

- `lang` , the language of this blob; more than one language may be available

- `extension` , the extentions  of this blob; more than one extension may be available

- `optarg` , the optional argument of the environment, as in this example.
  
  .. code:: tex
  
    \begin{Theorem}[Foobar's theorem]
      The hypothesis implies the thesis.
    \end{Theorem}
  
  where the `optarg` would be equal to `Foobar's theorem`.

- `authors` the list of people that contributed to this blob

- `original_filename` , the filename whose content was copied in this blob (and children of this blob)

- `uuid` , the UUID of this blob

- `parent_uuid` , the UUID of the parent of this blob; all blob have one, but for the
  blob with `environ=main_file`

- `child_uuid` , the UUID of the children of this blob; there may be none, one, or more than one

- `M_` followed by a `name` that was provided as `--metadata-command name` . E.g. if 
  `blob_inator` was invoked with the command
  
  .. code:: shell
    
    blob_inator --metadata-command label --split-environment Theorem
  
  to parse this input
  
  .. code:: latex
    
    \begin{Theorem}\label{tautol}
      The hypothesis implies the thesis.
    \end{Theorem}
  
  then the metadata for that blob would contain `environ=E_Theorem` and `M_label=tautol`

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
  `M_label=tautol` and `S_E_equation_M_label=eq:forall`

Metadata in source code
------------------------

Metadata is represented and operated on by a Python Class.

The class interface is described as the base class `MetadataBase` in `ColDoc.classes`

The interface has a list of `properties` that can be used to retrieve and (in Django implementation) set
the value.

Some keys though are known to be single valued, and are returned as single values
by the associated property: `coldoc`, `uuid`, `environ`.

Instead `extension`, `lang` , `lang_ext`, `authors`, `child_uuid`,  `parent_uuid`, are multi-valued,
and are returned as lists of strings.

There is also a `get` function, that always returns a list of values
(even for properties that are known to be single valued)

This interface is implemented in the `FMetadata` class, that stores
metadata in a file (this is independent of Django); and `DMetadata`, that
stores metadata in the Django databases
