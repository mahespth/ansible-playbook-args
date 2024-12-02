
from setuptools import setup, find_packages

setup(
    name="ansilble-playbook-args",
    version="1.0.0",
    packages=find_packages(),
    entry_points={
        "console_scripts": [
            "my_command=my_package.main:main",
        ],
    },
    install_requires=[],
    python_requires=">=3.6",
    description="Execute Ansible Playbooks with flags that are transposed to ansible input."
    long_description=open("README.md").read(),
    long_description_content_type="text/markdown",
    author="Stephen Maher",
    author_email="steve@aixtreme.org"
    url="https://github.com/mahespth/ansible-playbook-args",
    classifiers=[
        "Programming Language :: Python :: 3",
        "License :: OSI Approved :: GNU General Public License v3 (GPLv3)",
        "Operating System :: OS Independent",
    ],
)

