Known issues
============

Backref
-------

Sometimes an incompatibility arises when using the option `backref` in
`hyperref` and using `\\url` in bibliographical entries inside the
`\\begin{thebibliography}` environment; reformatting entries, (adding
`\\newblock`, adding an extra newline before `\\end{thebibliography}`
) may solve it.
For some unfathomable reason, this `bug` is not
triggered when `\\url` is used in bibliographical entries inside a
`.bib` file, later processed with `bibtex`.


Sqlite
------

Compiling LaTeX code is slow; so compilations of multiple versions of
LaTeX are run in parallel (using `forked` processes).
These processes eventually will access the database to update
metadata, all at the same moment (more or less), alas.
The `sqlite` database does not allow concurrency;
so sometimes the database subsystem will raise
an exception `Database is locked`, that is
reported to the user.

In this case there are some mitigations that may be applied:

- grow the `timeout` parameter in `settings`

- use `WAL` mode: https://sqlite.org/wal.html .

In the long run, though, using a better database may be the only real solution. Here
are some steps to convert a portal from `sqlite` to `MySQL`.

- Install MySQl and check that the root user can access it.

- Install  `mysqlclient`, by running::

  # pip install mysqlclient

- Stop your portal (`eg` stop Apache)

- **backup all your site data** in case some catastrophic error occours.

- run::

  # ${COLDOC_SRC_ROOT}/ColDocDjango/manage.py   dumpdata --exclude contenttypes  --exclude sessions --indent 2   -o dump-site.json

- run::

  # sudo mysql < ${COLDOC_SITE_ROOT}/mysql.sql

- edit ${COLDOC_SITE_ROOT}/settings.py, uncomment the line `exec(...)` that sets up the MySQL database parameters.

- run::

  # ${COLDOC_SRC_ROOT}/ColDocDjango/manage.py  migrate

- run::

  # ${COLDOC_SRC_ROOT}/ColDocDjango/manage.py  loaddata dump-site.json

- Start your portal (and cross fingers)
