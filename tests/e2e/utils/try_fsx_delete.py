import boto3
from utils import rand_name
from utils import (
    rand_name,
    wait_for,
    curl_file_to_path,
    load_json_file,
)
from time import sleep
import botocore


region = "eu-west-1"
cluster= "e2e-test-cluster-"
eks_client = boto3.client("eks", region_name=region)
fsx_client = boto3.client("fsx", region_name=region)
ec2_client = boto3.client("ec2", region_name=region)

def wait_on_fsx_deletion(fsx_client, file_system_id):
    def callback():
        try:
            response = fsx_client.describe_file_systems(
                FileSystemIds=[file_system_id],
            )
            number_of_file_systems_with_id = len(response["FileSystems"])
            print(f"{file_system_id} has {number_of_file_systems_with_id} results .... waiting")
            assert number_of_file_systems_with_id == 0 
        except fsx_client.exceptions.FileSystemNotFound:
            return True

    wait_for(callback)


sg_id = ""
file_system_id = "fs-"

print(f"deleting filesystem {file_system_id}")
# delete the filesystem
fsx_client.delete_file_system(
    FileSystemId=file_system_id,
)

wait_on_fsx_deletion(fsx_client, file_system_id)
print(f"deleted filesystem {file_system_id}")

# delete the security group
# ec2_client.delete_security_group(GroupId=sg_id)
