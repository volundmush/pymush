import os
import sys
from setuptools import setup, find_packages

os.chdir(os.path.dirname(os.path.realpath(__file__)))

OS_WINDOWS = os.name == "nt"


def get_requirements():
    """
    To update the requirements for PyMUSH, edit the requirements.txt file.
    """
    with open("requirements.txt", "r") as f:
        req_lines = f.readlines()
    reqs = []
    for line in req_lines:
        # Avoid adding comments.
        line = line.split("#")[0].strip()
        if line:
            reqs.append(line)
    return reqs

def get_scripts():
    """
    Determine which executable scripts should be added. For Windows,
    this means creating a .bat file.
    """
    if OS_WINDOWS:
        batpath = os.path.join("bin", "windows", "pymush.bat")
        scriptpath = os.path.join(sys.prefix, "Scripts", "pymush_launcher.py")
        with open(batpath, "w") as batfile:
            batfile.write('@"%s" "%s" %%*' % (sys.executable, scriptpath))
        return [batpath, os.path.join("bin", "windows", "pymush_launcher.py")]
    else:
        return [os.path.join("bin", "unix", "pymush")]


from os import path
this_directory = path.abspath(path.dirname(__file__))
with open(path.join(this_directory, 'README.md'), encoding='utf-8') as f:
    long_description = f.read()

# setup the package
setup(
    name="pymush",
    version="0.0.1",
    author="Volund",
    maintainer="Volund",
    url="https://github.com/volundmush/pymush",
    description="",
    license="???",
    long_description=long_description,
    long_description_content_type='text/markdown',
    install_requires=get_requirements(),
    packages=["pymush"],
    zip_safe=False,
    scripts=get_scripts(),
    classifiers=[
        "Programming Language :: Python :: 3 :: Only",
        "Programming Language :: Python :: 3.8",
        "Intended Audience :: Developers",
        "Topic :: Games/Entertainment :: Multi-User Dungeons (MUD)",
        "Topic :: Games/Entertainment :: Puzzle Games",
        "Topic :: Games/Entertainment :: Role-Playing",
        "Topic :: Games/Entertainment :: Simulation",
        "Topic :: Software Development :: Libraries :: Application Frameworks",
    ],
    python_requires=">=3.8",
    project_urls={
        "Source": "https://github.com/volundmush/pymush",
        "Issue tracker": "https://github.com/volundmush/pymush/issues",
        "Patreon": "https://www.patreon.com/volund",
    },
)
