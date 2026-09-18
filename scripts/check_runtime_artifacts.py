"""Check reviewed database build inputs and consumers without operator state."""
from __future__ import annotations

import json
import hashlib
from pathlib import Path
import re

import yaml


ROOT = Path(__file__).resolve().parents[1]
DIGEST = re.compile(r"sha256:[0-9a-f]{64}\Z")


def require(condition: bool, message: str) -> None:
    if not condition:
        raise SystemExit(message)


def validate(root: Path = ROOT) -> dict:
    inventory = json.loads((root / "runtime-artifacts.json").read_text(encoding="utf-8"))
    require(set(inventory) == {"database"}, "Runtime inventory must contain only the reviewed database artifact")
    database = inventory["database"]
    require(isinstance(database, dict), "Database artifact metadata is invalid")
    require(database.get("kind") == "reviewed_local_build",
            "Database artifact must use the reviewed local build")
    digest = database.get("base_oci_index_digest", "")
    manifest = database.get("base_platform_manifest_digest", "")
    require(isinstance(digest, str) and DIGEST.fullmatch(digest) is not None,
            "Database OCI index digest is invalid")
    require(isinstance(manifest, str) and DIGEST.fullmatch(manifest) is not None,
            "Database platform manifest digest is invalid")
    recipe_hash = database.get("recipe_sha256", "")
    require(isinstance(recipe_hash, str) and re.fullmatch(r"[0-9a-f]{64}", recipe_hash) is not None,
            "Database aggregate recipe hash is invalid")
    image = "cardchemy-database:pg16-vector0.8.6-" + recipe_hash
    base_image = f"postgres:16-alpine3.24@{digest}"
    require(database.get("image") == image and database.get("base_image") == base_image,
            "Database image/base must match the reviewed PG16 Alpine build")
    require(database.get("supported_platform") == "linux/amd64"
            and database.get("postgres_major") == 16
            and database.get("pgvector_extension_version") == "0.8.6"
            and database.get("postgres_data_directory") == "/var/lib/postgresql/data",
            "Database platform, extension or data path differs from the reviewed contract")
    require(database.get("postgres_version") == "16.15"
            and database.get("fresh_cluster_initdb_args")
            == "--encoding=UTF8 --locale-provider=icu --icu-locale=en-US"
            and database.get("upgrade_policy") == "logical_restore_to_separate_target",
            "Database version, ICU initialization or safe upgrade policy is invalid")
    recipe_path = database.get("recipe_path")
    require(recipe_path == "docker/database/Dockerfile", "Database recipe path is invalid")
    recipe_bytes = (root / recipe_path).read_bytes()
    recipe = recipe_bytes.decode("utf-8")
    required_inputs = {"Dockerfile", "database-entrypoint.sh", "verify-initial-profile.sh",
                       ".dockerignore", ".gitattributes"}
    input_hashes = database.get("recipe_inputs", {})
    require(set(input_hashes) == required_inputs, "Database recipe input inventory is incomplete")
    actual_hashes = {}
    for name in sorted(required_inputs):
        content = (root / "docker/database" / name).read_bytes()
        require(b"\r" not in content, "Database recipe/scripts require LF line endings")
        actual_hashes[name] = hashlib.sha256(content).hexdigest()
    require(input_hashes == actual_hashes, "Database recipe input hashes differ from the reviewed inventory")
    aggregate_hash = hashlib.sha256(json.dumps(actual_hashes, sort_keys=True,
                                               separators=(",", ":")).encode()).hexdigest()
    require(database.get("recipe_sha256") == aggregate_hash,
            "Database recipe hash differs from the reviewed inventory")
    require(database.get("source_url") == "https://codeload.github.com/pgvector/pgvector/tar.gz/refs/tags/v0.8.6"
            and database.get("source_sha256") == "10bf9938906e5d643bbc4a7eea104b6f57ba4898e5b76b20e60484ea1d5a7f8f"
            and database.get("source_commit") == "8ee86c96f0fd72390f890aa8a336fda6d3ab4c6c"
            and database.get("compiler_options") == 'OPTFLAGS="" with_llvm=no',
            "Database extension source/compiler identity is invalid")
    require(base_image in recipe and database["source_url"] in recipe
            and database["source_sha256"] in recipe
            and database["compiler_options"] in recipe,
            "Database recipe does not contain the reviewed pinned inputs")
    packages = database.get("build_packages", []) + database.get("runtime_packages", [])
    require(bool(packages) and len(set(packages)) == len(packages)
            and all(isinstance(package, str) and re.fullmatch(r"[a-z0-9+-]+=[0-9][a-z0-9.+_-]*", package)
                    and package in recipe for package in packages)
            and database.get("runtime_packages") == ["su-exec=0.3-r0"],
            "Database compiler/runtime package versions must be locked in the recipe")

    compose = yaml.safe_load((root / "docker-compose.yml").read_text(encoding="utf-8"))
    service = compose["services"]["db"]
    require(service.get("image") == image and service.get("platform") == "linux/amd64",
            "Compose database image/platform must match the reviewed inventory")
    require(service.get("build", {}).get("context") == "./docker/database"
            and service.get("build", {}).get("dockerfile") == "Dockerfile"
            and service.get("build", {}).get("labels", {}).get("org.cardchemy.database.recipe-sha256")
            == database["recipe_sha256"],
            "Compose database recipe identity differs from the reviewed inventory")
    require("postgres_data:/var/lib/postgresql/data" in service.get("volumes", [])
            and "postgres_data" in compose.get("volumes", {}),
            "Compose must preserve the existing PostgreSQL data volume path")

    workflow = yaml.load((root / ".github/workflows/ci.yml").read_text(encoding="utf-8"),
                         Loader=yaml.BaseLoader)
    job = workflow["jobs"].get("database-artifact", {})
    require(job.get("env", {}).get("DB_IMAGE") == image,
            "Mandatory CI database image must match the reviewed inventory")
    require(job.get("env", {}).get("DB_PLATFORM") == "linux/amd64",
            "Mandatory CI must scan the supported database platform")
    return database


if __name__ == "__main__":
    database = validate()
    print("Reviewed database base/source/recipe identity, platform, Compose volume and CI identity match.")
