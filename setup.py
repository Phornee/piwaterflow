import setuptools

with open("README.md", "r", encoding="utf-8") as fh:
    long_description = fh.read()

setuptools.setup(
    name="piwaterflow",
    version="0.4.0",
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
        'baseutils_phornee>=0.1.0',
        'RPi.GPIO>=0.7.0',
        'Flask>=1.1.2',
        'flask-compress>=1.9.0',
        'importlib-metadata>=4.5.0',
        'tzlocal>=4.1',
        'influxdb_wrapper>=0.0.3',
        'python-socketio>=5.8.0',
        'eventlet>=0.33.3'
    ],
    python_requires='>=3.6',
)