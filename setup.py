from setuptools import find_packages, setup

with open("README.md", "r") as f:
    long_description = f.read()

setup(
    name="lost-n-phoned",
    version="0.1.2",
    maintainer="Keane Nguyen",
    maintainer_email="keanekyn@gmail.com",
    description="Get your contacts from a stranger's phone",
    long_description=long_description,
    long_description_content_type="text/markdown",
    url="https://github.com/ljacob15/lost-and-phoned",
    packages=find_packages(),
    include_package_data=True,
    zip_safe=False,
    install_requires=[
        "flask",
        "requests",
        "google-auth",
        "google-auth-oauthlib",
        "google-auth-httplib2",
        "google-api-python-client",
        "twilio",
        "phonenumberslite"
    ],
    python_requires=">=3.4",
)
