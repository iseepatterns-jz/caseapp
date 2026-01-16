#!/usr/bin/env python3
"""
MINIMAL AWS CDK Infrastructure - Backend Only
For testing and debugging deployment issues
"""

import os
import aws_cdk as cdk
from constructs import Construct
from aws_cdk import (
    Stack,
    aws_ec2 as ec2,
    aws_ecs as ecs,
    aws_ecs_patterns as ecs_patterns,
    aws_rds as rds,
    aws_secretsmanager as secretsmanager,
    Duration,
    RemovalPolicy,
    CfnOutput
)

class MinimalBackendStack(Stack):
    """Minimal stack with just backend service and database"""
    
    def __init__(self, scope: Construct, construct_id: str, **kwargs) -> None:
        super().__init__(scope, construct_id, **kwargs)
        
        # Get Docker username from environment
        docker_username = os.environ.get('DOCKER_USERNAME', 'iseepatterns')
        
        # VPC - Minimal configuration
        vpc = ec2.Vpc(
            self, "MinimalVPC",
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
        
        # Database - Minimal RDS PostgreSQL
        db_secret = rds.DatabaseSecret(
            self, "DBSecret",
            username="courtcaseadmin"
        )
        
        database = rds.DatabaseInstance(
            self, "MinimalDatabase",
            engine=rds.DatabaseInstanceEngine.postgres(
                version=rds.PostgresEngineVersion.VER_15_8
            ),
            instance_type=ec2.InstanceType.of(
                ec2.InstanceClass.BURSTABLE3,
                ec2.InstanceSize.MICRO  # Smallest instance for testing
            ),
            vpc=vpc,
            vpc_subnets=ec2.SubnetSelection(
                subnet_type=ec2.SubnetType.PRIVATE_WITH_EGRESS
            ),
            credentials=rds.Credentials.from_secret(db_secret),
            database_name="courtcasedb",
            allocated_storage=20,  # Minimum storage
            max_allocated_storage=30,
            deletion_protection=False,  # Allow deletion for testing
            removal_policy=RemovalPolicy.DESTROY,
            backup_retention=Duration.days(1)  # Minimal backup
        )
        
        # Docker Hub credentials secret
        dockerhub_secret = secretsmanager.Secret.from_secret_name_v2(
            self, "DockerHubCredentials",
            secret_name="dockerhub-credentials"
        )
        
        # ECS Cluster
        cluster = ecs.Cluster(
            self, "MinimalCluster",
            vpc=vpc,
            container_insights=False  # Disable to reduce costs
        )
        
        # Create execution role explicitly for Docker Hub credentials
        from aws_cdk import aws_iam as iam
        
        backend_execution_role = iam.Role(
            self, "BackendExecutionRole",
            assumed_by=iam.ServicePrincipal("ecs-tasks.amazonaws.com"),
            managed_policies=[
                iam.ManagedPolicy.from_aws_managed_policy_name(
                    "service-role/AmazonECSTaskExecutionRolePolicy"
                )
            ]
        )
        
        # Grant Docker Hub secret read access to execution role
        dockerhub_secret.grant_read(backend_execution_role)
        
        # Backend Task Definition with explicit execution role
        backend_task = ecs.FargateTaskDefinition(
            self, "BackendTask",
            memory_limit_mib=1024,  # Increased for FastAPI + SQLAlchemy + dependencies
            cpu=512,  # Increased for better performance
            execution_role=backend_execution_role
        )
        
        # Backend Container
        backend_container = backend_task.add_container(
            "web",
            image=ecs.ContainerImage.from_registry(
                f"{docker_username}/court-case-backend:latest"
            ),
            logging=ecs.LogDrivers.aws_logs(stream_prefix="backend"),
            environment={
                "DATABASE_URL": f"postgresql://courtcaseadmin@{database.db_instance_endpoint_address}:5432/courtcasedb",
                "ENVIRONMENT": "production",
                "LOG_LEVEL": "INFO"
            },
            secrets={
                "DATABASE_PASSWORD": ecs.Secret.from_secrets_manager(db_secret, "password")
            },
            health_check=ecs.HealthCheck(
                command=["CMD-SHELL", "curl -f http://localhost:8000/health || exit 1"],
                interval=Duration.seconds(30),
                timeout=Duration.seconds(10),  # Increased for database operations
                retries=3,
                start_period=Duration.seconds(180)  # 3 minutes for DB connection + app startup
            )
        )
        
        backend_container.add_port_mappings(
            ecs.PortMapping(container_port=8000)
        )
        
        # Add Docker Hub credentials via CloudFormation override
        cfn_task_def = backend_task.node.default_child
        cfn_task_def.add_property_override(
            "ContainerDefinitions.0.RepositoryCredentials",
            {
                "CredentialsParameter": dockerhub_secret.secret_arn
            }
        )
        
        # Backend Service with ALB
        backend_service = ecs_patterns.ApplicationLoadBalancedFargateService(
            self, "BackendService",
            cluster=cluster,
            task_definition=backend_task,
            desired_count=1,  # Just 1 task for testing
            public_load_balancer=True,
            health_check_grace_period=Duration.seconds(300),  # 5 minutes for app startup
            circuit_breaker=ecs.DeploymentCircuitBreaker(
                rollback=True,
                enable=True  # Explicitly enable circuit breaker
            )
        )
        
        # Grant database access to backend service (after service is created)
        database.connections.allow_from(
            backend_service.service,
            ec2.Port.tcp(5432),
            "Allow backend to access database"
        )
        
        # Configure health check
        backend_service.target_group.configure_health_check(
            path="/health",  # Simple check without database dependency
            interval=Duration.seconds(30),
            timeout=Duration.seconds(10),
            healthy_threshold_count=2,
            unhealthy_threshold_count=3
        )
        
        # Outputs
        CfnOutput(
            self, "LoadBalancerDNS",
            value=backend_service.load_balancer.load_balancer_dns_name,
            description="Backend API endpoint"
        )
        
        CfnOutput(
            self, "DatabaseEndpoint",
            value=database.db_instance_endpoint_address,
            description="Database endpoint"
        )

# App
app = cdk.App()

MinimalBackendStack(
    app, "MinimalBackendStack",
    env=cdk.Environment(
        account=os.environ.get('CDK_DEFAULT_ACCOUNT'),
        region=os.environ.get('CDK_DEFAULT_REGION', 'us-east-1')
    )
)

app.synth()
