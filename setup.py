import setuptools

with open("README.md", "r", encoding="utf-8") as fh:
    long_description = fh.read()

setuptools.setup(
    name="piwaterflow",
    version="0.5.2",
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
        'log_mgr>=0.0.2',
        'config_yml>=0.2.3',
        'RPi.GPIO>=0.7.0',
        'fake-rpi>=0.7.1',
        'influxdb_wrapper>=0.0.3'
    ],
    python_requires='>=3.6',
)