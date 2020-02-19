from setuptools import setup
setup(
  name='plugwise-plugwise',
  packages=["plugwise", "plugwise.connections", "plugwise.messages", "plugwise.nodes"],
  version='0.1',
  license='MIT',
  description='Async library for communicating with Plugwise devices by using a Plugwise stick',
  author='Frank van Breugel',
  author_email='frank_van_breugel@hotmail.com',
  url='https://github.com/brefra/python-plugwise',
  download_url='https://github.com/brefra/python-plugwise/archive/0.1.tar.gz',
  install_requires=[
        'crcmod',
        'pyserial',
  ],
  classifiers=[
    'Development Status :: 3 - Alpha',
    'Intended Audience :: Developers',
    'Topic :: Software Development :: Build Tools',
    'License :: OSI Approved :: MIT License',
    'Programming Language :: Python :: 3',
  ],
)

