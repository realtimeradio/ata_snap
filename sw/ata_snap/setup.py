from distutils.core import setup
import glob

setup(
    name='ata_snap',
    version='0.0.1',
    author='J.Hickish',
    author_email='jackhickish@gmail.com',
    url='',
    #license='LICENSE.txt',
    description='Control and collect data from the ATA\'s SNAP DSP boards.',
    #long_description=open('README.txt').read(),
    install_requires=[
        'casperfpga',
        'numpy',
    ],
    provides=['ata_snap'],
    packages=['ata_snap'],
    package_dir={'ata_snap': 'src'},
    scripts=glob.glob('scripts/*'),
)

