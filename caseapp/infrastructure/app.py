#!/usr/bin/env python3
"""
AWS CDK Infrastructure for Court Case Management System
"""

import aws_cdk as cdk
from constructs import Construct
from aws_cdk import (
    Stack,
    aws_ec2 as ec2,
    aws_ecs as ecs,
    aws_ecs_patterns as ecs_patterns,
    aws_rds as rds,
    aws_s3 as s3,
    aws_cloudfront as cloudfront,
    aws_elasticache as elasticache,
    aws_opensearchservice as opensearch,
    aws_cognito as cognito,
    aws_iam as iam,
    aws_logs as logs,
    Duration,
    RemovalPolicy
)

class CourtCaseManagementStack(Stack):
    """Main infrastructure stack"""
    
    def __init__(self, scope: Construct, construct_id: str, **kwargs) -> None:
        super().__init__(scope, construct_id, **kwargs)
        
        # VPC
        self.vpc = ec2.Vpc(
            self, "CourtCaseVPC",
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
                ),
                ec2.SubnetConfiguration(
                    name="Database",
                    subnet_type=ec2.SubnetType.PRIVATE_ISOLATED,
                    cidr_mask=24
                )
            ]
        )
        
        # S3 Buckets
        self.create_s3_buckets()
        
        # Database
        self.create_database()
        
        # Redis Cache
        self.create_redis_cache()
        
        # OpenSearch
        self.create_opensearch()
        
        # Cognito
        self.create_cognito()
        
        # ECS Cluster
        self.create_ecs_cluster()
        
        # Media Processing
        self.create_media_services()
        
        # AI Services Setup
        self.setup_ai_services()
    
    def create_s3_buckets(self):
        """Create S3 buckets for document and media storage"""
        
        # Documents bucket
        self.documents_bucket = s3.Bucket(
            self, "DocumentsBucket",
            versioned=True,
            encryption=s3.BucketEncryption.S3_MANAGED,
            block_public_access=s3.BlockPublicAccess.BLOCK_ALL,
            lifecycle_rules=[
                s3.LifecycleRule(
                    id="ArchiveOldDocuments",
                    enabled=True,
                    transitions=[
                        s3.Transition(
                            storage_class=s3.StorageClass.INFREQUENT_ACCESS,
                            transition_after=Duration.days(30)
                        ),
                        s3.Transition(
                            storage_class=s3.StorageClass.GLACIER,
                            transition_after=Duration.days(90)
                        )
                    ]
                )
            ],
            removal_policy=RemovalPolicy.RETAIN
        )
        
        # Media bucket for audio/video evidence
        self.media_bucket = s3.Bucket(
            self, "MediaBucket",
            versioned=True,
            encryption=s3.BucketEncryption.S3_MANAGED,
            block_public_access=s3.BlockPublicAccess.BLOCK_ALL,
            cors=[
                s3.CorsRule(
                    allowed_methods=[s3.HttpMethods.GET, s3.HttpMethods.POST],
                    allowed_origins=["*"],
                    allowed_headers=["*"],
                    max_age=3000
                )
            ],
            lifecycle_rules=[
                s3.LifecycleRule(
                    id="MediaArchiving",
                    enabled=True,
                    transitions=[
                        s3.Transition(
                            storage_class=s3.StorageClass.INFREQUENT_ACCESS,
                            transition_after=Duration.days(60)
                        ),
                        s3.Transition(
                            storage_class=s3.StorageClass.DEEP_ARCHIVE,
                            transition_after=Duration.days(365)
                        )
                    ]
                )
            ],
            removal_policy=RemovalPolicy.RETAIN
        )
    
    def create_database(self):
        """Create RDS PostgreSQL database"""
        
        # Database subnet group
        db_subnet_group = rds.SubnetGroup(
            self, "DatabaseSubnetGroup",
            description="Subnet group for court case database",
            vpc=self.vpc,
            vpc_subnets=ec2.SubnetSelection(
                subnet_type=ec2.SubnetType.PRIVATE_ISOLATED
            )
        )
        
        # Database security group
        db_security_group = ec2.SecurityGroup(
            self, "DatabaseSecurityGroup",
            vpc=self.vpc,
            description="Security group for court case database",
            allow_all_outbound=False
        )
        
        # Database instance
        self.database = rds.DatabaseInstance(
            self, "CourtCaseDatabase",
            engine=rds.DatabaseInstanceEngine.postgres(
                version=rds.PostgresEngineVersion.VER_15_4
            ),
            instance_type=ec2.InstanceType.of(
                ec2.InstanceClass.BURSTABLE3,
                ec2.InstanceSize.MEDIUM
            ),
            vpc=self.vpc,
            subnet_group=db_subnet_group,
            security_groups=[db_security_group],
            database_name="courtcase_db",
            credentials=rds.Credentials.from_generated_secret(
                "courtcase_admin",
                secret_name="court-case-db-credentials"
            ),
            allocated_storage=100,
            storage_encrypted=True,
            backup_retention=Duration.days(7),
            deletion_protection=True,
            removal_policy=RemovalPolicy.RETAIN
        )
    
    def create_redis_cache(self):
        """Create ElastiCache Redis cluster"""
        
        # Redis subnet group
        redis_subnet_group = elasticache.CfnSubnetGroup(
            self, "RedisSubnetGroup",
            description="Subnet group for Redis cache",
            subnet_ids=[subnet.subnet_id for subnet in self.vpc.private_subnets]
        )
        
        # Redis security group
        redis_security_group = ec2.SecurityGroup(
            self, "RedisSecurityGroup",
            vpc=self.vpc,
            description="Security group for Redis cache"
        )
        
        # Redis cluster
        self.redis_cluster = elasticache.CfnCacheCluster(
            self, "RedisCluster",
            cache_node_type="cache.t3.micro",
            engine="redis",
            num_cache_nodes=1,
            cache_subnet_group_name=redis_subnet_group.ref,
            vpc_security_group_ids=[redis_security_group.security_group_id]
        )
    
    def create_opensearch(self):
        """Create OpenSearch cluster for document search"""
        
        self.opensearch_domain = opensearch.Domain(
            self, "CourtCaseSearch",
            version=opensearch.EngineVersion.OPENSEARCH_2_3,
            capacity=opensearch.CapacityConfig(
                master_nodes=3,
                master_node_instance_type="t3.small.search",
                data_nodes=2,
                data_node_instance_type="t3.small.search"
            ),
            ebs=opensearch.EbsOptions(
                volume_size=20,
                volume_type=ec2.EbsDeviceVolumeType.GP3
            ),
            zone_awareness=opensearch.ZoneAwarenessConfig(
                enabled=True,
                availability_zone_count=2
            ),
            vpc=self.vpc,
            vpc_subnets=[ec2.SubnetSelection(
                subnet_type=ec2.SubnetType.PRIVATE_WITH_EGRESS
            )],
            security_groups=[
                ec2.SecurityGroup(
                    self, "OpenSearchSecurityGroup",
                    vpc=self.vpc,
                    description="Security group for OpenSearch"
                )
            ],
            encryption_at_rest=opensearch.EncryptionAtRestOptions(enabled=True),
            node_to_node_encryption=True,
            enforce_https=True,
            removal_policy=RemovalPolicy.DESTROY
        )
    
    def create_cognito(self):
        """Create Cognito User Pool for authentication"""
        
        self.user_pool = cognito.UserPool(
            self, "CourtCaseUserPool",
            user_pool_name="court-case-users",
            sign_in_aliases=cognito.SignInAliases(email=True),
            auto_verify=cognito.AutoVerifiedAttrs(email=True),
            password_policy=cognito.PasswordPolicy(
                min_length=12,
                require_lowercase=True,
                require_uppercase=True,
                require_digits=True,
                require_symbols=True
            ),
            mfa=cognito.Mfa.REQUIRED,
            mfa_second_factor=cognito.MfaSecondFactor(
                sms=True,
                otp=True
            ),
            account_recovery=cognito.AccountRecovery.EMAIL_ONLY,
            removal_policy=RemovalPolicy.DESTROY
        )
        
        # User pool client
        self.user_pool_client = cognito.UserPoolClient(
            self, "CourtCaseUserPoolClient",
            user_pool=self.user_pool,
            generate_secret=True,
            auth_flows=cognito.AuthFlow(
                user_password=True,
                user_srp=True
            ),
            o_auth=cognito.OAuthSettings(
                flows=cognito.OAuthFlows(
                    authorization_code_grant=True
                ),
                scopes=[cognito.OAuthScope.OPENID, cognito.OAuthScope.EMAIL, cognito.OAuthScope.PROFILE]
            )
        )
    
    def create_ecs_cluster(self):
        """Create ECS cluster for containerized applications"""
        
        # ECS Cluster
        self.cluster = ecs.Cluster(
            self, "CourtCaseCluster",
            vpc=self.vpc,
            container_insights=True
        )
        
        # Task execution role
        execution_role = iam.Role(
            self, "TaskExecutionRole",
            assumed_by=iam.ServicePrincipal("ecs-tasks.amazonaws.com"),
            managed_policies=[
                iam.ManagedPolicy.from_aws_managed_policy_name("service-role/AmazonECSTaskExecutionRolePolicy")
            ]
        )
        
        # Task role with permissions for AWS services
        task_role = iam.Role(
            self, "TaskRole",
            assumed_by=iam.ServicePrincipal("ecs-tasks.amazonaws.com")
        )
        
        # Grant permissions to access AWS services
        self.documents_bucket.grant_read_write(task_role)
        self.media_bucket.grant_read_write(task_role)
        self.database.secret.grant_read(task_role)
        
        # Backend service
        self.backend_service = ecs_patterns.ApplicationLoadBalancedFargateService(
            self, "BackendService",
            cluster=self.cluster,
            memory_limit_mib=2048,
            cpu=1024,
            desired_count=2,
            task_image_options=ecs_patterns.ApplicationLoadBalancedTaskImageOptions(
                image=ecs.ContainerImage.from_registry("iseepatterns/court-case-backend:latest"),
                container_port=8000,
                execution_role=execution_role,
                task_role=task_role,
                environment={
                    "AWS_REGION": self.region,
                    "S3_BUCKET_NAME": self.documents_bucket.bucket_name,
                    "S3_MEDIA_BUCKET": self.media_bucket.bucket_name,
                    "OPENSEARCH_ENDPOINT": self.opensearch_domain.domain_endpoint,
                    "COGNITO_USER_POOL_ID": self.user_pool.user_pool_id,
                    "COGNITO_CLIENT_ID": self.user_pool_client.user_pool_client_id
                },
                secrets={
                    "DATABASE_URL": ecs.Secret.from_secrets_manager(self.database.secret, "connectionString")
                },
                log_driver=ecs.LogDrivers.aws_logs(
                    stream_prefix="backend",
                    log_retention=logs.RetentionDays.ONE_WEEK
                )
            ),
            public_load_balancer=True,
            listener_port=80
        )
        
        # Allow backend to access database
        self.backend_service.service.connections.allow_to(
            self.database,
            ec2.Port.tcp(5432),
            "Backend to database"
        )
    
    def create_media_services(self):
        """Create media processing services"""
        
        # Media processing task definition
        media_task_def = ecs.FargateTaskDefinition(
            self, "MediaProcessingTask",
            memory_limit_mib=4096,
            cpu=2048
        )
        
        # Grant permissions
        self.media_bucket.grant_read_write(media_task_def.task_role)
        
        # Media processing container
        media_container = media_task_def.add_container(
            "MediaProcessor",
            image=ecs.ContainerImage.from_registry("iseepatterns/court-case-media:latest"),
            environment={
                "AWS_REGION": self.region,
                "S3_BUCKET_NAME": self.media_bucket.bucket_name
            },
            logging=ecs.LogDrivers.aws_logs(
                stream_prefix="media-processor",
                log_retention=logs.RetentionDays.ONE_WEEK
            )
        )
        
        # Media processing service
        self.media_service = ecs.FargateService(
            self, "MediaProcessingService",
            cluster=self.cluster,
            task_definition=media_task_def,
            desired_count=1
        )
    
    def setup_ai_services(self):
        """Setup AI services permissions and configurations"""
        
        # Grant Textract permissions
        self.backend_service.task_definition.task_role.add_to_policy(
            iam.PolicyStatement(
                effect=iam.Effect.ALLOW,
                actions=[
                    "textract:StartDocumentTextDetection",
                    "textract:GetDocumentTextDetection",
                    "textract:StartDocumentAnalysis",
                    "textract:GetDocumentAnalysis"
                ],
                resources=["*"]
            )
        )
        
        # Grant Comprehend permissions
        self.backend_service.task_definition.task_role.add_to_policy(
            iam.PolicyStatement(
                effect=iam.Effect.ALLOW,
                actions=[
                    "comprehend:DetectEntities",
                    "comprehend:DetectKeyPhrases",
                    "comprehend:DetectSentiment",
                    "comprehend:ClassifyDocument"
                ],
                resources=["*"]
            )
        )
        
        # Grant Transcribe permissions
        self.backend_service.task_definition.task_role.add_to_policy(
            iam.PolicyStatement(
                effect=iam.Effect.ALLOW,
                actions=[
                    "transcribe:StartTranscriptionJob",
                    "transcribe:GetTranscriptionJob",
                    "transcribe:ListTranscriptionJobs"
                ],
                resources=["*"]
            )
        )
        
        # Grant Bedrock permissions for AI features
        self.backend_service.task_definition.task_role.add_to_policy(
            iam.PolicyStatement(
                effect=iam.Effect.ALLOW,
                actions=[
                    "bedrock:InvokeModel",
                    "bedrock:InvokeModelWithResponseStream"
                ],
                resources=["*"]
            )
        )

app = cdk.App()
CourtCaseManagementStack(app, "CourtCaseManagementStack")
app.synth()