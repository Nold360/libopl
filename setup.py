import setuptools

with open("README.md", "r") as fh:
    long_description = fh.read()

setuptools.setup(
    name="libopl",
    version="0.1.1",
    author="Nold",
    author_email="nold@gnu.one",
    description="Library And Tool To Manage Open-PS2-Loader USB-Drives & Games",
    long_description=long_description,
    long_description_content_type="text/markdown",
    url="https://github.com/nold360/libopl",
    packages=setuptools.find_packages(),
    entry_points={
        'console_scripts': [
            'opl= libopl.opl:main',
        ]
    },
    classifiers=[
        "Programming Language :: Python :: 3",
        "License :: OSI Approved :: GNU General Public License v3 or later (GPLv3+)",
        "Operating System :: POSIX :: Linux",
	"Environment :: Console"
    ],
)
