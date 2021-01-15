import setuptools

with open("README.md", "r", encoding="utf-8") as fh:
    long_description = fh.read()

setuptools.setup(
    name="PiWaterflow",
    version="0.0.2",
    author="Ismael Raya",
    author_email="phornee@gmail.com",
    description="Waterflow resilient system",
    long_description=long_description,
    long_description_content_type="text/markdown",
    url="https://github.com/Phornee/PiWaterflow",
    packages=setuptools.find_packages(),
    classifiers=[
        "Programming Language :: Python :: 3",
        "License :: OSI Approved :: MIT License",
        "Operating System :: OS Independent",
    ],
    install_requires=[
        'phorneebaseutils>=0.0.2',
        'RPi.GPIO>=0.7.0',
        'PyYAML>=5.3.1'
    ],
    python_requires='>=3.6',
)