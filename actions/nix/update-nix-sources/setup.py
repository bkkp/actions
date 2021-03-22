import setuptools

setuptools.setup(
    name='update-nix-sources',
    version='2021.1', 
    author='Kristoffer Føllesdal',
    author_email='kristoffer.follesdal@bkk.no',
    packages=setuptools.find_packages(),
    entry_points={
        'console_scripts': ['update-nix-sources=src.update_nix_sources:run']
    }
)