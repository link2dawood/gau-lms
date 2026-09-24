"""Services that belong to no single module.

Architecture rule C.1 gives every module a ``services.py`` as its public face,
and forbids one module reaching into another's models. Some work spans several
modules and so has no natural home in any of them — provisioning a launch
touches accounts, courses and lti at once, inside one transaction.

Those live here, and the agreed layout keeps them in one place rather than
scattered (DECISIONS.md D-024). The dependency runs one way, and D-048 states
it precisely: this package imports each module's ``services.py``, and a
module's **core** — its ``models.py`` and ``services.py`` — never imports this
package, because that would be circular. A module's **edges** — views, tasks,
management commands — may, and do: they are composition roots, and the work
they wire up sometimes spans modules.
"""
