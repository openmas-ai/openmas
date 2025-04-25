"""Generators for deployment configurations from OpenMAS metadata."""

from pathlib import Path
from typing import Any, Dict, List, Union

import yaml

from openmas.deployment.metadata import DeploymentMetadata, EnvironmentVar


class DockerComposeGenerator:
    """Generator for Docker Compose configurations."""

    def generate(self, metadata: DeploymentMetadata) -> Dict[str, Any]:
        """Generate Docker Compose configuration from metadata.

        Args:
            metadata: Deployment metadata

        Returns:
            Docker Compose configuration as a dictionary
        """
        service_name = metadata.component.name
        service_config: Dict[str, Any] = {}

        # Docker build or image
        if metadata.docker.build:
            service_config["build"] = {
                "context": metadata.docker.build.context,
                "dockerfile": metadata.docker.build.dockerfile,
            }
            if metadata.docker.build.args:
                service_config["build"]["args"] = {arg["name"]: arg["value"] for arg in metadata.docker.build.args}
        elif metadata.docker.image:
            service_config["image"] = metadata.docker.image

        # Environment variables
        if metadata.environment:
            service_config["environment"] = []
            for env_var in metadata.environment:
                if env_var.secret:
                    # For Docker Compose, we just list the secret variables
                    # without a value, expecting them to be supplied externally
                    service_config["environment"].append(env_var.name)
                else:
                    value = env_var.value or ""
                    service_config["environment"].append(f"{env_var.name}={value}")

        # Ports
        if metadata.ports:
            service_config["ports"] = []
            for port_spec in metadata.ports:
                service_config["ports"].append(f"{port_spec.port}:{port_spec.port}")

        # Volumes
        if metadata.volumes:
            service_config["volumes"] = []
            for volume_spec in metadata.volumes:
                service_config["volumes"].append(f"./{volume_spec.name}:{volume_spec.path}")

        # Dependencies
        if metadata.dependencies:
            service_config["depends_on"] = []
            for dependency in metadata.dependencies:
                if dependency.required:
                    service_config["depends_on"].append(dependency.name)

        # Health check
        if metadata.health_check:
            service_config["healthcheck"] = {
                "test": [
                    "CMD",
                    "curl",
                    "-f",
                    f"http://localhost:{metadata.health_check.port}{metadata.health_check.path}",
                ],
                "interval": f"{metadata.health_check.period_seconds}s",
                "timeout": "10s",
                "retries": 3,
                "start_period": f"{metadata.health_check.initial_delay_seconds}s",
            }

        # Combine into a Docker Compose configuration
        compose_config = {"version": "3", "services": {service_name: service_config}}

        return compose_config

    def save(self, metadata: DeploymentMetadata, output_path: Union[str, Path]) -> Path:
        """Generate and save Docker Compose configuration to a file.

        Args:
            metadata: Deployment metadata
            output_path: Path to save the configuration file

        Returns:
            Path to the saved file
        """
        compose_config = self.generate(metadata)

        path = Path(output_path)
        with open(path, "w") as f:
            yaml.safe_dump(compose_config, f, sort_keys=False)

        return path


class DockerfileGenerator:
    """Generator for Dockerfiles."""

    def generate_pip_dockerfile(
        self, python_version: str, app_entrypoint: str, requirements_file: str, port: int
    ) -> str:
        """Generate a Dockerfile using pip for dependencies.

        Args:
            python_version: Python version to use
            app_entrypoint: Application entrypoint file
            requirements_file: Path to requirements file
            port: Port to expose

        Returns:
            Dockerfile content as a string
        """
        return f"""# OpenMAS Agent Dockerfile
# Generated with openmas deploy generate-dockerfile

FROM python:{python_version}-slim

WORKDIR /app

# Copy requirements first for better caching
COPY {requirements_file} .
RUN pip install --no-cache-dir -r {requirements_file}

# Copy application code
COPY . .

# Expose the port the app runs on
EXPOSE {port}

# Set environment variables
ENV PYTHONUNBUFFERED=1 \\
    PYTHONDONTWRITEBYTECODE=1 \\
    AGENT_PORT={port}

# Run the application
CMD ["python", "{app_entrypoint}"]
"""

    def generate_poetry_dockerfile(self, python_version: str, app_entrypoint: str, port: int) -> str:
        """Generate a Dockerfile using Poetry for dependencies.

        Args:
            python_version: Python version to use
            app_entrypoint: Application entrypoint file
            port: Port to expose

        Returns:
            Dockerfile content as a string
        """
        return f"""# OpenMAS Agent Dockerfile
# Generated with openmas deploy generate-dockerfile

FROM python:{python_version}-slim

WORKDIR /app

# Install Poetry
RUN pip install --no-cache-dir poetry && \\
    poetry config virtualenvs.create false

# Copy Poetry configuration files
COPY pyproject.toml poetry.lock* ./

# Install dependencies
RUN poetry install --no-dev --no-interaction --no-ansi

# Copy application code
COPY . .

# Expose the port the app runs on
EXPOSE {port}

# Set environment variables
ENV PYTHONUNBUFFERED=1 \\
    PYTHONDONTWRITEBYTECODE=1 \\
    AGENT_PORT={port}

# Run the application
CMD ["poetry", "run", "python", "{app_entrypoint}"]
"""

    def save(
        self,
        output_path: Union[str, Path],
        python_version: str,
        app_entrypoint: str,
        requirements_file: str = "requirements.txt",
        use_poetry: bool = False,
        port: int = 8000,
    ) -> Path:
        """Generate and save a Dockerfile to a file.

        Args:
            output_path: Path to save the Dockerfile
            python_version: Python version to use
            app_entrypoint: Application entrypoint file
            requirements_file: Path to requirements file (only for pip)
            use_poetry: Whether to use Poetry for dependency management
            port: Port to expose

        Returns:
            Path to the saved file
        """
        if use_poetry:
            dockerfile_content = self.generate_poetry_dockerfile(python_version, app_entrypoint, port)
        else:
            dockerfile_content = self.generate_pip_dockerfile(python_version, app_entrypoint, requirements_file, port)

        path = Path(output_path)
        with open(path, "w") as f:
            f.write(dockerfile_content)

        return path


class KubernetesGenerator:
    """Generator for Kubernetes manifests."""

    def generate(self, metadata: DeploymentMetadata) -> List[Dict[str, Any]]:
        """Generate Kubernetes manifests from metadata.

        Args:
            metadata: Deployment metadata

        Returns:
            List of Kubernetes manifests as dictionaries
        """
        manifests: List[Dict[str, Any]] = []

        # Determine the image to use
        image = metadata.docker.image
        if not image and metadata.docker.build:
            # Use a placeholder image name based on the component name
            # In real use, this would come from a Docker registry
            image = f"{metadata.component.name}:latest"

        # Create deployment manifest
        if image:
            deployment = self._create_deployment(metadata, image)
            manifests.append(deployment)

        # Create service manifest if ports are defined
        if metadata.ports:
            service = self._create_service(metadata)
            manifests.append(service)

        # Create secret manifests if needed
        secret_env_vars = [env for env in metadata.environment if env.secret]
        if secret_env_vars:
            secret = self._create_secret(metadata, secret_env_vars)
            manifests.append(secret)

        return manifests

    def _create_deployment(self, metadata: DeploymentMetadata, image: str) -> Dict[str, Any]:
        """Create a Kubernetes Deployment manifest.

        Args:
            metadata: Deployment metadata
            image: Container image to use

        Returns:
            Deployment manifest as a dictionary
        """
        component_name = metadata.component.name

        # Prepare container environment variables
        env: List[Dict[str, Any]] = []
        for env_var in metadata.environment:
            if env_var.secret:
                env.append(
                    {
                        "name": env_var.name,
                        "valueFrom": {"secretKeyRef": {"name": f"{component_name}-secrets", "key": env_var.name}},
                    }
                )
            else:
                env.append({"name": env_var.name, "value": env_var.value or ""})

        # Prepare container ports
        ports: List[Dict[str, Any]] = []
        for port_spec in metadata.ports:
            ports.append(
                {
                    "containerPort": port_spec.port,
                    "protocol": "TCP" if port_spec.protocol.lower() in ("http", "tcp") else "UDP",
                }
            )

        # Prepare volume mounts and volumes
        volume_mounts: List[Dict[str, str]] = []
        volumes: List[Dict[str, Any]] = []
        for i, volume_spec in enumerate(metadata.volumes):
            volume_name = f"{component_name}-{volume_spec.name}"
            volume_mounts.append({"name": volume_name, "mountPath": volume_spec.path})
            volumes.append({"name": volume_name, "emptyDir": {}})  # Use emptyDir as a basic volume type

        # Prepare container resources
        resources: Dict[str, Any] = {}
        if metadata.resources:
            resources = {
                "requests": {"cpu": metadata.resources.cpu, "memory": metadata.resources.memory},
                "limits": {"cpu": metadata.resources.cpu, "memory": metadata.resources.memory},
            }

        # Prepare health check
        readiness_probe = None
        if metadata.health_check:
            readiness_probe = {
                "httpGet": {"path": metadata.health_check.path, "port": metadata.health_check.port},
                "initialDelaySeconds": metadata.health_check.initial_delay_seconds,
                "periodSeconds": metadata.health_check.period_seconds,
            }

        # Create container spec
        container: Dict[str, Any] = {"name": component_name, "image": image, "env": env}

        if ports:
            container["ports"] = ports
        if volume_mounts:
            container["volumeMounts"] = volume_mounts
        if resources:
            container["resources"] = resources
        if readiness_probe:
            container["readinessProbe"] = readiness_probe

        # Create deployment manifest
        deployment: Dict[str, Any] = {
            "apiVersion": "apps/v1",
            "kind": "Deployment",
            "metadata": {
                "name": component_name,
                "labels": {"app": component_name, "component-type": metadata.component.type},
            },
            "spec": {
                "replicas": 1,
                "selector": {"matchLabels": {"app": component_name}},
                "template": {"metadata": {"labels": {"app": component_name}}, "spec": {"containers": [container]}},
            },
        }

        # Add volumes if defined
        if volumes:
            deployment["spec"]["template"]["spec"]["volumes"] = volumes

        return deployment

    def _create_service(self, metadata: DeploymentMetadata) -> Dict[str, Any]:
        """Create a Kubernetes Service manifest.

        Args:
            metadata: Deployment metadata

        Returns:
            Service manifest as a dictionary
        """
        component_name = metadata.component.name

        # Prepare service ports
        ports: List[Dict[str, Any]] = []
        for port_spec in metadata.ports:
            ports.append(
                {
                    "port": port_spec.port,
                    "targetPort": port_spec.port,
                    "protocol": "TCP" if port_spec.protocol.lower() in ("http", "tcp") else "UDP",
                }
            )

        # Create service manifest
        service: Dict[str, Any] = {
            "apiVersion": "v1",
            "kind": "Service",
            "metadata": {"name": f"{component_name}-service", "labels": {"app": component_name}},
            "spec": {"selector": {"app": component_name}, "ports": ports, "type": "ClusterIP"},
        }

        return service

    def _create_secret(self, metadata: DeploymentMetadata, secret_env_vars: List[EnvironmentVar]) -> Dict[str, Any]:
        """Create a Kubernetes Secret manifest.

        Args:
            metadata: Deployment metadata
            secret_env_vars: List of secret environment variables

        Returns:
            Secret manifest as a dictionary
        """
        component_name = metadata.component.name

        # Create an empty secret (values to be filled in externally)
        string_data: Dict[str, str] = {}

        # Add placeholder for each secret
        for env_var in secret_env_vars:
            string_data[env_var.name] = ""

        secret: Dict[str, Any] = {
            "apiVersion": "v1",
            "kind": "Secret",
            "metadata": {"name": f"{component_name}-secrets"},
            "type": "Opaque",
            "stringData": string_data,
        }

        return secret

    def save(self, metadata: DeploymentMetadata, output_dir: Union[str, Path]) -> List[Path]:
        """Generate and save Kubernetes manifests to files.

        Args:
            metadata: Deployment metadata
            output_dir: Directory to save the manifests in

        Returns:
            List of paths to the saved files
        """
        manifests = self.generate(metadata)
        component_name = metadata.component.name

        output_path = Path(output_dir)
        output_path.mkdir(parents=True, exist_ok=True)

        saved_paths: List[Path] = []
        for i, manifest in enumerate(manifests):
            kind = manifest["kind"].lower()
            file_path = output_path / f"{component_name}-{kind}.yaml"

            with open(file_path, "w") as f:
                yaml.safe_dump(manifest, f, sort_keys=False)

            saved_paths.append(file_path)

        return saved_paths
