import setuptools

setuptools.setup(
    name='update-nix-sources',
    packages=setuptools.find_packages(),
    entry_points={
        'console_scripts': ['update-nix-sources=src.update_nix_sources:run']
    }
)