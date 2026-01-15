#!/usr/bin/env python3
"""
Minimal Test Stack - Just VPC + RDS + 1 ECS Task
Purpose: Quickly validate RDS secret fix without waiting 30+ minutes
"""

import aws_cdk as cdk
from constructs import Construct
from aws_cdk import (
    Stack,
    aws_ec2 as ec2,
    aws_ecs as ecs,
    aws_rds as rds,
    aws_iam as iam,
    aws_logs as logs,
    Duration,
    RemovalPolicy
)

class MinimalTestStack(Stack):
    """Minimal stack to test RDS secret configuration"""
    
    def __init__(self, scope: Construct, construct_id: str, **kwargs) -> None:
        super().__init__(scope, construct_id, **kwargs)
        
        # VPC - minimal configuration
        self.vpc = ec2.Vpc(
            self, "TestVPC",
            max_azs=2,
            nat_gateways=1,
            subnet_configuration=[
                ec2.SubnetConfiguration(
                    name="Public",
                    subnet_type=ec2.SubnetType.PUBLIC,
                    cidr_mask=24
                ),
                ec2.SubnetConfiguration(
                    name="Private",
                    subnet_type=ec2.SubnetType.PRIVATE_WITH_EGRESS,
                    cidr_mask=24
                )
            ]
        )
        
        # RDS Database - minimal configuration
        db_security_group = ec2.SecurityGroup(
            self, "DBSecurityGroup",
            vpc=self.vpc,
            description="Security group for test RDS database",
            allow_all_outbound=True
        )
        
        self.database = rds.DatabaseInstance(
            self, "TestDatabase",
            engine=rds.DatabaseInstanceEngine.postgres(
                version=rds.PostgresEngineVersion.VER_15
            ),
            instance_type=ec2.InstanceType.of(
                ec2.InstanceClass.BURSTABLE3,
                ec2.InstanceSize.MICRO
            ),
            vpc=self.vpc,
            vpc_subnets=ec2.SubnetSelection(
                subnet_type=ec2.SubnetType.PRIVATE_WITH_EGRESS
            ),
            security_groups=[db_security_group],
            allocated_storage=20,
            max_allocated_storage=100,
            database_name="testdb",
            deletion_protection=False,  # Allow easy cleanup
            removal_policy=RemovalPolicy.DESTROY,
            backup_retention=Duration.days(0)  # No backups for test
        )
        
        # ECS Cluster
        cluster = ecs.Cluster(
            self, "TestCluster",
            vpc=self.vpc,
            container_insights=False  # Disable for faster creation
        )
        
        # ECS Task Definition with RDS secret fix
        task_definition = ecs.FargateTaskDefinition(
            self, "TestTaskDef",
            memory_limit_mib=512,
            cpu=256
        )
        
        # Container with individual RDS secret fields (THE FIX)
        container = task_definition.add_container(
            "TestContainer",
            image=ecs.ContainerImage.from_registry("public.ecr.aws/docker/library/python:3.11-slim"),
            logging=ecs.LogDrivers.aws_logs(
                stream_prefix="test",
                log_retention=logs.RetentionDays.ONE_DAY
            ),
            environment={
                "TEST_MODE": "true"
            },
            secrets={
                # Use individual secret fields from RDS-generated secret (THE FIX)
                "DB_HOST": ecs.Secret.from_secrets_manager(self.database.secret, "host"),
                "DB_USER": ecs.Secret.from_secrets_manager(self.database.secret, "username"),
                "DB_PASSWORD": ecs.Secret.from_secrets_manager(self.database.secret, "password"),
                "DB_PORT": ecs.Secret.from_secrets_manager(self.database.secret, "port"),
                "DB_NAME": ecs.Secret.from_secrets_manager(self.database.secret, "dbname")
            },
            command=[
                "python", "-c",
                "import os; print(f'DB_HOST={os.environ.get(\"DB_HOST\")}'); print(f'DB_USER={os.environ.get(\"DB_USER\")}'); print(f'DB_PORT={os.environ.get(\"DB_PORT\")}'); print(f'DB_NAME={os.environ.get(\"DB_NAME\")}'); print('✅ Secret fields loaded successfully!'); import time; time.sleep(300)"
            ]
        )
        
        # Grant task access to secrets
        self.database.secret.grant_read(task_definition.task_role)
        
        # ECS Service Security Group
        service_sg = ec2.SecurityGroup(
            self, "ServiceSecurityGroup",
            vpc=self.vpc,
            description="Security group for test ECS service",
            allow_all_outbound=True
        )
        
        # Allow ECS to connect to RDS
        db_security_group.add_ingress_rule(
            peer=service_sg,
            connection=ec2.Port.tcp(5432),
            description="Allow ECS tasks to connect to RDS"
        )
        
        # ECS Service - just 1 task
        service = ecs.FargateService(
            self, "TestService",
            cluster=cluster,
            task_definition=task_definition,
            desired_count=1,
            security_groups=[service_sg],
            vpc_subnets=ec2.SubnetSelection(
                subnet_type=ec2.SubnetType.PRIVATE_WITH_EGRESS
            )
        )
        
        # Outputs
        cdk.CfnOutput(
            self, "ClusterName",
            value=cluster.cluster_name,
            description="ECS Cluster Name"
        )
        
        cdk.CfnOutput(
            self, "ServiceName",
            value=service.service_name,
            description="ECS Service Name"
        )
        
        cdk.CfnOutput(
            self, "DatabaseEndpoint",
            value=self.database.db_instance_endpoint_address,
            description="RDS Database Endpoint"
        )

# App
app = cdk.App()
MinimalTestStack(app, "MinimalTestStack", env=cdk.Environment(
    account="730335557645",
    region="us-east-1"
))
app.synth()
