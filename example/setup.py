import setuptools
from pathlib import Path

setuptools.setup(
    name="clavier-example",
    author="Neil Souza, Expanded Performance Inc",
    author_email="neil@neilsouza.com",
    description="Clavier CLI example",
    url="https://github.com/nrser/clavier",
    packages=setuptools.find_packages(),
    classifiers=[
        "Programming Language :: Python :: 3",
        "Operating System :: POSIX",
    ],
    install_requires=[
        "clavier>=0.1.1",
    ],
    scripts=[
        "bin/clavier-example",
    ],
)
