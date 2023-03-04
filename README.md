Clavier
==============================================================================

A CLI framework for Python. Use case focus is development tools. Write fast, run
fast.

> 🙅‍♀️ No Windows 🙅‍♂️
> 
> Unix-like only. Developed on macOS and Linux (Debian-based).

Why?
------------------------------------------------------------------------------

1.  Build on top of the standard library's `argparse` so — like it or not —
    you're likely already familiar with much of it.
    
2.  Integrates [argcomplete][] for tab-completion (Bash-only, it seems) and
    [rich][] for pretty pretty printing.
    
    [argcomplete]: https://pypi.org/project/argcomplete/
    [rich]: https://pypi.org/project/rich/
    
3.  Capable of running a persistent server daemon and generating fast entrypoint
    binaries to _tremendously_ speed-up commands and completions. Like
    under-`100 ms` fast, compared to around `1 s` when invoked the "normal" way
    (`10x` speed-up).
    
    > This improvement is possible because — in the "one-and-done" execution
    > pattern typical of a CLI app — Python often spends the _vast_ majority of
    > time loading itself up and importing modules. This gets really bad if
    > you're depending on large and complicated packages like Numpy or OpenCV.
    > 
    > Yes, this functionality adds all sorts of complexity and introduces many
    > new failure modes. Yes, it kinda unnerves me to have my terminal commands
    > answered by some unseen server-of-sorts floating somewhere out in the
    > ether of my machine. Yes, it reminds me of frustrated and furious episodes
    > with `nodemon` and whatever-that-one-for-Rails-was-called from back in the
    > day.
    > 
    > But, it makes Python CLI apps fast enough to be frequently-used part of my
    > development flow, and that's a massive benefit. Especially when
    > tab-completion is fast enough to use for exploring available commands and
    > options.

Status
------------------------------------------------------------------------------

Not really there yet.

How To...
------------------------------------------------------------------------------

### Develop ###

Should pretty much be `poetry install`.


### Run Tests ###

All of them (that have tests):

    poetry run dr.t --all --hide-empty

Single file, fail-fast, printing header panel (so you can find where they
start and end easily during repeated runs):

    poetry run dr.t -fp <filename>

### Build Docs ###

    poetry run novella -d ./docs
    
Serving them:

    poetry run novella -d ./docs --serve
    

### Publish ###

1.  Update the version in `pyproject.toml`.
    
2.  Commit, tag `vX.Y.Z`, push.
    
3.  Log in to [PyPI](https://pypi.org) and go to
    
    https://pypi.org/manage/account/
    
    to generate an API token.
    
4.  Throw `poetry` at it:
    
        poetry publish --build --username __token__ --password <token>
    
5.  Bump patch by 1 and append `-dev`, commit and push (now we're on the "dev"
    version of the next patch version).
