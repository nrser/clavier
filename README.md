clavier
==============================================================================

A light and not-so-bright CLI framework for Python.

Release
------------------------------------------------------------------------------

To release to PyPi, 'cause I always forget...

```shell
rm -rf ./dist/*
python setup.py sdist bdist_wheel
python -m twine upload ./dist/*
```
