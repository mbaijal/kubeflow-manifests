"""
Installs the vanilla distribution of kubeflow and validates EFS integration by:
    - Installing the EFS Driver from upstream
    - Creating the required IAM Policy, Role and Service Account
    - Creating the EFS Volume 
    - Creating a StorageClass, PersistentVolume and PersistentVolumeClaim using Static Provisioning
"""

import pytest
import subprocess

from e2e.utils.constants import DEFAULT_USER_NAMESPACE
from e2e.utils.config import metadata

from e2e.conftest import region

from e2e.fixtures.cluster import cluster
from e2e.fixtures.clients import account_id

from e2e.fixtures.kustomize import kustomize, configure_manifests

from e2e.fixtures.storage_efs_dependencies import (
    install_efs_csi_driver,
    create_efs_driver_sa,
    create_efs_volume,
    static_provisioning,
    dynamic_provisioning,
)
from e2e.utils.constants import (
    DEFAULT_USER_NAMESPACE,
    DEFAULT_NAMESPACE,
)

GENERIC_KUSTOMIZE_MANIFEST_PATH = "../../../../example"


@pytest.fixture(scope="class")
def kustomize_path():
    return GENERIC_KUSTOMIZE_MANIFEST_PATH


class TestEFS_Static:
    @pytest.fixture(scope="class")
    def setup(self, metadata, kustomize, static_provisioning):
        metadata_file = metadata.to_file()
        print(metadata.params)  # These needed to be logged
        print("Created metadata file for TestSanity", metadata_file)

    def test_pvc_with_volume(
        self,
        metadata,
        setup,
        account_id,
        create_efs_volume,
        static_provisioning,
    ):
        driver_list = subprocess.check_output("kubectl get csidriver".split()).decode()
        assert "efs.csi.aws.com" in driver_list

        pod_list = subprocess.check_output("kubectl get pods -A".split()).decode()
        assert "efs-csi-controller" in pod_list

        sa_account = subprocess.check_output(
            "kubectl describe -n kube-system serviceaccount efs-csi-controller-sa".split()
        ).decode()
        assert f"arn:aws:iam::{account_id}:role" in sa_account

        fs_id = create_efs_volume["file_system_id"]
        assert "fs-" in fs_id

        claim_name = static_provisioning["claim_name"]
        claim_list = subprocess.check_output("kubectl get pvc -A".split()).decode()
        assert claim_name in claim_list


class TestEFS_Dynamic:
    @pytest.fixture(scope="class")
    def setup_dynamic(self, metadata, kustomize, dynamic_provisioning):
        metadata_file = metadata.to_file()
        print(metadata.params)  # These needed to be logged
        print("Created metadata file for TestSanity", metadata_file)

    def test_pvc_with_volume_dynamic(
        self,
        metadata,
        setup_dynamic,
        account_id,
        create_efs_volume,
        dynamic_provisioning,
    ):
        driver_list = subprocess.check_output("kubectl get csidriver".split()).decode()
        assert "efs.csi.aws.com" in driver_list

        pod_list = subprocess.check_output("kubectl get pods -A".split()).decode()
        assert "efs-csi-controller" in pod_list

        sa_account = subprocess.check_output(
            "kubectl describe -n kube-system serviceaccount efs-csi-controller-sa".split()
        ).decode()
        assert f"arn:aws:iam::{account_id}:role" in sa_account

        fs_id = create_efs_volume["file_system_id"]
        assert "fs-" in fs_id

        efs_claim_dyn = dynamic_provisioning["efs_claim_dyn"]
        claim_list = subprocess.check_output("kubectl get pvc -A".split()).decode()
        assert efs_claim_dyn in claim_list

        # TODO: Add this check to static provisioning as well
        # TODO: Status is currently pending but we should also be testing for this to reach bound state
        claim_entry = subprocess.check_output(f"kubectl get pvc -n {DEFAULT_USER_NAMESPACE} {efs_claim_dyn} -o=jsonpath='{{.status.phase}}'".split()).decode()
        assert "Pending" in claim_entry
        
