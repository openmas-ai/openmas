"""Setup script for openmas-mqtt-communicator."""

from setuptools import find_packages, setup

setup(
    name="openmas-mqtt-communicator",
    version="0.1.0",
    description="MQTT Communicator plugin for OpenMAS",
    author="OpenMAS Contributors",
    author_email="example@example.com",
    url="https://github.com/example/openmas-mqtt-communicator",
    packages=find_packages(),
    install_requires=[
        "openmas>=0.1.0",
        "asyncio-mqtt>=0.12.0",
    ],
    entry_points={
        "openmas.communicators": [
            "mqtt=mqtt_communicator:MqttCommunicator",
        ],
    },
    classifiers=[
        "Development Status :: 3 - Alpha",
        "Intended Audience :: Developers",
        "License :: OSI Approved :: MIT License",
        "Programming Language :: Python :: 3",
        "Programming Language :: Python :: 3.8",
        "Programming Language :: Python :: 3.9",
        "Programming Language :: Python :: 3.10",
    ],
)
