import boto3
from e2e.utils.utils import rand_name
from e2e.utils.utils import (
    rand_name,
    wait_for,
    curl_file_to_path,
    get_security_group_id_from_name
)
from time import sleep
from e2e.fixtures.cluster import associate_iam_oidc_provider, create_iam_service_account


region = "eu-west-1"
cluster= "e2e-test-cluster-"
eks_client = boto3.client("eks", region_name=region)
efs_client = boto3.client("efs", region_name=region)
ec2_client = boto3.client("ec2", region_name=region)

def wait_on_efs_status(desired_status, efs_client, file_system_id):
    def callback():
        response = efs_client.describe_file_systems(
            FileSystemId=file_system_id,
        )
        filesystem_status = response["FileSystems"][0]["LifeCycleState"]
        print(f"{file_system_id} {filesystem_status} .... waiting")
        assert filesystem_status == desired_status

    wait_for(callback)

def wait_on_mount_target_status(desired_status, efs_client, file_system_id):
    def callback():
        response = efs_client.describe_file_systems(
            FileSystemId=file_system_id,
        )
        number_of_mount_targets = response["FileSystems"][0]["NumberOfMountTargets"]
        print(f"{file_system_id} has {number_of_mount_targets} mount targets .... waiting")
        if desired_status == "deleted": assert number_of_mount_targets == 0
        else: assert number_of_mount_targets > 0

    wait_for(callback)

def wait_on_efs_deletion(efs_client, file_system_id):
    def callback():
        try:
            response = efs_client.describe_file_systems(
            FileSystemId=file_system_id,
            )
            number_of_file_systems_with_id = len(response["FileSystems"])
            print(f"{file_system_id} has {number_of_file_systems_with_id} results .... waiting")
            assert number_of_file_systems_with_id == 0 
        except efs_client.exceptions.FileSystemNotFound:
            return True

    wait_for(callback)

# Get VPC ID
response = eks_client.describe_cluster(name=cluster)
vpc_id = response["cluster"]["resourcesVpcConfig"]["vpcId"]

# Get CIDR Range
response = ec2_client.describe_vpcs( 
    VpcIds=[
        vpc_id,
    ]
)
cidr_ip = response["Vpcs"][0]["CidrBlock"]

# Create Security Group
security_group_name = rand_name("efs-security-group-")
response = ec2_client.create_security_group(
    VpcId=vpc_id,
    GroupName=security_group_name,
    Description="My EFS security group",
)
security_group_id = response["GroupId"]

# Open Port for CIDR Range
response = ec2_client.authorize_security_group_ingress(
    GroupId=security_group_id,
    FromPort=2049,
    ToPort=2049,
    CidrIp=cidr_ip,
    IpProtocol="tcp",
)

# Create an Amazon EFS FileSystem for your EKS Cluster
response = efs_client.create_file_system(
    PerformanceMode="generalPurpose",
)
file_system_id = response["FileSystemId"]

# Check for status of filesystem to be "available" before creating mount targets
wait_on_efs_status("available", efs_client, file_system_id)

# Get Subnet Ids
response = ec2_client.describe_subnets(
    Filters=[
        {
            "Name": "vpc-id",
            "Values": [
                vpc_id,
            ],
        },
    ]
)

# Create Mount Targets for each subnet - TODO: Check how many subnets this needs to be added to.
subnets = response["Subnets"]
for subnet in subnets:
    subnet_id = subnet["SubnetId"]
    response = efs_client.create_mount_target(
        FileSystemId=file_system_id,
        SecurityGroups=[
            security_group_id,
        ],
        SubnetId=subnet_id,
    )


# Get FileSystem_ID
fs_id = file_system_id
sg_id = security_group_id

# Delete the Mount Targets
response = efs_client.describe_mount_targets(
    FileSystemId=fs_id,
)
existing_mount_targets = response["MountTargets"]
for mount_target in existing_mount_targets:
    mount_target_id = mount_target["MountTargetId"]
    efs_client.delete_mount_target(
        MountTargetId=mount_target_id,
    )

wait_on_mount_target_status("deleted", efs_client, fs_id)

# Delete the Filesystem

efs_client.delete_file_system(
    FileSystemId=fs_id,
)
# wait_on_efs_status("deleting", efs_client, fs_id)
wait_on_efs_deletion(efs_client, fs_id)




# Delete the Security Group
sg_id=get_security_group_id_from_name(ec2_client, eks_client, security_group_name, cluster)
print(security_group_name, sg_id)
ec2_client.delete_security_group(GroupId=sg_id)






# efs_deps = {}
# iam_client = boto3.client("iam")

# EFS_IAM_POLICY = "https://raw.githubusercontent.com/kubernetes-sigs/aws-efs-csi-driver/v1.3.4/docs/iam-policy-example.json"
# policy_name = rand_name("efs-iam-policy-")
# policy_arn = [f"arn:aws:iam::169544399729:policy/{policy_name}"]

# curl_file_to_path(EFS_IAM_POLICY, "iam-policy-example.json")
# with open("iam-policy-example.json", "r") as myfile:
#     policy = myfile.read()

# response = iam_client.create_policy(
#     PolicyName=policy_name,
#     PolicyDocument=policy,
# )
# policy_arn = response["Policy"]["Arn"]
# assert policy_arn is not None

# create_iam_service_account(
#     "efs-csi-controller-sa",
#     "kube-system",
#     cluster,
#     region,
#     policy_arn,
# )

# iam_client.delete_policy(
#     PolicyArn=policy_arn,
# )