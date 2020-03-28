import setuptools

with open("README.md", "r") as fh:
    long_description = fh.read()

setuptools.setup(
  name='python-plugwise',
  version="0.3",
  author='Frank van Breugel',
  author_email='f.v.breugel@gmail.com',
  description='Async library for Plugwise stick',
  long_description=long_description,
  long_description_content_type="text/markdown",
  url="https://github.com/brefra/python-plugwise",
  packages=setuptools.find_packages(),
  classifiers=[
    "Programming Language :: Python :: 3",
    "License :: OSI Approved :: MIT License",
    "Intended Audience :: Developers",
    "Natural Language :: English",
    "Operating System :: OS Independent",
    "Topic :: Home Automation",
  ],
  python_requires='>=3.6',
  install_requires=[
        'crcmod',
        'pyserial',
  ],
)

