
from setuptools import setup, find_packages
from io import open
from os import path

import pathlib
# The directory containing this file
HERE = pathlib.Path(__file__).parent

# The text of the README file
README = (HERE / "README.md").read_text()

# automatically captured required modules for install_requires in requirements.txt
with open(path.join(HERE, 'requirements.txt'), encoding='utf-8') as f:
    all_reqs = f.read().split('\n')

install_requires = [x.strip() for x in all_reqs if ('git+' not in x) and (
    not x.startswith('#')) and (not x.startswith('-'))]
dependency_links = [x.strip().replace('git+', '') for x in all_reqs \
                    if 'git+' not in x]
setup (
    name = 'bespokeasm',
    description = 'A customizable byte code assembler that allows for the definition of custom instruction set architecture',
    version = '0.0.6',
    packages = find_packages(), # list of all packages
    install_requires = install_requires,
    python_requires='>=3.9',
    entry_points='''
        [console_scripts]
        bespokeasm=bespokeasm.__main__:main
    ''',
    author="Michael Kamprath",
    keyword="",
    long_description=README,
    long_description_content_type="text/markdown",
    license='GPLv3+',
    url='https://github.com/michaelkamprath/bespokeasm',
    download_url='',
    dependency_links=dependency_links,
    author_email='michael@kamprath.net',
    classifiers=[
        "Development Status :: 2 - Pre-Alpha",
        "License :: OSI Approved :: GNU General Public License v3 or later (GPLv3+)",
        "Programming Language :: Python :: 3.9",
    ]
)
