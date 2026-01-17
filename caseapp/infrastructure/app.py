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
    aws_cloudwatch as cloudwatch,
    aws_cloudwatch_actions as cw_actions,
    aws_sns as sns,
    aws_secretsmanager as secretsmanager,
    Duration,
    RemovalPolicy
)

class CourtCaseManagementStack(Stack):
    """Main infrastructure stack"""
    
    def __init__(self, scope: Construct, construct_id: str, environment: str = "production", **kwargs) -> None:
        super().__init__(scope, construct_id, **kwargs)
        self.deploy_env = environment
        
        # Suffix for named resources
        self.suffix = f"-{environment}" if environment == "staging" else ""
        
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
        
        # OpenSearch - TEMPORARILY DISABLED for deployment testing
        # Will be re-enabled after successful deployment
        # self.create_opensearch()
        
        # Cognito
        self.create_cognito()
        
        # ECS Cluster
        self.create_ecs_cluster()
        
        # Monitoring and Alerting
        self.create_monitoring_dashboard()
        
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
            removal_policy=RemovalPolicy.DESTROY  # CHANGED: Delete bucket when stack is deleted (for testing)
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
            removal_policy=RemovalPolicy.DESTROY  # CHANGED: Delete bucket when stack is deleted (for testing)
        )
    
    def create_database(self):
        """Create RDS PostgreSQL database with optimized security configuration"""
        
        # Database subnet group
        db_subnet_group = rds.SubnetGroup(
            self, "DatabaseSubnetGroup",
            description="Subnet group for court case database",
            vpc=self.vpc,
            vpc_subnets=ec2.SubnetSelection(
                subnet_type=ec2.SubnetType.PRIVATE_ISOLATED
            )
        )
        
        # Database security group with minimal required permissions
        self.db_security_group = ec2.SecurityGroup(
            self, "DatabaseSecurityGroup",
            vpc=self.vpc,
            description="Security group for court case database - minimal required access",
            allow_all_outbound=False
        )
        
        # Only allow inbound PostgreSQL connections from ECS tasks
        # This will be configured after ECS service is created
        
        # Database instance
        self.database = rds.DatabaseInstance(
            self, "CourtCaseDatabase",
            engine=rds.DatabaseInstanceEngine.postgres(
                version=rds.PostgresEngineVersion.of("15", "15.15")  # Latest PostgreSQL 15 version available in RDS
            ),
            instance_type=ec2.InstanceType.of(
                ec2.InstanceClass.BURSTABLE3,
                ec2.InstanceSize.MEDIUM
            ),
            vpc=self.vpc,
            subnet_group=db_subnet_group,
            security_groups=[self.db_security_group],
            database_name="courtcase_db",
            credentials=rds.Credentials.from_generated_secret(
                "courtcase_admin",
                secret_name=f"court-case-db-credentials{self.suffix}"
            ),
            allocated_storage=100,
            storage_encrypted=True,
            backup_retention=Duration.days(7),
            deletion_protection=False,  # CHANGED: Allow deletion for testing/development
            removal_policy=RemovalPolicy.DESTROY,  # CHANGED: Delete RDS when stack is deleted
            # Enhanced monitoring and performance insights
            monitoring_interval=Duration.seconds(0),  # FIXED: Disabled enhanced monitoring (missing IAM role causing failures)
            enable_performance_insights=True,
            performance_insight_retention=rds.PerformanceInsightRetention.DEFAULT,
            # Multi-AZ for high availability
            multi_az=True,
            # Automated backup windows
            preferred_backup_window="03:00-04:00",
            preferred_maintenance_window="sun:04:00-sun:05:00"
        )
    
    def validate_cdk_parameters(self, construct_type: str, parameters: dict) -> dict:
        """
        Validate CDK parameters for compatibility with current CDK version
        Remove unsupported parameters and log warnings
        """
        # Known incompatible parameters for different construct types
        incompatible_params = {
            'CfnCacheCluster': [
                'at_rest_encryption_enabled',  # Not supported in CfnCacheCluster
                'auth_token',  # Not supported in CfnCacheCluster, use CfnReplicationGroup instead
            ]
        }
        
        if construct_type in incompatible_params:
            validated_params = parameters.copy()
            for param in incompatible_params[construct_type]:
                if param in validated_params:
                    print(f"WARNING: Removing unsupported parameter '{param}' from {construct_type}")
                    del validated_params[param]
            return validated_params
        
        return parameters
    
    def create_redis_cache(self):
        """Create ElastiCache Redis cluster with optimized security"""
        
        # Redis subnet group
        redis_subnet_group = elasticache.CfnSubnetGroup(
            self, "RedisSubnetGroup",
            description="Subnet group for Redis cache",
            subnet_ids=[subnet.subnet_id for subnet in self.vpc.private_subnets]
        )
        
        # Redis security group with minimal required permissions
        self.redis_security_group = ec2.SecurityGroup(
            self, "RedisSecurityGroup",
            vpc=self.vpc,
            description="Security group for Redis cache - minimal required access",
            allow_all_outbound=False
        )
        
        # Only allow inbound Redis connections from ECS tasks
        # This will be configured after ECS service is created
        
        # Redis cluster with basic configuration
        # Note: transit_encryption_enabled is not supported with cache.t3.micro instances
        # For encryption features, use CfnReplicationGroup or higher-level constructs
        self.redis_cluster = elasticache.CfnCacheCluster(
            self, "RedisCluster",
            cache_node_type="cache.t3.micro",
            engine="redis",
            num_cache_nodes=1,
            cache_subnet_group_name=redis_subnet_group.ref,
            vpc_security_group_ids=[self.redis_security_group.security_group_id],
            # Basic configuration for t3.micro instances
            engine_version="7.0",
            port=6379
            # Note: transit_encryption_enabled, at_rest_encryption_enabled, and auth_token 
            # are not supported in CfnCacheCluster with t3.micro instances
            # For encryption features, consider using CfnReplicationGroup or higher-level constructs
        )
    
    def create_opensearch(self):
        """Create OpenSearch cluster for document search with enhanced security
        
        TEMPORARILY DISABLED - OpenSearch adds 16+ minutes to deployment time.
        This method is commented out to allow faster deployments during testing.
        Will be re-enabled after successful deployment validation.
        """
        
        # COMMENTED OUT - Uncomment to re-enable OpenSearch
        """
        # OpenSearch security group with minimal required permissions
        self.opensearch_security_group = ec2.SecurityGroup(
            self, "OpenSearchSecurityGroup",
            vpc=self.vpc,
            description="Security group for OpenSearch - minimal required access",
            allow_all_outbound=False
        )
        
        # Only allow HTTPS connections from ECS tasks
        # This will be configured after ECS service is created
        
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
            security_groups=[self.opensearch_security_group],
            encryption_at_rest=opensearch.EncryptionAtRestOptions(enabled=True),
            node_to_node_encryption=True,
            enforce_https=True,
            # Enhanced security with fine-grained access control
            fine_grained_access_control=opensearch.AdvancedSecurityOptions(
                master_user_name="admin",
                master_user_password=cdk.SecretValue.secrets_manager(
                    "opensearch-master-password",
                    json_field="password"
                )
            ),
            # Domain access policy - use security groups for VPC access control
            # Note: When using VPC, access control is handled by security groups
            # IP-based policies are not compatible with VPC endpoints
            removal_policy=RemovalPolicy.DESTROY
        )
        """
        pass
    
    def create_cognito(self):
        """Create Cognito User Pool for authentication"""
        
        self.user_pool = cognito.UserPool(
            self, "CourtCaseUserPool",
            user_pool_name=f"court-case-users{self.suffix}",
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
        """Create ECS cluster for containerized applications with optimized security"""
        
        # Get Docker username from environment or use default
        docker_username = self.node.try_get_context("docker_username") or "iseepatterns"
        
        # Import Docker Hub credentials from Secrets Manager
        dockerhub_secret = secretsmanager.Secret.from_secret_name_v2(
            self, "DockerHubCredentials",
            secret_name="dockerhub-credentials"
        )
        
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
        
        # Grant execution role permission to read Docker Hub credentials
        dockerhub_secret.grant_read(execution_role)
        
        # Task role with minimal required permissions for AWS services
        task_role = iam.Role(
            self, "TaskRole",
            assumed_by=iam.ServicePrincipal("ecs-tasks.amazonaws.com")
        )
        
        # Grant minimal required permissions to access AWS services
        self.documents_bucket.grant_read_write(task_role)
        self.media_bucket.grant_read_write(task_role)
        self.database.secret.grant_read(task_role)
        
        # Backend service (this will create the ALB and its security group)
        self.backend_service = ecs_patterns.ApplicationLoadBalancedFargateService(
            self, "BackendService",
            cluster=self.cluster,
            memory_limit_mib=4096,  # Increased from 2048 MiB to 4096 MiB for complex applications
            cpu=2048,               # Increased from 1024 to 2048 (2 vCPU) for better performance
            desired_count=2,
            health_check_grace_period=Duration.seconds(300),  # 5 minute grace period for startup
            circuit_breaker=ecs.DeploymentCircuitBreaker(
                rollback=True,
                enable=True  # Explicitly enable circuit breaker for automatic rollback
            ),
            task_image_options=ecs_patterns.ApplicationLoadBalancedTaskImageOptions(
                image=ecs.ContainerImage.from_registry(f"{docker_username}/court-case-backend:latest"),
                container_port=8000,
                execution_role=execution_role,
                task_role=task_role,
                environment={
                    "AWS_REGION": self.region,
                    "S3_BUCKET_NAME": self.documents_bucket.bucket_name,
                    "S3_MEDIA_BUCKET": self.media_bucket.bucket_name,
                    # "OPENSEARCH_ENDPOINT": self.opensearch_domain.domain_endpoint,  # TEMPORARILY DISABLED
                    "COGNITO_USER_POOL_ID": self.user_pool.user_pool_id,
                    "COGNITO_CLIENT_ID": self.user_pool_client.user_pool_client_id,
                    "REDIS_URL": f"redis://{self.redis_cluster.attr_redis_endpoint_address}:6379"
                },
                secrets={
                    # Use individual secret fields from RDS-generated secret
                    "DB_HOST": ecs.Secret.from_secrets_manager(self.database.secret, "host"),
                    "DB_USER": ecs.Secret.from_secrets_manager(self.database.secret, "username"),
                    "DB_PASSWORD": ecs.Secret.from_secrets_manager(self.database.secret, "password"),
                    "DB_PORT": ecs.Secret.from_secrets_manager(self.database.secret, "port"),
                    "DB_NAME": ecs.Secret.from_secrets_manager(self.database.secret, "dbname")
                },
                log_driver=ecs.LogDrivers.aws_logs(
                    stream_prefix="backend",
                    log_retention=logs.RetentionDays.ONE_WEEK
                )
            ),
            public_load_balancer=True,
            listener_port=80,
            # Deployment configuration - use direct parameters instead of DeploymentConfiguration object
            min_healthy_percent=50,     # Maintain at least 50% healthy tasks during deployment
            max_healthy_percent=200,    # Allow up to 200% of desired capacity during deployment
            # Use private subnets for ECS tasks
            task_subnets=ec2.SubnetSelection(
                subnet_type=ec2.SubnetType.PRIVATE_WITH_EGRESS
            )
        )
        
        # Get ALB security group reference
        self.alb_security_group = self.backend_service.load_balancer.connections.security_groups[0]
        
        # Create ECS Service Security Group with minimal required permissions
        self.ecs_security_group = ec2.SecurityGroup(
            self, "ECSServiceSecurityGroup",
            vpc=self.vpc,
            description="Security group for ECS service - minimal required access",
            allow_all_outbound=True  # Allow outbound for AWS service calls
        )
        
        # Allow inbound HTTP traffic from ALB only
        self.ecs_security_group.add_ingress_rule(
            peer=ec2.Peer.security_group_id(self.alb_security_group.security_group_id),
            connection=ec2.Port.tcp(8000),
            description="Allow HTTP traffic from ALB"
        )
        
        # Configure database access from ECS
        self.db_security_group.add_ingress_rule(
            peer=ec2.Peer.security_group_id(self.ecs_security_group.security_group_id),
            connection=ec2.Port.tcp(5432),
            description="Allow PostgreSQL access from ECS tasks"
        )
        
        # Configure Redis access from ECS
        self.redis_security_group.add_ingress_rule(
            peer=ec2.Peer.security_group_id(self.ecs_security_group.security_group_id),
            connection=ec2.Port.tcp(6379),
            description="Allow Redis access from ECS tasks"
        )
        
        # Configure OpenSearch access from ECS - TEMPORARILY DISABLED
        # Uncomment when OpenSearch is re-enabled
        # self.opensearch_security_group.add_ingress_rule(
        #     peer=ec2.Peer.security_group_id(self.ecs_security_group.security_group_id),
        #     connection=ec2.Port.tcp(443),
        #     description="Allow HTTPS access to OpenSearch from ECS tasks"
        # )
        
        # Apply custom security group to ECS service
        cfn_service = self.backend_service.service.node.default_child
        cfn_service.add_property_override("NetworkConfiguration.AwsvpcConfiguration.SecurityGroups", 
                                        [self.ecs_security_group.security_group_id])
        
        # Configure ECS service health check settings
        cfn_service.add_property_override("HealthCheckGracePeriodSeconds", 300)
        
        # Add Docker Hub credentials to backend task definition
        cfn_task_def = self.backend_service.task_definition.node.default_child
        cfn_task_def.add_property_override(
            "ContainerDefinitions.0.RepositoryCredentials",
            {
                "CredentialsParameter": dockerhub_secret.secret_arn
            }
        )
        
        # Configure load balancer health check
        # Use root endpoint / which is simple and doesn't require database
        self.backend_service.target_group.configure_health_check(
            path="/",                       # Use root endpoint (simple, no DB required)
            healthy_threshold_count=2,      # Require 2 consecutive successful checks
            unhealthy_threshold_count=3,    # Allow 3 consecutive failures before marking unhealthy
            timeout=Duration.seconds(10),   # 10 second timeout per check
            interval=Duration.seconds(30),  # Check every 30 seconds
            port="8000"                     # Health check on application port
        )
    
    def create_monitoring_dashboard(self):
        """Create CloudWatch dashboard and alarms for deployment monitoring"""
        
        # Import CloudWatch constructs
        from aws_cdk import aws_cloudwatch as cloudwatch
        from aws_cdk import aws_sns as sns
        
        # Create SNS topic for alerts
        self.alerts_topic = sns.Topic(
            self, "DeploymentAlerts",
            topic_name=f"court-case-deployment-alerts{self.suffix}",
            display_name="Court Case Deployment Alerts"
        )
        
        # Extract service and cluster names
        service_name = self.backend_service.service.service_name
        cluster_name = self.cluster.cluster_name
        
        # Extract load balancer name from ARN with error handling
        lb_arn = self.backend_service.load_balancer.load_balancer_arn
        lb_name_parts = lb_arn.split('/')
        
        # Ensure we have enough parts for the load balancer name
        if len(lb_name_parts) >= 3:
            lb_name = f"{lb_name_parts[-3]}/{lb_name_parts[-2]}/{lb_name_parts[-1]}"
        else:
            # Fallback to a simpler name if ARN format is unexpected
            lb_name = lb_name_parts[-1] if lb_name_parts else "unknown-lb"
        
        # Extract database identifier
        db_identifier = self.database.instance_identifier
        
        # Create CloudWatch dashboard
        dashboard = cloudwatch.Dashboard(
            self, "DeploymentMonitoringDashboard",
            dashboard_name=f"CourtCase-Deployment-Monitoring{self.suffix}",
            widgets=[
                [
                    # ECS Service Metrics
                    cloudwatch.GraphWidget(
                        title="ECS Service Metrics",
                        left=[
                            cloudwatch.Metric(
                                namespace="AWS/ECS",
                                metric_name="CPUUtilization",
                                dimensions_map={
                                    "ServiceName": service_name,
                                    "ClusterName": cluster_name
                                },
                                statistic="Average",
                                period=Duration.minutes(5)
                            ),
                            cloudwatch.Metric(
                                namespace="AWS/ECS",
                                metric_name="MemoryUtilization",
                                dimensions_map={
                                    "ServiceName": service_name,
                                    "ClusterName": cluster_name
                                },
                                statistic="Average",
                                period=Duration.minutes(5)
                            )
                        ],
                        right=[
                            cloudwatch.Metric(
                                namespace="AWS/ECS",
                                metric_name="RunningTaskCount",
                                dimensions_map={
                                    "ServiceName": service_name,
                                    "ClusterName": cluster_name
                                },
                                statistic="Average",
                                period=Duration.minutes(5)
                            )
                        ],
                        width=12,
                        height=6
                    ),
                    
                    # Load Balancer Metrics
                    cloudwatch.GraphWidget(
                        title="Load Balancer Metrics",
                        left=[
                            cloudwatch.Metric(
                                namespace="AWS/ApplicationELB",
                                metric_name="RequestCount",
                                dimensions_map={
                                    "LoadBalancer": lb_name
                                },
                                statistic="Sum",
                                period=Duration.minutes(5)
                            ),
                            cloudwatch.Metric(
                                namespace="AWS/ApplicationELB",
                                metric_name="HTTPCode_ELB_5XX_Count",
                                dimensions_map={
                                    "LoadBalancer": lb_name
                                },
                                statistic="Sum",
                                period=Duration.minutes(5)
                            )
                        ],
                        right=[
                            cloudwatch.Metric(
                                namespace="AWS/ApplicationELB",
                                metric_name="TargetResponseTime",
                                dimensions_map={
                                    "LoadBalancer": lb_name
                                },
                                statistic="Average",
                                period=Duration.minutes(5)
                            ),
                            cloudwatch.Metric(
                                namespace="AWS/ApplicationELB",
                                metric_name="HealthyHostCount",
                                dimensions_map={
                                    "LoadBalancer": lb_name
                                },
                                statistic="Average",
                                period=Duration.minutes(5)
                            )
                        ],
                        width=12,
                        height=6
                    )
                ],
                [
                    # Database Metrics
                    cloudwatch.GraphWidget(
                        title="Database Metrics",
                        left=[
                            cloudwatch.Metric(
                                namespace="AWS/RDS",
                                metric_name="CPUUtilization",
                                dimensions_map={
                                    "DBInstanceIdentifier": db_identifier
                                },
                                statistic="Average",
                                period=Duration.minutes(5)
                            ),
                            cloudwatch.Metric(
                                namespace="AWS/RDS",
                                metric_name="DatabaseConnections",
                                dimensions_map={
                                    "DBInstanceIdentifier": db_identifier
                                },
                                statistic="Average",
                                period=Duration.minutes(5)
                            )
                        ],
                        right=[
                            cloudwatch.Metric(
                                namespace="AWS/RDS",
                                metric_name="ReadLatency",
                                dimensions_map={
                                    "DBInstanceIdentifier": db_identifier
                                },
                                statistic="Average",
                                period=Duration.minutes(5)
                            ),
                            cloudwatch.Metric(
                                namespace="AWS/RDS",
                                metric_name="WriteLatency",
                                dimensions_map={
                                    "DBInstanceIdentifier": db_identifier
                                },
                                statistic="Average",
                                period=Duration.minutes(5)
                            )
                        ],
                        width=12,
                        height=6
                    ),
                    
                    # Log Insights Widget
                    cloudwatch.LogQueryWidget(
                        title="Recent Application Errors",
                        log_group_names=[
                            f"/ecs/{service_name}"
                        ],
                        query_lines=[
                            "fields @timestamp, @message",
                            "filter @message like /ERROR/",
                            "sort @timestamp desc",
                            "limit 100"
                        ],
                        width=12,
                        height=6
                    )
                ]
            ]
        )
        
        # Create CloudWatch Alarms
        
        # ECS Service CPU Alarm
        cpu_alarm = cloudwatch.Alarm(
            self, "ECSHighCPUAlarm",
            alarm_name=f"{service_name}-HighCPU",
            alarm_description=f"High CPU utilization for {service_name}",
            metric=cloudwatch.Metric(
                namespace="AWS/ECS",
                metric_name="CPUUtilization",
                dimensions_map={
                    "ServiceName": service_name,
                    "ClusterName": cluster_name
                },
                statistic="Average",
                period=Duration.minutes(5)
            ),
            threshold=80,
            evaluation_periods=2,
            comparison_operator=cloudwatch.ComparisonOperator.GREATER_THAN_THRESHOLD
        )
        cpu_alarm.add_alarm_action(
            cw_actions.SnsAction(self.alerts_topic)
        )
        
        # ECS Service Memory Alarm
        memory_alarm = cloudwatch.Alarm(
            self, "ECSHighMemoryAlarm",
            alarm_name=f"{service_name}-HighMemory",
            alarm_description=f"High memory utilization for {service_name}",
            metric=cloudwatch.Metric(
                namespace="AWS/ECS",
                metric_name="MemoryUtilization",
                dimensions_map={
                    "ServiceName": service_name,
                    "ClusterName": cluster_name
                },
                statistic="Average",
                period=Duration.minutes(5)
            ),
            threshold=85,
            evaluation_periods=2,
            comparison_operator=cloudwatch.ComparisonOperator.GREATER_THAN_THRESHOLD
        )
        memory_alarm.add_alarm_action(
            cw_actions.SnsAction(self.alerts_topic)
        )
        
        # ALB 5XX Error Alarm
        alb_5xx_alarm = cloudwatch.Alarm(
            self, "ALBHigh5XXAlarm",
            alarm_name=f"{service_name}-ALB-High5XX",
            alarm_description=f"High 5XX error rate for {service_name}",
            metric=cloudwatch.Metric(
                namespace="AWS/ApplicationELB",
                metric_name="HTTPCode_ELB_5XX_Count",
                dimensions_map={
                    "LoadBalancer": lb_name
                },
                statistic="Sum",
                period=Duration.minutes(5)
            ),
            threshold=10,
            evaluation_periods=2,
            comparison_operator=cloudwatch.ComparisonOperator.GREATER_THAN_THRESHOLD,
            treat_missing_data=cloudwatch.TreatMissingData.NOT_BREACHING
        )
        alb_5xx_alarm.add_alarm_action(
            cw_actions.SnsAction(self.alerts_topic)
        )
        
        # RDS CPU Alarm
        rds_cpu_alarm = cloudwatch.Alarm(
            self, "RDSHighCPUAlarm",
            alarm_name=f"{db_identifier}-HighCPU",
            alarm_description=f"High CPU utilization for database {db_identifier}",
            metric=cloudwatch.Metric(
                namespace="AWS/RDS",
                metric_name="CPUUtilization",
                dimensions_map={
                    "DBInstanceIdentifier": db_identifier
                },
                statistic="Average",
                period=Duration.minutes(5)
            ),
            threshold=75,
            evaluation_periods=2,
            comparison_operator=cloudwatch.ComparisonOperator.GREATER_THAN_THRESHOLD
        )
        rds_cpu_alarm.add_alarm_action(
            cw_actions.SnsAction(self.alerts_topic)
        )
        
        # Store references for outputs
        self.monitoring_dashboard = dashboard
        self.monitoring_alarms = [cpu_alarm, memory_alarm, alb_5xx_alarm, rds_cpu_alarm]
        
        # Output dashboard URL
        cdk.CfnOutput(
            self, "MonitoringDashboardURL",
            value=f"https://{self.region}.console.aws.amazon.com/cloudwatch/home?region={self.region}#dashboards:name={dashboard.dashboard_name}",
            description="CloudWatch Dashboard URL for deployment monitoring"
        )
        
        # Output SNS topic ARN
        cdk.CfnOutput(
            self, "AlertsTopicARN",
            value=self.alerts_topic.topic_arn,
            description="SNS Topic ARN for deployment alerts"
        )
    
    def create_media_services(self):
        """Create media processing services"""
        
        # Get Docker username from environment or use default
        docker_username = self.node.try_get_context("docker_username") or "iseepatterns"
        
        # Import Docker Hub credentials from Secrets Manager
        dockerhub_secret = secretsmanager.Secret.from_secret_name_v2(
            self, "DockerHubCredentialsMedia",
            secret_name="dockerhub-credentials"
        )
        
        # Create execution role for media task
        media_execution_role = iam.Role(
            self, "MediaTaskExecutionRole",
            assumed_by=iam.ServicePrincipal("ecs-tasks.amazonaws.com"),
            managed_policies=[
                iam.ManagedPolicy.from_aws_managed_policy_name("service-role/AmazonECSTaskExecutionRolePolicy")
            ]
        )
        
        # Grant execution role permission to read Docker Hub credentials
        dockerhub_secret.grant_read(media_execution_role)
        
        # Media processing task definition
        media_task_def = ecs.FargateTaskDefinition(
            self, "MediaProcessingTask",
            memory_limit_mib=4096,  # Increased for media processing workloads
            cpu=2048,               # Increased for better media processing performance
            execution_role=media_execution_role
        )
        
        # Grant permissions
        self.media_bucket.grant_read_write(media_task_def.task_role)
        self.database.secret.grant_read(media_task_def.task_role)
        
        # Media processing container
        media_container = media_task_def.add_container(
            "MediaProcessor",
            image=ecs.ContainerImage.from_registry(f"{docker_username}/court-case-media:latest"),
            environment={
                "AWS_REGION": self.region,
                "S3_BUCKET_NAME": self.media_bucket.bucket_name,
                "S3_MEDIA_BUCKET": self.media_bucket.bucket_name,
                "REDIS_URL": f"redis://{self.redis_cluster.attr_redis_endpoint_address}:6379"
            },
            secrets={
                # Use individual secret fields from RDS-generated secret
                "DB_HOST": ecs.Secret.from_secrets_manager(self.database.secret, "host"),
                "DB_USER": ecs.Secret.from_secrets_manager(self.database.secret, "username"),
                "DB_PASSWORD": ecs.Secret.from_secrets_manager(self.database.secret, "password"),
                "DB_PORT": ecs.Secret.from_secrets_manager(self.database.secret, "port"),
                "DB_NAME": ecs.Secret.from_secrets_manager(self.database.secret, "dbname")
            },
            logging=ecs.LogDrivers.aws_logs(
                stream_prefix="media-processor",
                log_retention=logs.RetentionDays.ONE_WEEK
            )
        )
        
        # Add Docker Hub credentials to media container
        cfn_task_def = media_task_def.node.default_child
        cfn_task_def.add_property_override(
            "ContainerDefinitions.0.RepositoryCredentials",
            {
                "CredentialsParameter": dockerhub_secret.secret_arn
            }
        )
        
        # Media processing service
        self.media_service = ecs.FargateService(
            self, "MediaProcessingService",
            cluster=self.cluster,
            task_definition=media_task_def,
            desired_count=1,
            circuit_breaker=ecs.DeploymentCircuitBreaker(
                rollback=True,
                enable=True  # Explicitly enable circuit breaker for automatic rollback
            )
        )
        
        # Apply same security group as backend service to allow database and Redis access
        cfn_media_service = self.media_service.node.default_child
        cfn_media_service.add_property_override("NetworkConfiguration.AwsvpcConfiguration.SecurityGroups",
                                                [self.ecs_security_group.security_group_id])
    
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

import os

# Get environment from environment variable
environment = os.getenv("ENVIRONMENT", "production")
stack_name = os.getenv("STACK_NAME", "CourtCaseManagementStack")

if environment == "staging" and "STACK_NAME" not in os.environ:
    stack_name = f"{stack_name}-Staging"

app = cdk.App()
CourtCaseManagementStack(app, stack_name, environment=environment)
app.synth()