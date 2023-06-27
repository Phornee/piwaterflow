""" Setup.py """
import os
import re
import setuptools

with open("README.md", "r", encoding="utf-8") as fh:
    long_description = fh.read()

def get_version():
    """ Gets version string from the init file
    Returns:
        str: Version string
    """
    version_file = os.path.join('piwaterflow', '__init__.py')
    with open(version_file, 'r',  encoding="utf-8").readlines() as initfile_lines:
        return re.search(r"^__version__ = ['\"]([^'\"]*)['\"]", initfile_lines.read()).group(1)
    raise RuntimeError(f'Unable to find version string in {version_file}.')

setuptools.setup(
    name="piwaterflow",
    version=get_version(),
    author="Ismael Raya",
    author_email="phornee@gmail.com",
    description="Raspberry Pi Waterflow resilient system",
    long_description=long_description,
    long_description_content_type="text/markdown",
    url="https://github.com/Phornee/piwaterflow",
    packages=setuptools.find_packages(),
    package_data={
        '': ['*.yml'],
    },
    classifiers=[
        "Programming Language :: Python :: 3",
        "License :: OSI Approved :: MIT License",
        "Operating System :: OS Independent",
        "Topic :: Home Automation",
    ],
    install_requires=[
        'log_mgr>=0.1.1',
        'config_yml>=0.3.1',
        'RPi.GPIO>=0.7.0',
        'fake-rpigpio>=0.1.1',
        'influxdb_wrapper>=0.0.5'
    ],
    python_requires='>=3.6',
)